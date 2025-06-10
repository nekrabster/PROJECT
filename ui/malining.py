import os
import logging
import re
import random
from random import randint
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum, auto
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QCheckBox, QGroupBox,
    QHBoxLayout, QMessageBox, QLineEdit, QTextEdit, QLabel, QRadioButton,
    QButtonGroup, QSplitter, QDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from telethon.tl.types import User
from telethon.tl.functions.contacts import GetContactsRequest, AddContactRequest
from ui.loader import load_config, load_proxy
from ui.session_win import SessionWindow
from ui.okak import ErrorReportDialog
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection, TelegramErrorType)
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.mate import distributor, TaskType
from ui.malina import MessageEditorDialog
DEFAULT_MAX_FLOOD_WAIT = 10
DEFAULT_MIN_DELAY = 1
DEFAULT_MAX_DELAY = 5
class MailingMode(Enum):
    FORWARD = auto()
    USERS = auto()
    DIALOGS = auto()
    MASS = auto()
@dataclass
class MailingConfig:
    mode: MailingMode
    message: str
    media_path: Optional[str] = None
    silent: bool = False
    add_to_contacts: bool = False
    min_delay: Optional[int] = None
    max_delay: Optional[int] = None
    use_proxy: bool = False
    user_list: Optional[List[str]] = None
    from_chat: Optional[str] = None
    message_ids: Optional[List[str]] = None
    forward_to_users: bool = False
    forward_to_chats: bool = False
@dataclass
class TelegramErrorInfo:
    type: TelegramErrorType
    message: str
    wait_time: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
class BaseMailingMode:
    def __init__(self, thread):
        self.thread = thread
        self.client = None
        self.total_targets = 0
        self.processed_targets = 0
        self.is_stopped = False
        self.logger = logging.getLogger(self.__class__.__name__)
    @staticmethod
    def normalize_joinchat_link(link_text: str) -> str:
        link_text = link_text.strip()

        if link_text.startswith("+"):
            return f"https://t.me/{link_text}"

        if "joinchat/" in link_text:
            if link_text.startswith("https://t.me/joinchat/"):
                hash_code = link_text.split("joinchat/", 1)[1]
                return f"https://t.me/+{hash_code}"
            elif link_text.startswith("t.me/joinchat/"):
                hash_code = link_text.split("joinchat/", 1)[1]
                return f"https://t.me/+{hash_code}"
            elif link_text.startswith("joinchat/"):
                hash_code = link_text.split("joinchat/", 1)[1]
                return f"https://t.me/+{hash_code}"
            elif link_text.startswith("@joinchat/"):
                hash_code = link_text.split("@joinchat/", 1)[1]
                return f"https://t.me/+{hash_code}"
        if link_text.startswith("https://t.me/+"):
            return link_text
        elif link_text.startswith("t.me/+"):
            return f"https://{link_text}"
        return link_text
    async def initialize(self, client, *args, **kwargs):
        self.client = client
        self.is_stopped = False
        return True
    async def execute(self, *args, **kwargs):
        pass
    async def handle_error(self, entity_name, error, *args, **kwargs):
        error_text = str(error).lower()
        if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
            self.thread.window.update_mailing_stats('sent_failed')
            if "chat admin privileges" in error_text:
                self.thread.window.update_mailing_stats('no_permissions')
            elif "spam" in error_text:
                self.thread.window.update_mailing_stats('spam_blocked')
                self.thread.log_signal.emit(f"⚠️ {os.path.basename(self.thread.session_file)} | Обнаружен спам блок")
            elif "auth" in error_text or "unauthorized" in error_text or "session" in error_text:
                self.thread.window.update_mailing_stats('unauthorized')
                self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Сессия не авторизована")
        session_name = os.path.basename(self.thread.session_file)
        if "wait of" in error_text and "seconds" in error_text:
            await self.handle_wait_limit(error_text, entity_name)
            return False
        self.thread.log_signal.emit(f"❌ {session_name} | Ошибка при отправке в {entity_name}: {error}")
        if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'show_error_dialog'):
            self.thread.window.show_error_dialog(str(error))
        return False
    def _randomize_message(self, text: str) -> str:
        if not getattr(self.thread, 'randomize_text', False):
            return text
        def replace_random(match):
            options = match.group(1).split('|')
            return random.choice(options)
        return re.sub(r'\{([^}]+)\}', replace_random, text)
    async def send_message(self, entity, message, media_path=None, *args, **kwargs):
        if self.thread.is_stopped:
            return False
        try:
            entity_name = getattr(entity, 'username', None) or getattr(entity, 'title', None) or str(entity.id)
            message = self._randomize_message(message)
            if media_path:
                await self.client.send_file(entity, media_path, caption=message, silent=self.thread.silent)
            else:
                await self.client.send_message(entity, message, silent=self.thread.silent)
            if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                self.thread.window.update_mailing_stats('sent_success')
            self.thread.log_signal.emit(f"✅ {os.path.basename(self.thread.session_file)} отправила сообщение {entity_name}")
            await self.thread.apply_delay()
            return True
        except Exception as e:
            await self.handle_error(entity_name, e)
            return False
    def update_progress(self, value=None, *args, **kwargs):
        if value is not None:
            self.processed_targets = value
        if self.total_targets > 0:
            progress = int((self.processed_targets / self.total_targets) * 100)
            self.thread.emit_progress(progress, f"Отправлено {self.processed_targets}/{self.total_targets}")
    async def handle_wait_limit(self, error_text, entity_name=None):
        match = re.search(r'(\d+) seconds', error_text)
        if match:
            wait_time = int(match.group(1))
            MailingThread.all_wait_limits_count += 1
            if wait_time > 3600:
                hours = wait_time // 3600
                minutes = (wait_time % 3600) // 60
                total_minutes = (hours * 60) + minutes
                self.thread.log_signal.emit(f"🚫 Обнаружено длительное ограничение {hours} ч. {minutes} мин. Аварийная остановка!")
                if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'handle_long_wait'):
                    self.thread.window.handle_long_wait(total_minutes, entity_name)
                return False
            if MailingThread.all_wait_limits_count >= MailingThread.MAX_ALL_WAIT_LIMITS:
                self.thread.log_signal.emit(f"🚫 Обнаружено {MailingThread.all_wait_limits_count} временных ограничений подряд! Аварийная остановка для защиты аккаунта.")
                if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'emergency_stop_signal'):
                    self.thread.window.emergency_stop_signal.emit()
                    if hasattr(self.thread.window, 'stop_mailing'):
                        self.thread.window.stop_mailing()
                return False
            if wait_time > 60:
                minutes = wait_time // 60
                self.thread.log_signal.emit(f"⏱️ Временное ограничение №{MailingThread.all_wait_limits_count}: {minutes} мин. для {entity_name}")
            else:
                self.thread.log_signal.emit(f"⏱️ Временное ограничение №{MailingThread.all_wait_limits_count}: {wait_time} сек. для {entity_name}")
            if MailingThread.all_wait_limits_count >= MailingThread.MAX_ALL_WAIT_LIMITS // 2:
                self.thread.log_signal.emit(f"⚠️ Внимание! Уже {MailingThread.all_wait_limits_count} ограничений из {MailingThread.MAX_ALL_WAIT_LIMITS}! Близка аварийная остановка.")
            return False
        return False
    async def verify_user_contacts(self, user_list, *args, **kwargs):
        if not user_list:
            return []
        verified_users = []
        for username in user_list:
            if self.thread.is_stopped:
                break
            try:
                entity = await self.client.get_entity(username)
                if not isinstance(entity, User) or entity.bot or getattr(entity, 'deleted', False):
                    self.thread.log_signal.emit(f"⚠️ Пропущен {username}: не является пользователем")
                    continue
                verified_users.append(username)
            except Exception as e:
                if self.thread.add_to_contacts and "not found" in str(e).lower():
                    self.thread.log_signal.emit(f"⚠️ Пользователь {username} не найден")
                else:
                    self.thread.log_signal.emit(f"⚠️ Ошибка проверки {username}: {str(e)}")
        return verified_users
class ForwardMode(BaseMailingMode):
    async def execute(self, *args, **kwargs):
        try:
            from_chat, message_ids = await self.process_message_link()
            if not from_chat:
                return
            targets = []
            if self.thread.forward_to_users and self.thread.user_list:
                for username in self.thread.user_list:
                    try:
                        entity = await self.client.get_entity(username)

                        targets.append((entity, username))
                    except Exception:
                        self.thread.log_signal.emit(f"⚠️ {os.path.basename(self.thread.session_file)} | Не удалось найти пользователя {username}")
            elif self.thread.forward_to_chats:
                if self.thread.groups_list:
                    for group_username in self.thread.groups_list:
                        try:
                            entity = await self.client.get_entity(group_username)
                            targets.append((entity, group_username))
                        except Exception as e:
                            self.thread.log_signal.emit(f"⚠️ {os.path.basename(self.thread.session_file)} | Не удалось найти группу {group_username}: {str(e)}")
                else:
                    self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Список групп пуст")
                    return
            if not targets:
                self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Нет целей для пересылки")
                return
            self.total_targets = len(targets)
            self.processed_targets = 0
            self.update_progress()
            if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                self.thread.window.update_mailing_stats('total_targets', self.total_targets)
            messages_to_forward = []
            for msg_id in message_ids:
                try:
                    messages = await self.client.get_messages(from_chat, ids=msg_id)
                    if messages:
                        messages_to_forward.append(messages)
                except Exception as e:
                    self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Не удалось получить сообщение {msg_id}: {str(e)}")
            if not messages_to_forward:
                self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Не удалось получить сообщения для пересылки")
                return
            for entity, name in targets:
                if self.thread.is_stopped:
                    break
                try:
                    for message in messages_to_forward:
                        if message.media:
                            await self.client.send_file(
                                entity,
                                file=message.media,
                                caption=message.text,
                                silent=self.thread.silent
                            )
                        else:
                            await self.client.send_message(
                                entity,
                                message.text or message.raw_text,
                                silent=self.thread.silent
                            )
                    if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                        self.thread.window.update_mailing_stats('sent_success')
                    self.processed_targets += 1
                    self.update_progress()
                    self.thread.log_signal.emit(f"✅ {os.path.basename(self.thread.session_file)} отправила сообщение {name}")
                    await self.thread.apply_delay()
                except Exception as e:
                    await self.handle_error(name, e)
        except Exception as e:
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Ошибка при пересылке: {str(e)}")
    async def process_message_link(self, *args, **kwargs) -> Tuple[Any, List[int]]:
        from_chat = self.thread.from_chat
        message_ids = []
        message_link_pattern = r'https?://t\.me/([^/]+)/(\d+)'
        alt_message_link_pattern = r'@([\w\d]+)/(\d+)'
        if isinstance(self.thread.from_chat, str):
            match = re.match(message_link_pattern, self.thread.from_chat)
            if not match:
                match = re.match(alt_message_link_pattern, self.thread.from_chat)
            if match:
                channel_name, message_id = match.groups()
                try:
                    from_chat = await self.client.get_entity(f"@{channel_name}")
                    message_ids = [int(message_id)]
                except Exception as e:
                    self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Не удалось получить канал: {str(e)}")
                    return None, []
            else:
                try:
                    from_chat = await self.client.get_entity(self.thread.from_chat)
                except Exception as e:
                    self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Не удалось найти исходный чат: {str(e)}")
                    return None, []
        if not message_ids and self.thread.message_ids:
            for mid in self.thread.message_ids:
                match = re.match(message_link_pattern, mid)
                if match:
                    _, msg_id = match.groups()
                    message_ids.append(int(msg_id))
                    continue
                if mid.strip().isdigit():
                    message_ids.append(int(mid.strip()))
                else:
                    match = re.search(r'/(\d+)$', mid)
                    if match:
                        message_ids.append(int(match.group(1)))
        if not message_ids:
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Не указаны корректные ID сообщений")
            return None, []
        return from_chat, message_ids
class UsersMode(BaseMailingMode):
    async def execute(self, *args, **kwargs):
        if not self.thread.user_list:
            self.thread.log_signal.emit("❌ Список пользователей пуст")
            return

        self.total_targets = len(self.thread.user_list)
        self.processed_targets = 0
        self.update_progress()
        if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
            self.thread.window.update_mailing_stats('total_targets', self.total_targets)
        for username in self.thread.user_list:
            if self.thread.is_stopped:
                break
            try:
                if isinstance(username, str) and username.startswith('id') and username[2:].isdigit():
                    entity_id = int(username[2:])
                    entity = await self.client.get_entity(entity_id)
                else:
                    entity = await self.client.get_entity(username)
                if not isinstance(entity, User) or entity.bot or getattr(entity, 'deleted', False):
                    self.thread.log_signal.emit(f"⚠️ {os.path.basename(self.thread.session_file)} | Пропущен {username}: не является пользователем")
                    continue
                if self.thread.add_to_contacts:
                    contact_added = await self._check_and_add_contact(entity, username)
                    if not contact_added:
                        continue
                if await self.send_message(entity, self.thread.message, self.thread.media_path):
                    self.processed_targets += 1
                    self.update_progress()
            except Exception as e:
                await self.handle_error(username, e)
    async def _check_and_add_contact(self, user, username: str, *args, **kwargs) -> bool:
        try:
            contacts = await self.client(GetContactsRequest(hash=0))
            contact_ids = {contact.id for contact in contacts.users}

            if user.id not in contact_ids:
                if self.thread.add_to_contacts:
                    await self._add_to_contacts(user)
                    await self.thread.apply_delay()
                    self.thread.log_signal.emit(f"✅ {os.path.basename(self.thread.session_file)} | {username} добавлен в контакты")
                else:
                    self.thread.log_signal.emit(f"⚠️ {os.path.basename(self.thread.session_file)} | {username} отсутствует в контактах")
                    return False
            return True
        except Exception as e:
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Ошибка проверки контакта {username}: {str(e)}")
            return False
    async def _add_to_contacts(self, user, *args, **kwargs) -> None:
        try:
            await self.client(AddContactRequest(
                id=user,
                first_name=user.first_name or "Unknown",
                last_name=user.last_name or "",
                phone=user.phone or ""
            ))
        except Exception as e:
            user_name = getattr(user, 'username', str(user.id))
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Ошибка добавления контакта {user_name}: {str(e)}")
class DialogsMode(BaseMailingMode):
    async def execute(self, *args, **kwargs):
        try:
            dialogs = await self.client.get_dialogs()
            valid_users = [d for d in dialogs if isinstance(d.entity, User) and not d.entity.bot and not getattr(d.entity, 'deleted', False)]

            if not valid_users:
                self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Нет доступных пользователей")
                return
            self.total_targets = len(valid_users)
            self.processed_targets = 0
            self.update_progress()
            if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                self.thread.window.update_mailing_stats('total_targets', self.total_targets)
            for dialog in valid_users:
                if self.thread.is_stopped:
                    break
                if await self.send_message(dialog.entity, self.thread.message, self.thread.media_path):
                    self.processed_targets += 1
                    self.update_progress()
        except Exception as e:
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Ошибка при получении списка диалогов: {str(e)}")
class MassMode(BaseMailingMode):
    async def execute(self, *args, **kwargs):
        try:
            if not self.thread.groups_list:
                self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Список групп/ботов пуст")
                return
            self.total_targets = len(self.thread.groups_list)
            self.processed_targets = 0
            self.update_progress()
            if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                self.thread.window.update_mailing_stats('total_targets', self.total_targets)
            for group_username in self.thread.groups_list:
                if self.thread.is_stopped:
                    break
                try:
                    entity = await self.client.get_entity(group_username)

                    if await self.send_message(entity, self.thread.message, self.thread.media_path):
                        self.processed_targets += 1
                        self.update_progress()
                    else:
                        self.processed_targets += 1
                        self.update_progress()
                except Exception as e:
                    self.thread.log_signal.emit(f"❌ Ошибка при отправке в {group_username}: {e}")
                    self.processed_targets += 1
                    self.update_progress()
        except Exception as e:
            self.thread.log_signal.emit(f"❌ {os.path.basename(self.thread.session_file)} | Ошибка при обработке списка групп: {str(e)}")
class MailingThread(BaseThread):
    flood_wait_signal = pyqtSignal(str, int)
    emergency_stop_signal = pyqtSignal()
    delay_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    done_signal = pyqtSignal()
    flood_wait_count = 0
    MAX_FLOOD_WAIT_ERRORS = 10
    all_wait_limits_count = 0
    MAX_ALL_WAIT_LIMITS = 15
    def __init__(self, session_file: str, session_folder: str, mode: str, message: str,
                silent: bool, add_to_contacts: bool, use_proxy: bool, user_list: Optional[List[str]] = None,
                media_path: Optional[str] = None, from_chat: Optional[str] = None,
                message_ids: Optional[List[str]] = None, forward_to_users: bool = False,
                forward_to_chats: bool = False, verify_contacts: bool = False,
                groups_list: Optional[List[str]] = None, randomize_text: bool = False, parent=None, proxy=None):
        super().__init__(session_file=session_file, parent=parent)
        self.session_file = session_file
        self.session_folder = session_folder
        self.mode = mode
        self.message = message
        self.silent = silent
        self.add_to_contacts = add_to_contacts
        self.use_proxy = use_proxy
        self.user_list = user_list
        self.media_path = media_path
        self.from_chat = from_chat
        self.message_ids = message_ids
        self.forward_to_users = forward_to_users
        self.forward_to_chats = forward_to_chats
        self.verify_contacts = verify_contacts
        self.groups_list = groups_list
        self.randomize_text = randomize_text
        self.proxy = proxy
        if parent:
            min_delay = int(getattr(parent, 'min_delay', 0) or 0)
            max_delay = int(getattr(parent, 'max_delay', 0) or 0)
            self.set_delay_range(min_delay, max_delay)
    @classmethod
    def reset_limits_counter(cls):
        cls.flood_wait_count = 0
        cls.all_wait_limits_count = 0
    async def apply_delay(self, *args, **kwargs) -> None:
        await super().apply_delay()
    async def process(self, *args, **kwargs):
        if not self.running:
            self.log_signal.emit(f"Сессия {self.session_file} остановлена")
            self.progress_signal.emit(1, "Завершена")
            return
        connection = TelegramConnection(self.session_folder)
        try:
            connected, me = await connection.connect(self.session_file, self.use_proxy, proxy=self.proxy)
            if not connected or not me:
                if hasattr(self, 'window') and hasattr(self.window, 'update_mailing_stats'):
                    self.window.update_mailing_stats('unauthorized')
                self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Сессия не авторизована")
                self.progress_signal.emit(1, "Завершена")
                return
            connection.log_signal.connect(self.log_signal)
            self.client = connection.client
            spam_blocked, spam_block_end_date = await connection.check_spam_block()
            if spam_blocked:
                if spam_block_end_date:
                    self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Обнаружен спам блок до {spam_block_end_date}")
                else:
                    self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Обнаружен спам блок")
                if hasattr(self, 'window') and hasattr(self.window, 'update_mailing_stats'):
                    self.window.update_mailing_stats('spam_blocked')
            await connection.update_session_info(
                self.session_file,
                me,
                spam_blocked=spam_blocked,
                spam_block_end_date=spam_block_end_date
            )
            mailing_mode = self.get_mailing_mode()
            result = await mailing_mode.initialize(self.client)
            if not result:
                self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Не удалось инициализировать режим рассылки")
                self.progress_signal.emit(1, "Завершена")
                return
            if self.verify_contacts and self.user_list and (self.mode == "users" or (self.mode == "forward" and self.forward_to_users)):
                verified_users = await mailing_mode.verify_user_contacts(self.user_list)
                if not verified_users and not self.add_to_contacts:
                    self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Нет доступных контактов для рассылки")
                    self.progress_signal.emit(1, "Завершена")
                    return
                self.user_list = verified_users
            await mailing_mode.execute()
        except Exception as e:
            error_text = str(e).lower()
            if hasattr(self, 'window') and hasattr(self.window, 'update_mailing_stats'):
                if "auth" in error_text or "unauthorized" in error_text or "session" in error_text:
                    self.window.update_mailing_stats('unauthorized')
                elif "spam" in error_text:
                    self.window.update_mailing_stats('spam_blocked')
            self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Ошибка: {str(e)}")
            if hasattr(self, 'window') and hasattr(self.window, 'show_error_dialog'):
                self.window.show_error_dialog(str(e))
        finally:
            if hasattr(self, 'client') and self.client:
                await connection.disconnect()
            self.progress_signal.emit(100, "Завершена")
            self.done_signal.emit()
    def get_mailing_mode(self, *args, **kwargs) -> BaseMailingMode:
        if self.mode == "forward":
            return ForwardMode(self)
        elif self.mode == "users":
            return UsersMode(self)
        elif self.mode == "dialogs":
            return DialogsMode(self)
        else:
            return MassMode(self)
    def emit_progress(self, value: int, status: str, *args, **kwargs):
        super().emit_progress(value, status)
    def stop(self, *args, **kwargs):
        super().stop()
    @classmethod
    def handle_flood_wait(cls, session_file: str, wait_time: int) -> bool:
        cls.flood_wait_count += 1
        if wait_time > 3600:
            return True
        if cls.flood_wait_count >= cls.MAX_FLOOD_WAIT_ERRORS:
            return True
        return False
    def _randomize_message(self, text: str) -> str:
        if not self.randomize_text:
            return text
        def replace_random(match):
            options = match.group(1).split('|')
            return random.choice(options)
        return re.sub(r'\{([^}]+)\}', replace_random, text)
    async def send_message(self, entity, message, media_path=None, *args, **kwargs):
        if self.thread.is_stopped:
            return False
        try:
            entity_name = getattr(entity, 'username', None) or getattr(entity, 'title', None) or str(entity.id)
            if self.randomize_text:
                message = self._randomize_message(message)
            if media_path:
                await self.client.send_file(entity, media_path, caption=message, silent=self.thread.silent)
            else:
                await self.client.send_message(entity, message, silent=self.thread.silent)
            if hasattr(self.thread, 'window') and hasattr(self.thread.window, 'update_mailing_stats'):
                self.thread.window.update_mailing_stats('sent_success')
            self.thread.log_signal.emit(f"✅ {os.path.basename(self.thread.session_file)} отправила сообщение {entity_name}")
            await self.thread.apply_delay()
            return True
        except Exception as e:
            await self.handle_error(entity_name, e)
            return False
class MailingWindow(QWidget, ThreadStopMixin):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    flood_wait_signal = pyqtSignal(str, int)
    emergency_stop_signal = pyqtSignal()
    def __init__(self, session_folder: str, main_window=None, *args):
        super().__init__(main_window, *args)
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.main_window = main_window
        self.user_list = None
        self.message = None
        self.media_path = None
        self.session_progress = {}
        self.session_stats = {}
        self.config = load_config()
        self.mailing_stats = {
            'total_targets': 0,
            'sent_success': 0,
            'sent_failed': 0,
            'no_permissions': 0,
            'spam_blocked': 0,
            'unauthorized': 0,
            'emergency_stop': False
        }
        self.report_shown = False
        self.new_distribution_active = False
        self.distributed_user_list = {}
        self.distributed_groups_list = {}
        self.total_threads = 0
        self.completed_threads = 0
        self.stopped = False
        self.setup_ui()
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
    def emit_log(self, message, *args, **kwargs):
        self.log_signal.emit(message)
    def emit_progress(self, value, status, *args, **kwargs):
        self.progress_signal.emit(value, status)
    def emit_flood_wait(self, session_file, wait_time, *args, **kwargs):
        self.log_area.append(f"⚠️ {os.path.basename(session_file)} | Ограничение скорости: ожидание {wait_time} сек.")
    def emit_emergency_stop(self, *args, **kwargs):
        self.emergency_stop_signal.emit()
    def get_common_styles(self, *args, **kwargs) -> dict:
        return {}
    def setup_ui(self, *args):
        styles = self.get_common_styles()
        self.setWindowTitle("Рассылка сообщений")
        main_layout = QVBoxLayout(self)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_layout.setContentsMargins(0, 0, 0, 0)
        proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси")
        proxy_layout.addWidget(self.use_proxy_checkbox)
        self.use_proxy_txt_checkbox = QCheckBox("Использовать прокси из txt-файла")
        proxy_layout.addWidget(self.use_proxy_txt_checkbox)
        proxy_layout.addStretch()
        left_layout.addLayout(proxy_layout)
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup()
        self.user_mode = QRadioButton("▶ По пользователям")
        self.mass_mode = QRadioButton("▶ По чатам")
        self.forward_mode = QRadioButton("▶ Пересылка")
        self.user_mode.setChecked(True)
        for btn in [self.user_mode, self.mass_mode, self.forward_mode]:
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        left_layout.addLayout(mode_layout)
        self.distribute_tasks_checkbox = QCheckBox("Распределить задачи между сессиями (новый)")
        self.distribute_tasks_checkbox.toggled.connect(self.on_distribute_tasks_toggled)
        left_layout.addWidget(self.distribute_tasks_checkbox)
        forward_layout = QHBoxLayout()
        self.from_chat_input = QLineEdit()
        self.from_chat_input.setPlaceholderText("ID чата/канала (@name или -100...)")
        self.from_chat_input.hide()
        forward_layout.addWidget(self.from_chat_input)
        self.message_ids_input = QLineEdit()
        self.message_ids_input.setPlaceholderText("ID сообщения (t.me/c/...)")
        self.message_ids_input.hide()
        forward_layout.addWidget(self.message_ids_input)
        left_layout.addLayout(forward_layout)
        forward_targets_layout = QHBoxLayout()
        self.forward_to_users_checkbox = QRadioButton("👤 Пользователям")
        self.forward_to_users_checkbox.setChecked(True)
        self.forward_to_users_checkbox.hide()
        self.forward_to_users_checkbox.toggled.connect(self.on_forward_target_changed)
        forward_targets_layout.addWidget(self.forward_to_users_checkbox)
        self.forward_to_chats_checkbox = QRadioButton("👥 В чаты")
        self.forward_to_chats_checkbox.hide()
        self.forward_to_chats_checkbox.toggled.connect(self.on_forward_target_changed)
        forward_targets_layout.addWidget(self.forward_to_chats_checkbox)
        left_layout.addLayout(forward_targets_layout)
        settings_layout = QHBoxLayout()
        left_settings = QVBoxLayout()
        options_layout = QHBoxLayout()
        self.silent_checkbox = QCheckBox("🔕 Без звука")
        options_layout.addWidget(self.silent_checkbox)
        self.verify_contacts_checkbox = QCheckBox("Проверить контакты")
        options_layout.addWidget(self.verify_contacts_checkbox)
        left_settings.addLayout(options_layout)
        settings_layout.addLayout(left_settings)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("⏱"))
        delay_layout.addWidget(QLabel("Мин:"))
        self.min_delay_input = QLineEdit()
        self.min_delay_input.setValidator(QIntValidator(0, 3600))
        self.min_delay_input.setMaximumWidth(50)
        self.min_delay_input.setPlaceholderText("0")
        self.min_delay_input.setText("0")
        delay_layout.addWidget(self.min_delay_input)
        delay_layout.addWidget(QLabel("Макс:"))
        self.max_delay_input = QLineEdit()
        self.max_delay_input.setValidator(QIntValidator(0, 3600))
        self.max_delay_input.setMaximumWidth(50)
        self.max_delay_input.setPlaceholderText("0")
        self.max_delay_input.setText("0")
        delay_layout.addWidget(self.max_delay_input)
        delay_layout.addWidget(QLabel("сек"))
        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)
        left_layout.addLayout(settings_layout)
        self.load_groups_button = QPushButton("📂 Загрузить список групп/ботов")
        self.load_groups_button.clicked.connect(self.load_groups_list)
        self.load_groups_button.setVisible(False)
        left_layout.addWidget(self.load_groups_button)
        self.load_users_button = QPushButton("📂 Загрузить список пользователей")
        self.load_users_button.clicked.connect(self.load_user_list)
        left_layout.addWidget(self.load_users_button)
        button_layout = QHBoxLayout()
        self.message_button = QPushButton("✏️ Сообщение")
        self.message_button.clicked.connect(self.show_message_dialog)
        button_layout.addWidget(self.message_button)
        self.start_button = QPushButton("▶ Начать")
        self.start_button.clicked.connect(self.on_start_button_clicked)
        button_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("⏹ Стоп")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_mailing)
        button_layout.addWidget(self.stop_button)
        left_layout.addLayout(button_layout)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(200)
        left_layout.addWidget(self.log_area)
        status_layout = QVBoxLayout()
        self.current_delay_label = QLabel("⏱ Текущая задержка: 0 сек.")
        status_layout.addWidget(self.current_delay_label)
        self.progress_widget = ProgressWidget(self)
        status_layout.addWidget(self.progress_widget)
        left_layout.addLayout(status_layout)
        main_splitter.addWidget(left_groupbox)
        self.session_window = SessionWindow(self.session_folder, self)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        main_splitter.addWidget(self.session_window)
        main_splitter.setSizes([750, 250])
    def on_mode_changed(self, button, *args, **kwargs):
        is_forward = button == self.forward_mode
        is_mass = button == self.mass_mode
        self.from_chat_input.setVisible(is_forward)
        self.message_ids_input.setVisible(is_forward)
        self.forward_to_users_checkbox.setVisible(is_forward)
        self.forward_to_chats_checkbox.setVisible(is_forward)
        self.message_button.setVisible(not is_forward)
        self.load_groups_button.setVisible(is_mass or (is_forward and self.forward_to_chats_checkbox.isChecked()))
        self.load_users_button.setVisible(not is_mass and (not is_forward or (is_forward and self.forward_to_users_checkbox.isChecked())))
    def on_forward_target_changed(self, checked, *args, **kwargs):
        if self.sender() == self.forward_to_users_checkbox:
            if checked:
                self.load_users_button.setVisible(True)
                self.load_groups_button.setVisible(False)
        elif self.sender() == self.forward_to_chats_checkbox:
            if checked:
                self.load_users_button.setVisible(False)
                self.load_groups_button.setVisible(True)
    def on_start_button_clicked(self, *args, **kwargs):
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну сессию")
            return
        if self.forward_mode.isChecked():
            if not self.from_chat_input.text() or not self.message_ids_input.text():
                QMessageBox.warning(self, "Ошибка", "Укажите чат-источник и ID сообщений")
                return
            if not self.forward_to_users_checkbox.isChecked() and not self.forward_to_chats_checkbox.isChecked():
                QMessageBox.warning(self, "Ошибка", "Выберите цель для пересылки")
                return
            if self.forward_to_users_checkbox.isChecked() and not self.user_list:
                QMessageBox.warning(self, "Ошибка", "Загрузите список пользователей")
                return
            if self.forward_to_chats_checkbox.isChecked() and not hasattr(self, 'groups_list'):
                QMessageBox.warning(self, "Ошибка", "Загрузите список групп/ботов")
                return
        elif self.mass_mode.isChecked():
            if not self.message:
                QMessageBox.warning(self, "Ошибка", "Введите сообщение")
                return
            if not hasattr(self, 'groups_list'):
                QMessageBox.warning(self, "Ошибка", "Загрузите список групп/ботов")
                return
        else:
            if not self.message:
                QMessageBox.warning(self, "Ошибка", "Введите сообщение")
                return
            if not self.user_list:
                QMessageBox.warning(self, "Ошибка", "Загрузите список пользователей")
                return
        self.start_button.setEnabled(False)
        self.start_mailing(selected_sessions)
    def on_sessions_updated(self, valid_sessions, *args):
        if not valid_sessions:
            self.start_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)
            self.available_sessions = valid_sessions
    def load_user_list(self, *args, **kwargs):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл со списком пользователей",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if not file_path:
                        return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                users = []
                for line in f:
                    username = line.strip()
                    if username:
                        users.append(username)
            if not users:
                QMessageBox.warning(self, "Ошибка", "Файл пуст")
                return
            self.user_list = users
            self.log_area.append(f"✅ Загружено пользователей: {len(users)}")
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            self.log_area.append(f"❌ Ошибка загрузки списка: {str(e)}")
            QApplication.processEvents()
    def show_message_dialog(self, *args, **kwargs):
        dialog = MessageEditorDialog(self)
        if self.message:
            dialog.message_input.setPlainText(self.message)
        if self.media_path:
            dialog.load_media(self.media_path)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.message, self.media_path, self.randomize_text = dialog.get_message()
            self.log_area.append("✅ Сообщение сохранено")
    def on_use_proxy_txt_toggled(self, checked, *args):
        if checked:
            file_path, _ = QFileDialog.getOpenFileName(self, "Выберите txt-файл с прокси", "", "Text Files (*.txt)")
            if file_path:
                self.proxy_txt_path = file_path
                self.proxies_list = parse_proxies_from_txt(file_path)
                self.log_area.append(f"✅ Загружено прокси из файла: {len(self.proxies_list)}")
            else:
                self.use_proxy_txt_checkbox.setChecked(False)
        else:
            self.proxy_txt_path = None
            self.proxies_list = []
    def start_mailing(self, selected_sessions, *args, **kwargs):
        self.report_shown = False
        self.stopped = False
        if not selected_sessions:
            return
        self.log_area.clear()
        MailingThread.reset_limits_counter()
        use_proxy = self.use_proxy_checkbox.isChecked()
        use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
        proxies = self.proxies_list if use_proxy_txt and self.proxies_list else []
        config = None
        if use_proxy:
            config = load_config()
        threads = []
        self.total_threads = len(selected_sessions)
        self.completed_threads = 0
        self.active_sessions = set()
        self.session_progress.clear()
        self.session_stats.clear()
        self.reset_mailing_stats()
        self.new_distribution_active = self.distribute_tasks_checkbox.isChecked()
        self.distributed_user_list = {}
        self.distributed_groups_list = {}
        current_mode = self.get_current_mode()
        if self.new_distribution_active:
            distributor.set_sessions(selected_sessions)
            if current_mode == "users" and self.user_list:
                distributor.set_items(self.user_list, TaskType.MAILING)
                self.log_area.append("INFO: Новое распределение: пользователи разделены между сессиями.")
            elif current_mode == "mass" and hasattr(self, 'groups_list') and self.groups_list:
                distributor.set_items(self.groups_list, TaskType.MAILING)
                self.log_area.append("INFO: Новое распределение: группы разделены между сессиями.")
            elif current_mode == "forward":
                if self.forward_to_users_checkbox.isChecked() and self.user_list:
                    distributor.set_items(self.user_list, TaskType.MAILING)
                    self.log_area.append("INFO: Новое распределение (пересылка): пользователи разделены.")
                elif self.forward_to_chats_checkbox.isChecked() and hasattr(self, 'groups_list') and self.groups_list:
                    distributor.set_items(self.groups_list, TaskType.MAILING)
                    self.log_area.append("INFO: Новое распределение (пересылка): чаты разделены.")
        self.progress_widget.update_progress(0, f"Выполняется задача для {self.total_threads} сессий...")
        try:
            self.min_delay = int(self.min_delay_input.text() or 0)
            self.max_delay = int(self.max_delay_input.text() or 0)
        except ValueError:
            self.min_delay = 0
            self.max_delay = 0
        for idx, session_file in enumerate(selected_sessions):
            proxy = None
            if use_proxy_txt and proxies:
                proxy = load_proxy_from_list(idx, proxies)
                if proxy:
                    self.log_area.append(f"🌐 [{session_file}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}")
            elif use_proxy:
                proxy = load_proxy(config)
                if proxy:
                    self.log_area.append(f"🌐 [{session_file}] Используется прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.log_area.append(f"ℹ️ [{session_file}] Прокси не используется")
            current_user_list = self.user_list
            current_groups_list = self.groups_list if hasattr(self, 'groups_list') else None
            if self.new_distribution_active:
                if current_mode == "users":
                    current_user_list = distributor.get_session_items(session_file)
                    self.log_area.append(f"DEBUG: Сессия {session_file} (users mode) получила {len(current_user_list)} элементов от нового распределителя.")
                elif current_mode == "mass":
                    current_groups_list = distributor.get_session_items(session_file)
                    self.log_area.append(f"DEBUG: Сессия {session_file} (mass mode) получила {len(current_groups_list)} элементов от нового распределителя.")
                elif current_mode == "forward":
                    if self.forward_to_users_checkbox.isChecked():
                        current_user_list = distributor.get_session_items(session_file)
                        self.log_area.append(f"DEBUG: Сессия {session_file} (forward to users) получила {len(current_user_list)} элементов от нового распределителя.")
                    elif self.forward_to_chats_checkbox.isChecked():
                        current_groups_list = distributor.get_session_items(session_file)
                        self.log_area.append(f"DEBUG: Сессия {session_file} (forward to chats) получила {len(current_groups_list)} элементов от нового распределителя.")
            thread = MailingThread(
                session_file=session_file,
                session_folder=self.session_window.session_folder,
                mode=self.get_current_mode(),
                message=self.message,
                silent=self.silent_checkbox.isChecked(),
                add_to_contacts=self.verify_contacts_checkbox.isChecked(),
                use_proxy=bool(proxy),
                user_list=current_user_list,
                media_path=self.media_path,
                from_chat=self.from_chat_input.text() if self.forward_mode.isChecked() else None,
                message_ids=self.message_ids_input.text().split(',') if self.forward_mode.isChecked() and self.message_ids_input.text() else None,
                forward_to_users=self.forward_to_users_checkbox.isChecked() if self.forward_mode.isChecked() else False,
                forward_to_chats=self.forward_to_chats_checkbox.isChecked() if self.forward_mode.isChecked() else False,
                verify_contacts=self.verify_contacts_checkbox.isChecked(),
                groups_list=current_groups_list,
                randomize_text=getattr(self, 'randomize_text', False),
                parent=self,
                proxy=proxy
            )
            thread.window = self
            thread.log_signal.connect(self.log_area.append)
            thread.progress_signal.connect(self.update_thread_progress)
            thread.flood_wait_signal.connect(self.emit_flood_wait)
            thread.emergency_stop_signal.connect(self.stop_mailing)
            thread.done_signal.connect(lambda: self._on_thread_finished(thread))
            thread.delay_signal.connect(self.update_delay_label)
            thread.set_delay_range(self.min_delay, self.max_delay)
            threads.append(thread)
        if self.min_delay > 0 and self.max_delay > 0:
            self.start_threads_with_delay(threads, self.min_delay, self.max_delay)
        else:
            for thread in threads:
                self.thread_manager.start_thread(thread)
    def stop_mailing(self, *args, **kwargs):
        self.stopped = True
        self.stop_all_operations()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.log_area.append("Процесс остановлен.")
        self.progress_widget.update_progress(100, "Процесс остановлен")
        self.user_list = None
        self.groups_list = None
        self.total_threads = 0
        self.completed_threads = 0
    def _on_thread_finished(self, thread, *args, **kwargs):
        if not hasattr(self, '_already_done'):
            self._already_done = set()
        if thread.session_file in self._already_done:
            return
        self._already_done.add(thread.session_file)
        self.completed_threads += 1
        percent = int((self.completed_threads / self.total_threads) * 100) if self.total_threads else 100
        self.progress_widget.update_progress(percent, f"Выполнено {self.completed_threads} из {self.total_threads} потоков")
        if self.completed_threads >= self.total_threads:
            self.log_area.append("✅ Все задачи завершены.")
            self.progress_widget.update_progress(100, "Задача завершена.")
            report = self.generate_mailing_report()
            self.log_area.append(report)
            self.log_area.append("✅ Рассылка завершена")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(True)
    def get_current_mode(self, *args, **kwargs) -> str:
        if self.forward_mode.isChecked():
            return "forward"
        elif self.mass_mode.isChecked():
            return "mass"
        else:
            return "users"
    def update_thread_progress(self, value: int, status: str, *args, **kwargs):
        session_name = self.sender().session_file if hasattr(self.sender(), 'session_file') else 'Unknown'
        self.session_progress[session_name] = value
        total_progress = 0
        active_sessions = 0
        for session, progress in self.session_progress.items():
            total_progress += progress
            active_sessions += 1 if progress < 100 else 0
        if self.total_threads > 0:
            average_progress = int(total_progress / len(self.session_progress)) if len(self.session_progress) > 0 else 0
            status_text = f"Выполнено {len(self.session_progress) - active_sessions}/{self.total_threads} сессий ({average_progress}%)"
            self.progress_widget.update_progress(average_progress, status_text)
            try:
                min_delay = int(self.min_delay_input.text() or 0)
                max_delay = int(self.max_delay_input.text() or 0)
                current_delay = int(average_progress * (max_delay - min_delay) / 100 + min_delay)
                self.current_delay_label.setText(f"Текущая задержка: {current_delay} сек.")
            except (ValueError, AttributeError):
                self.current_delay_label.setText("Текущая задержка: 0 сек.")
    def update_delay_label(self, delay, *args):
        self.current_delay_label.setText(f"Текущая задержка: {delay} сек.")
    def handle_flood_wait(self, session_file, wait_time, *args, **kwargs):
        base_name = os.path.basename(session_file)
        MailingThread.all_wait_limits_count += 1
        if MailingThread.all_wait_limits_count >= MailingThread.MAX_ALL_WAIT_LIMITS:
            self.log_area.append(f"🚫 Обнаружено {MailingThread.all_wait_limits_count} временных ограничений подряд! Аварийная остановка для защиты аккаунта.")
            self.update_mailing_stats('emergency_stop')
            self.emergency_stop_signal.emit()

            self.stop_mailing()
            return
        if MailingThread.all_wait_limits_count >= MailingThread.MAX_ALL_WAIT_LIMITS // 2:
            self.log_area.append(f"⚠️ Внимание! Уже {MailingThread.all_wait_limits_count} ограничений из {MailingThread.MAX_ALL_WAIT_LIMITS}! Близка аварийная остановка.")
        if wait_time > 3600:
            hours = wait_time // 3600
            minutes = (wait_time % 3600) // 60
            self.log_area.append(f"🚫 {base_name} | Обнаружено длительное ограничение {hours} ч. {minutes} мин. Аварийная остановка!")
            self.log_area.append(f"⚠️ Рекомендация: при таких длительных ограничениях нужно сделать перерыв на несколько часов. Аккаунт под наблюдением системы защиты Telegram.")
            self.update_mailing_stats('emergency_stop')
            self.emergency_stop_signal.emit()
            self.stop_mailing()
        else:
            if wait_time > 60:
                minutes = wait_time // 60
                seconds = wait_time % 60
                self.log_area.append(f"⏱️ {base_name} | Временное ограничение №{MailingThread.all_wait_limits_count}: {minutes} мин. {seconds} сек. Рекомендуется снизить темп отправки.")
            else:
                self.log_area.append(f"⏱️ {base_name} | Временное ограничение №{MailingThread.all_wait_limits_count}: {wait_time} сек.")
    def handle_long_wait(self, wait_minutes, entity_name=None):
        entity_info = f" для {entity_name}" if entity_name else ""
        if wait_minutes > 60:
            self.log_area.append(f"🚫 Обнаружено длительное ограничение {wait_minutes} мин{entity_info}. Аварийная остановка!")
            self.log_area.append(f"⚠️ Рекомендация: при таких длительных ограничениях нужно сделать перерыв на несколько часов. Telegram защищает аккаунты от массовой активности.")
            self.update_mailing_stats('emergency_stop')
            self.emergency_stop_signal.emit()
            self.stop_mailing()
    def update_mailing_stats(self, stat_key: str, value: int = 1, *args, **kwargs):
        if stat_key in self.mailing_stats:
            if stat_key == 'emergency_stop':
                self.mailing_stats[stat_key] = True
            else:
                self.mailing_stats[stat_key] += value
    def reset_mailing_stats(self, *args, **kwargs):
        self.mailing_stats = {
            'total_targets': 0,
            'sent_success': 0,
            'sent_failed': 0,
            'no_permissions': 0,
            'spam_blocked': 0,
            'unauthorized': 0,
            'emergency_stop': False
        }
    def generate_mailing_report(self, *args, **kwargs):
        report = "\n📊 ИТОГОВЫЙ ОТЧЕТ РАССЫЛКИ:\n"
        report += f"├─ Всего целей: {self.mailing_stats['total_targets']}\n"
        report += f"├─ Успешно отправлено: {self.mailing_stats['sent_success']}\n"
        report += f"├─ Не отправлено: {self.mailing_stats['sent_failed']}\n"
        report += f"├─ Не отправлено из-за отсутствия прав: {self.mailing_stats['no_permissions']}\n"
        report += f"├─ Сессий в спам-блоке: {self.mailing_stats['spam_blocked']}\n"
        report += f"├─ Неавторизованных сессий: {self.mailing_stats['unauthorized']}\n"
        report += f"└─ Аварийная остановка: {'Да' if self.mailing_stats['emergency_stop'] else 'Нет'}"
        return report
    def parse_group_link(self, link_text):
        link_text = link_text.strip()
        if 'joinchat/' in link_text or link_text.startswith('+') or 't.me/+' in link_text:
            return BaseMailingMode.normalize_joinchat_link(link_text)
        if link_text.startswith('http://t.me/') or link_text.startswith('https://t.me/'):
            username = link_text.split('t.me/', 1)[1]
            return f"@{username}" if not username.startswith('@') else username
        elif link_text.startswith('t.me/'):
            username = link_text[5:]
            return f"@{username}" if not username.startswith('@') else username
        if link_text.startswith('@'):
            return link_text
        else:
            if '/' not in link_text and '.' not in link_text:
                return '@' + link_text
            else:
                return link_text
    def load_groups_list(self, *args, **kwargs):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл со списком групп/ботов",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                groups = []
                for line in f:
                    group_link = line.strip()
                    if group_link:
                        normalized_link = self.parse_group_link(group_link)
                        groups.append(normalized_link)
            if not groups:
                QMessageBox.warning(self, "Ошибка", "Файл пуст")
                return
            self.groups_list = groups
            self.log_area.append(f"✅ Загружено групп/ботов: {len(groups)}")
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            self.log_area.append(f"❌ Ошибка загрузки списка: {str(e)}")
            QApplication.processEvents()
    def on_distribute_tasks_toggled(self, checked):
        self.new_distribution_active = checked
        if hasattr(self, 'session_window'):
            selected_sessions = self.session_window.get_selected_sessions()
            self.start_button.setEnabled(bool(selected_sessions))
    def show_error_dialog(self, error_message, *args):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(None, error_text=error_message))

