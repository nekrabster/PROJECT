import os
import asyncio
import re
from random import randint
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum, auto
from dataclasses import dataclass
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFileDialog, QCheckBox, QGroupBox,
    QHBoxLayout, QMessageBox, QLineEdit, QTextEdit, QLabel, QRadioButton,
    QButtonGroup, QSplitter, QApplication, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator
from telethon.tl.types import Chat, Channel, User
from telethon.tl.functions.channels import GetParticipantsRequest, JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest, ImportChatInviteRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError
from ui.loader import load_config, load_proxy
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection )
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.mate import distributor, TaskType
DEFAULT_MAX_FLOOD_WAIT = 10
DEFAULT_MIN_DELAY = 1
DEFAULT_MAX_DELAY = 5
class ParserMode(Enum):
    INTERNAL_CHATS = auto()
    EXTERNAL_LINKS = auto()
@dataclass
class ParserConfig:
    mode: ParserMode
    use_proxy: bool = False
    min_delay: Optional[int] = None
    max_delay: Optional[int] = None
    group_links: Optional[List[str]] = None
    save_to_file: bool = True
    check_subscription: bool = True

    filter_by_last_seen: bool = False
    last_seen_days: int = 7
    filter_by_gender: bool = False
    gender_male: bool = True
    gender_female: bool = True
    filter_by_avatar: bool = False
    has_avatar: bool = True
    filter_by_premium: bool = False
    has_premium: bool = True
    export_to_excel: bool = False
    separate_source_files: bool = False
    distribute_accounts: bool = False
@dataclass
class UserData:
    id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    last_seen: Optional[datetime]
    has_avatar: bool
    has_premium: bool
    source: str
class SubscriberThread(BaseThread):
    flood_wait_signal = pyqtSignal(str, int)
    emergency_stop_signal = pyqtSignal()
    users_found_signal = pyqtSignal(int)
    flood_wait_count = 0
    MAX_FLOOD_WAIT_ERRORS = 10
    all_wait_limits_count = 0
    MAX_ALL_WAIT_LIMITS = 15
    def __init__(self, session_file: str, session_folder: str, mode: ParserMode,
                 use_proxy: bool, group_links: Optional[List[str]] = None,
                 check_subscription: bool = True,
                 filter_config: Optional[dict] = None,
                 parent=None, proxy=None):
        super().__init__(session_file=session_file, parent=parent)
        self.session_folder = session_folder
        self.mode = mode
        self.use_proxy = use_proxy
        self.proxy = proxy
        self.group_links = group_links or []
        self.check_subscription = check_subscription
        self.filter_config = filter_config or {}
        self.collected_users = set()
        self.user_data = []
        self.connection = TelegramConnection(self.session_folder)
        self.client = None
    @classmethod
    def reset_limits_counter(cls):
        cls.flood_wait_count = 0
        cls.all_wait_limits_count = 0
    async def process(self, *args, **kwargs):
        if not self.running:
            self.log_signal.emit(f"Сессия {self.session_file} остановлена")
            return
        try:
            connected, me = await self.connection.connect(self.session_file, self.use_proxy, proxy=self.proxy)
            if not connected or not me:
                if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                    self.window.update_parser_stats('unauthorized')
                self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Сессия не авторизована")
                return
            self.connection.log_signal.connect(self.log_signal.emit)
            self.client = self.connection.client
            spam_blocked, spam_block_end_date = await self.connection.check_spam_block()
            if spam_blocked:
                end_date_str = f" до {spam_block_end_date}" if spam_block_end_date else ""
                self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Обнаружен спам блок{end_date_str}")
                if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                    self.window.update_parser_stats('spam_blocked')
            await self.connection.update_session_info(
                self.session_file, me,
                spam_blocked=spam_blocked,
                spam_block_end_date=spam_block_end_date
            )
            total_users = 0
            if self.mode == ParserMode.INTERNAL_CHATS:
                total_users = await self.parse_internal_chats()
            elif self.mode == ParserMode.EXTERNAL_LINKS:
                total_users = await self.parse_external_links()
            self.log_signal.emit(f"✅ {os.path.basename(self.session_file)} | Собрано пользователей: {total_users}")
        except Exception as e:
            error_text = str(e).lower()
            if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                if "auth" in error_text or "unauthorized" in error_text or "session" in error_text:
                    self.window.update_parser_stats('unauthorized')
                elif "spam" in error_text:
                    self.window.update_parser_stats('spam_blocked')
            self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Ошибка: {str(e)}")
        finally:
            if self.client:
                await self.connection.disconnect()
            self.users_found_signal.emit(len(self.collected_users))
    async def parse_internal_chats(self, *args, **kwargs) -> int:
        self.log_signal.emit(f"🔄 {os.path.basename(self.session_file)} | Получение списка диалогов...")
        try:
            dialogs = await self.client.get_dialogs()
            groups_and_channels = [d for d in dialogs if isinstance(d.entity, (Channel, Chat))]
            if not groups_and_channels:
                self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Нет доступных групп или каналов")
                return 0
            self.log_signal.emit(f"ℹ️ {os.path.basename(self.session_file)} | Найдено {len(groups_and_channels)} групп/каналов")
            total_chats = len(groups_and_channels)
            processed_chats = 0
            total_users = 0
            for dialog in groups_and_channels:
                if self.is_stopped:
                    break
                chat_title = dialog.name if hasattr(dialog, 'name') else getattr(dialog.entity, 'title', 'Неизвестный чат')
                try:
                    users = await self.get_chat_members(dialog.entity)
                    for user in users:
                        if not user.bot and not getattr(user, 'deleted', False):
                            if user.username:
                                self.collected_users.add(user.username)
                            else:
                                self.collected_users.add(f"id{user.id}")
                    processed_chats += 1
                    total_users += len(users)
                    progress = int((processed_chats / total_chats) * 100)
                    self.progress_signal.emit(progress, f"Обработано {processed_chats}/{total_chats} чатов")
                    self.log_signal.emit(f"✅ {os.path.basename(self.session_file)} | Собрано {len(users)} пользователей из {chat_title}")
                except Exception as e:
                    error_text = str(e)
                    if 'Chat admin privileges are required' in error_text:
                        self.log_signal.emit(f"⛔ {os.path.basename(self.session_file)} | Нет прав администратора для получения участников. Добавьте аккаунт в администраторы группы/канала.")
                        if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                            self.window.update_parser_stats('no_permissions')
                    else:
                        self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при получении участников: {error_text}")
                    processed_chats += 1
            return total_users
        except Exception as e:
            self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Ошибка при получении диалогов: {str(e)}")
            return 0
    async def parse_external_links(self, *args, **kwargs) -> int:
        if not self.group_links:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Список ссылок на группы пуст")
            return 0
        total_chats = len(self.group_links)
        processed_chats = 0
        total_users = 0
        for link in self.group_links:
            if self.is_stopped:
                break
            try:
                entity = await self.get_entity_from_link(link)
                if not entity:
                    self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Не удалось получить сущность по ссылке {link}")
                    processed_chats += 1
                    continue
                chat_title = getattr(entity, 'title', 'Неизвестный чат')
                if self.check_subscription:
                    is_subscribed = await self.check_subscription_status(entity)
                    if not is_subscribed:
                        self.log_signal.emit(f"ℹ️ {os.path.basename(self.session_file)} | Не подписан на {chat_title}, требуется подписка")
                        try:
                            await self.client(JoinChannelRequest(entity))
                            self.log_signal.emit(f"✅ {os.path.basename(self.session_file)} | Успешно подписался на {chat_title}")
                        except Exception as e:
                            self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Ошибка при подписке на {chat_title}: {str(e)}")
                            processed_chats += 1
                            continue
                users = await self.get_chat_members(entity)
                for user in users:
                    if not user.bot and not getattr(user, 'deleted', False):
                        if user.username:
                            self.collected_users.add(user.username)
                        else:
                            self.collected_users.add(f"id{user.id}")
                processed_chats += 1
                total_users += len(users)
                progress = int((processed_chats / total_chats) * 100)
                self.progress_signal.emit(progress, f"Обработано {processed_chats}/{total_chats} чатов")
                self.log_signal.emit(f"✅ {os.path.basename(self.session_file)} | Собрано {len(users)} пользователей из {chat_title}")
            except Exception as e:
                self.log_signal.emit(f"❌ {os.path.basename(self.session_file)} | Ошибка при обработке ссылки {link}: {str(e)}")
                processed_chats += 1
        return total_users
    async def get_entity_from_link(self, link, *args, **kwargs):
        try:
            if 'joinchat' in link or '+' in link:
                if 'joinchat/' in link:
                    invite_hash = link.split('joinchat/')[1]
                elif 't.me/+' in link:
                    invite_hash = link.split('t.me/+')[1]
                elif link.startswith('+'):
                    invite_hash = link[1:]
                else:
                    invite_hash = link
                try:
                    updates = await self.client(ImportChatInviteRequest(invite_hash))
                    return updates.chats[0]
                except Exception as e:
                    self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при присоединении к приватной группе: {str(e)}")
                    return None
            else:
                username = link.replace('https://t.me/', '').replace('t.me/', '')
                if username.startswith('@'):
                    username = username[1:]
                return await self.client.get_entity(username)
        except Exception as e:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при получении сущности: {str(e)}")
            return None
    async def check_subscription_status(self, entity, *args, **kwargs) -> bool:
        try:
            if isinstance(entity, Channel):
                full_channel = await self.client(GetFullChannelRequest(entity))
                return not getattr(full_channel.full_chat, 'can_view_participants', False)
            elif isinstance(entity, Chat):
                full_chat = await self.client(GetFullChatRequest(entity.id))
                return True
            return False
        except Exception as e:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при проверке подписки: {str(e)}")
            return False
    async def get_chat_members(self, entity, *args, **kwargs) -> List[User]:
        users = []
        source_name = getattr(entity, 'title', 'Неизвестный чат')
        try:
            if isinstance(entity, Channel):
                participants = []
                offset = 0
                limit = 100
                while True:
                    if self.is_stopped:
                        break
                    try:
                        chunk = await self.client(GetParticipantsRequest(
                            channel=entity,
                            filter=ChannelParticipantsSearch(''),
                            offset=offset,
                            limit=limit,
                            hash=0
                        ))
                        if not chunk.users:
                            break
                        participants.extend(chunk.users)
                        offset += len(chunk.users)
                        if len(chunk.users) < limit:
                            break
                    except Exception as e:
                        error_text = str(e)
                        if 'Chat admin privileges are required' in error_text:
                            self.log_signal.emit(f"⛔ {os.path.basename(self.session_file)} | Нет прав администратора для получения участников. Добавьте аккаунт в администраторы группы/канала.")
                            if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                                self.window.update_parser_stats('no_permissions')
                        else:
                            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при получении участников: {error_text}")
                        break
                filtered_participants = []
                for user in participants:
                    if await self.apply_user_filters(user):
                        filtered_participants.append(user)
                        if user.username:
                            self.collected_users.add(user.username)
                        else:
                            self.collected_users.add(f"id{user.id}")
                        await self.save_user_data(user, source_name)
                users = filtered_participants
            elif isinstance(entity, Chat):
                full = await self.client(GetFullChatRequest(entity.id))
                all_users = await self.client.get_users(user.user_id for user in full.full_chat.participants.participants)
                filtered_users = []
                for user in all_users:
                    if await self.apply_user_filters(user):
                        filtered_users.append(user)
                        if user.username:
                            self.collected_users.add(user.username)
                        else:
                            self.collected_users.add(f"id{user.id}")
                        await self.save_user_data(user, source_name)
                users = filtered_users
        except ChatAdminRequiredError:
            self.log_signal.emit(f"⛔ {os.path.basename(self.session_file)} | Нет прав администратора для получения участников. Добавьте аккаунт в администраторы группы/канала.")
            if hasattr(self, 'window') and hasattr(self.window, 'update_parser_stats'):
                self.window.update_parser_stats('no_permissions')
        except ChannelPrivateError:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка доступа: приватный канал")
        except Exception as e:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при получении участников: {str(e)}")
        return users
    async def apply_user_filters(self, user, *args, **kwargs) -> bool:
        if not self.filter_config:
            return True
        if getattr(user, 'bot', False) or getattr(user, 'deleted', False):
            return False
        if self.filter_config.get('filter_by_last_seen', False):
            if not hasattr(user, 'status'):
                try:
                    full_user = await self.client.get_entity(user.id)
                    user.status = getattr(full_user, 'status', None)
                except:
                    user.status = None
            if hasattr(user, 'status'):
                status = user.status
                if not status:
                    return False
                max_days = self.filter_config.get('last_seen_days', 7)
                if hasattr(status, 'was_online'):
                    last_seen = status.was_online
                    days_ago = (datetime.now() - last_seen).days
                    if days_ago > max_days:
                        return False
                else:
                    return False
        if self.filter_config.get('filter_by_avatar', False):
            has_avatar_required = self.filter_config.get('has_avatar', True)
            try:
                profile_photos = await self.client.get_profile_photos(user)
                has_avatar = len(profile_photos) > 0
                if has_avatar_required != has_avatar:
                    return False
            except:
                if has_avatar_required:
                    return False
        if self.filter_config.get('filter_by_premium', False):
            has_premium_required = self.filter_config.get('has_premium', True)
            if hasattr(user, 'premium') and user.premium != has_premium_required:
                return False
        return True
    async def save_user_data(self, user, source: str, *args, **kwargs):
        try:
            phone = getattr(user, 'phone', None)
            last_seen = None
            if hasattr(user, 'status') and hasattr(user.status, 'was_online'):
                last_seen = user.status.was_online
            has_avatar = False
            try:
                profile_photos = await self.client.get_profile_photos(user)
                has_avatar = len(profile_photos) > 0
            except:
                pass
            has_premium = getattr(user, 'premium', False)
            gender = 'Неизвестно'
            user_data = UserData(
                id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=phone,
                gender=gender,
                last_seen=last_seen,
                has_avatar=has_avatar,
                has_premium=has_premium,
                source=source
            )
            self.user_data.append(user_data)
        except Exception as e:
            self.log_signal.emit(f"⚠️ {os.path.basename(self.session_file)} | Ошибка при сохранении данных о пользователе: {str(e)}")
class SubscriberWindow(QWidget, ThreadStopMixin):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    flood_wait_signal = pyqtSignal(str, int)
    emergency_stop_signal = pyqtSignal()
    def __init__(self, session_folder: str, main_window=None, *args, **kwargs):
        super().__init__(main_window, *args)
        self.session_folder = session_folder
        self.main_window = main_window
        self.group_links = None
        self.parser_threads = []
        self.session_progress = {}
        self.session_stats = {}
        self.total_sessions = 0
        self.active_sessions = set()
        self.created_threads = 0
        self.total_planned_threads = 0
        self.config = load_config()
        self.collected_users = set()
        self.report_shown = False
        self.parser_stats = {
            'total_groups': 0,
            'processed_groups': 0,
            'users_found': 0,
            'failed_groups': 0,
            'no_permissions': 0,
            'spam_blocked': 0,
            'unauthorized': 0,
            'emergency_stop': False
        }
        self.setup_ui()
        ThreadStopMixin.__init__(self)
    def setup_ui(self, *args):
        styles = self.get_common_styles()
        self.setWindowTitle("Парсер аудитории")
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
        self.internal_mode = QRadioButton("▶ Из чатов сессии")
        self.external_mode = QRadioButton("▶ По ссылкам")
        self.internal_mode.setChecked(True)
        for btn in [self.internal_mode, self.external_mode]:
            self.mode_group.addButton(btn)
            mode_layout.addWidget(btn)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        left_layout.addLayout(mode_layout)
        self.distribute_tasks_checkbox = QCheckBox("Распределить задачи между сессиями (новый)")
        left_layout.addWidget(self.distribute_tasks_checkbox)
        settings_layout = QHBoxLayout()
        left_settings = QVBoxLayout()
        options_layout = QHBoxLayout()
        self.check_subscription_checkbox = QCheckBox("Проверять подписку")
        self.check_subscription_checkbox.setChecked(True)
        options_layout.addWidget(self.check_subscription_checkbox)
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
        self.advanced_settings_checkbox = QCheckBox("🔧 Расширенные настройки")
        self.advanced_settings_checkbox.toggled.connect(self.toggle_advanced_settings)
        left_layout.addWidget(self.advanced_settings_checkbox)
        self.advanced_settings_group = QGroupBox()
        self.advanced_settings_layout = QVBoxLayout(self.advanced_settings_group)
        self.advanced_settings_layout.setContentsMargins(5, 5, 5, 5)
        self.advanced_settings_layout.setSpacing(5)
        filters_group = QGroupBox("📋 Фильтры")
        filters_layout = QVBoxLayout(filters_group)
        filters_layout.setContentsMargins(5, 5, 5, 5)
        filters_layout.setSpacing(5)
        last_seen_layout = QHBoxLayout()
        last_seen_layout.setContentsMargins(0, 0, 0, 0)
        last_seen_layout.setSpacing(5)
        self.filter_last_seen_checkbox = QCheckBox("⏰ Был онлайн за")
        last_seen_layout.addWidget(self.filter_last_seen_checkbox)
        self.last_seen_days_spinbox = QSpinBox()
        self.last_seen_days_spinbox.setMinimum(1)
        self.last_seen_days_spinbox.setMaximum(365)
        self.last_seen_days_spinbox.setValue(7)
        self.last_seen_days_spinbox.setMaximumWidth(60)
        last_seen_layout.addWidget(self.last_seen_days_spinbox)
        last_seen_layout.addWidget(QLabel("дней"))
        last_seen_layout.addStretch()
        filters_layout.addLayout(last_seen_layout)
        gender_layout = QHBoxLayout()
        gender_layout.setContentsMargins(0, 0, 0, 0)
        gender_layout.setSpacing(5)
        gender_layout.addWidget(QLabel("👥 Пол:"))
        self.gender_male_checkbox = QCheckBox("Мужской")
        self.gender_male_checkbox.setChecked(True)
        gender_layout.addWidget(self.gender_male_checkbox)
        self.gender_female_checkbox = QCheckBox("Женский")
        self.gender_female_checkbox.setChecked(True)
        gender_layout.addWidget(self.gender_female_checkbox)
        gender_layout.addStretch()
        filters_layout.addLayout(gender_layout)
        additional_filters_layout = QHBoxLayout()
        additional_filters_layout.setContentsMargins(0, 0, 0, 0)
        additional_filters_layout.setSpacing(5)
        self.filter_avatar_checkbox = QCheckBox("🖼 Только с аватаркой")
        additional_filters_layout.addWidget(self.filter_avatar_checkbox)
        self.filter_premium_checkbox = QCheckBox("💎 Только с премиум")
        additional_filters_layout.addWidget(self.filter_premium_checkbox)
        additional_filters_layout.addStretch()
        filters_layout.addLayout(additional_filters_layout)
        self.advanced_settings_layout.addWidget(filters_group)
        export_group = QGroupBox("💾 Экспорт")
        export_layout = QVBoxLayout(export_group)
        export_layout.setContentsMargins(5, 5, 5, 5)
        export_layout.setSpacing(5)
        export_options_layout = QHBoxLayout()
        export_options_layout.setContentsMargins(0, 0, 0, 0)
        export_options_layout.setSpacing(5)
        self.export_to_excel_checkbox = QCheckBox("📊 В Excel с расширенной информацией")
        self.export_to_excel_checkbox.setChecked(True)
        export_options_layout.addWidget(self.export_to_excel_checkbox)
        self.separate_files_checkbox = QCheckBox("📑 Отдельные файлы для источников")
        export_options_layout.addWidget(self.separate_files_checkbox)
        export_options_layout.addStretch()
        export_layout.addLayout(export_options_layout)
        self.advanced_settings_layout.addWidget(export_group)
        optimization_group = QGroupBox("⚡ Оптимизация")
        optimization_layout = QVBoxLayout(optimization_group)
        optimization_layout.setContentsMargins(5, 5, 5, 5)
        optimization_layout.setSpacing(5)
        self.distribute_accounts_checkbox = QCheckBox("♻️ Распределить аккаунты")
        optimization_layout.addWidget(self.distribute_accounts_checkbox)
        self.advanced_settings_layout.addWidget(optimization_group)
        self.advanced_settings_group.setVisible(False)
        left_layout.addWidget(self.advanced_settings_group)
        self.load_groups_button = QPushButton("📂 Загрузить список групп/каналов")
        self.load_groups_button.clicked.connect(self.load_group_links)
        self.load_groups_button.setVisible(False)
        left_layout.addWidget(self.load_groups_button)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("▶ Начать парсинг")
        self.start_button.clicked.connect(self.on_start_button_clicked)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("⏹ Стоп")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_parsing)
        button_layout.addWidget(self.stop_button)

        self.save_button = QPushButton("💾 Сохранить")
        self.save_button.clicked.connect(self.save_results)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)
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
        self.users_count_label = QLabel("👥 Собрано пользователей: 0")
        status_layout.addWidget(self.users_count_label)
        left_layout.addLayout(status_layout)
        main_splitter.addWidget(left_groupbox)
        self.session_window = SessionWindow(self.session_folder, self)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        main_splitter.addWidget(self.session_window)
        main_splitter.setSizes([750, 250])
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
    def on_mode_changed(self, button, *args, **kwargs):
        is_external = button == self.external_mode
        self.load_groups_button.setVisible(is_external)
    def on_sessions_updated(self, valid_sessions, *args):
        if not valid_sessions:
            self.start_button.setEnabled(False)
        else:
            self.start_button.setEnabled(True)
        self.available_sessions = valid_sessions
    def load_group_links(self, *args, **kwargs):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл со списком групп/каналов",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                links = []
                for line in f:
                    link = line.strip()
                    if link:
                        links.append(link)
            if not links:
                QMessageBox.warning(self, "Ошибка", "Файл пуст")
                return
            self.group_links = links
            self.log_area.append(f"✅ Загружено ссылок на группы/каналы: {len(links)}")
            QApplication.processEvents()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
            self.log_area.append(f"❌ Ошибка загрузки списка: {str(e)}")
            QApplication.processEvents()
    def on_use_proxy_txt_toggled(self, checked):
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
    def on_start_button_clicked(self, *args, **kwargs):
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одну сессию")
            return 
        if self.external_mode.isChecked() and not self.group_links:
            QMessageBox.warning(self, "Ошибка", "Загрузите список групп/каналов")
            return
        self.start_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.collected_users.clear()
        self.users_count_label.setText("Собрано пользователей: 0")
        self.start_parsing(selected_sessions)
    def start_parsing(self, selected_sessions, *args, **kwargs):
        self.report_shown = False
        if not selected_sessions:
            return
        self.log_area.clear()
        SubscriberThread.reset_limits_counter()
        use_proxy = self.use_proxy_checkbox.isChecked()
        use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
        config = None
        if use_proxy:
            config = load_config()
        proxies_list = self.proxies_list if use_proxy_txt else []
        self.total_planned_threads = len(selected_sessions)
        self.created_threads = 0
        self.active_sessions.clear()
        self.session_progress.clear()
        self.session_stats.clear()
        self.parser_threads = []
        self.collected_users.clear()
        self.new_distribution_active = False
        self.distributed_links = {}
        self.reset_parser_stats()
        self.progress_widget.update_progress(0, "Подготовка парсинга...")
        try:
            self.min_delay = int(self.min_delay_input.text() or 0)
            self.max_delay = int(self.max_delay_input.text() or 0)
        except ValueError:
            self.min_delay = 0
            self.max_delay = 0
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.log_area.append(f"✅ Начинаем парсинг для {len(selected_sessions)} сессий")
        filter_config = self.get_filter_config()
        threads = []
        for idx, session_file in enumerate(selected_sessions):
            proxy = None
            if use_proxy_txt and proxies_list:
                proxy = load_proxy_from_list(idx, proxies_list)
                if proxy:
                    self.log_area.append(f"🌐 [{session_file}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}")
            elif use_proxy:
                proxy = load_proxy(config)
                if proxy:
                    self.log_area.append(f"🌐 [{session_file}] Используется прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.log_area.append(f"ℹ️ [{session_file}] Прокси не используется")
            mode = ParserMode.EXTERNAL_LINKS if self.external_mode.isChecked() else ParserMode.INTERNAL_CHATS
            links_for_thread = self.group_links
            if mode == ParserMode.EXTERNAL_LINKS:
                if self.distribute_tasks_checkbox.isChecked() and self.group_links:
                    distributor.set_sessions(selected_sessions)
                    distributor.set_items(self.group_links, TaskType.PARSING)
                    links_for_thread = distributor.get_session_items(session_file)
                    self.log_area.append(f"DEBUG: Сессия {session_file} получила {len(links_for_thread)} ссылок от нового распределителя.")
                elif self.distributed_links.get(session_file):
                    links_for_thread = self.distributed_links.get(session_file)
                    self.log_area.append(f"DEBUG: Сессия {session_file} получила {len(links_for_thread)} ссылок от старого распределителя.")
            thread = SubscriberThread(
                session_file=session_file,
                session_folder=self.session_window.session_folder,
                mode=mode,
                use_proxy=bool(proxy),
                group_links=links_for_thread,
                check_subscription=self.check_subscription_checkbox.isChecked(),
                filter_config=filter_config,
                parent=self,
                proxy=proxy
            )
            thread.window = self
            thread.log_signal.connect(self.log_area.append)
            thread.progress_signal.connect(self.update_thread_progress)
            thread.flood_wait_signal.connect(self.emit_flood_wait)
            thread.emergency_stop_signal.connect(self.stop_parsing)
            thread.done_signal.connect(lambda: self._on_thread_finished(thread))
            thread.delay_signal.connect(self.update_current_delay)
            thread.users_found_signal.connect(self.update_users_found)
            thread.set_delay_range(self.min_delay, self.max_delay)
            threads.append(thread)
        self.parser_threads = threads
        if self.min_delay > 0 and self.max_delay > 0:
            self.start_threads_with_delay(threads, self.min_delay, self.max_delay)
        else:
            for thread in threads:
                self.thread_manager.start_thread(thread)
    def update_users_found(self, count, *args, **kwargs):
        thread = self.sender()
        if thread and hasattr(thread, 'collected_users'):
            self.collected_users.update(thread.collected_users)
        self.users_count_label.setText(f"Собрано пользователей: {len(self.collected_users)}")
        self.update_parser_stats('users_found', count)
    def _on_thread_finished(self, thread, *args, **kwargs):
        if hasattr(thread, 'collected_users'):
            self.collected_users.update(thread.collected_users)
        self.created_threads -= 1
        all_done = self.created_threads <= 0 and (not hasattr(self, 'pending_sessions') or not self.pending_sessions)
        if all_done and not self.report_shown:
            self.report_shown = True
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.save_button.setEnabled(True)
            self.progress_widget.update_progress(100, "Парсинг завершен")
            report = self.generate_parser_report()
            self.log_area.append(report)
            self.log_area.append("✅ Парсинг завершен")
            self.current_delay_label.setText("Текущая задержка: 0 сек.")
            self.save_results()
    def save_results(self, *args, **kwargs):
        try:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.basename(app_dir) == 'ui':
                app_dir = os.path.dirname(app_dir)
            file_path = os.path.join(app_dir, "users.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                for user in sorted(self.collected_users):
                    if user.startswith("id"):
                        f.write(f"{user}\n")
                    else:
                        f.write(f"@{user.lstrip('@')}\n")
            self.log_area.append(f"✅ Результаты сохранены в файл: {file_path}")
            filter_config = self.get_filter_config()
            user_data = []
            for thread in self.parser_threads:
                if hasattr(thread, 'user_data'):
                    user_data.extend(thread.user_data)
            if user_data and filter_config.get('export_to_excel', False):
                excel_path = os.path.join(app_dir, "users_data.xlsx")
                excel_data = []
                for user in user_data:
                    excel_data.append({
                        'ID': user.id,
                        'Имя': user.first_name or '',
                        'Фамилия': user.last_name or '',
                        'Юзернейм': f"@{user.username}" if user.username else '',
                        'Телефон': user.phone or 'Скрыт',
                        'Пол': user.gender or 'Неизвестно',
                        'Последний онлайн': user.last_seen.strftime("%Y-%m-%d %H:%M:%S") if user.last_seen else 'Неизвестно',
                        'Аватарка': 'Есть' if user.has_avatar else 'Нет',
                        'Премиум': 'Есть' if user.has_premium else 'Нет',
                        'Источник': user.source
                    })
                df = pd.DataFrame(excel_data)
                df.to_excel(excel_path, index=False)
                self.log_area.append(f"✅ Расширенные данные сохранены в Excel: {excel_path}")
                if filter_config.get('separate_source_files', False):
                    sources = {}
                    for user in user_data:
                        if user.source not in sources:
                            sources[user.source] = []
                        sources[user.source].append({
                            'ID': user.id,
                            'Имя': user.first_name or '',
                            'Фамилия': user.last_name or '',
                            'Юзернейм': f"@{user.username}" if user.username else '',
                            'Телефон': user.phone or 'Скрыт',
                            'Пол': user.gender or 'Неизвестно',
                            'Последний онлайн': user.last_seen.strftime("%Y-%m-%d %H:%M:%S") if user.last_seen else 'Неизвестно',
                            'Аватарка': 'Есть' if user.has_avatar else 'Нет',
                            'Премиум': 'Есть' if user.has_premium else 'Нет'
                        })
                    for source_name, source_data in sources.items():
                        safe_name = re.sub(r'[\\/*?:"<>|]', "_", source_name)
                        source_file = os.path.join(app_dir, f"users_{safe_name}.xlsx")
                        source_df = pd.DataFrame(source_data)
                        source_df.to_excel(source_file, index=False)
                        self.log_area.append(f"✅ Данные из источника '{source_name}' сохранены в: {source_file}")
            self.log_area.append(f"✅ Всего собрано пользователей: {len(self.collected_users)}")
            QMessageBox.information(
                self,
                "Парсинг завершен",
                f"Собрано {len(self.collected_users)} пользователей.\nФайл сохранен: {file_path}"
            )
        except Exception as e:
            self.log_area.append(f"❌ Ошибка при сохранении результатов: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить результаты: {str(e)}")
    def stop_parsing(self, *args, **kwargs):
        self.log_area.append("⚠️ Остановка парсинга...")
        if hasattr(self, 'pending_sessions'):
            self.pending_sessions.clear()
        self.stop_all_operations()
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(True)
        if self.collected_users:
            self.save_button.setEnabled(True)
        self.progress_widget.update_progress(100, "Парсинг остановлен")
        self.log_area.append("✅ Парсинг остановлен")
    def update_thread_progress(self, value: int, status: str, *args, **kwargs):
        session_name = self.sender().session_file if hasattr(self.sender(), 'session_file') else 'Unknown'
        self.session_progress[session_name] = value
        total_progress = 0
        active_sessions = 0
        for session, progress in self.session_progress.items():
            total_progress += progress
            active_sessions += 1 if progress < 100 else 0
        if self.total_planned_threads > 0:
            average_progress = int(total_progress / len(self.session_progress)) if len(self.session_progress) > 0 else 0
            status_text = f"Выполнено {len(self.session_progress) - active_sessions}/{self.total_planned_threads} сессий ({average_progress}%)"
            self.progress_widget.update_progress(average_progress, status_text)
            try:
                min_delay = int(self.min_delay_input.text() or 0)
                max_delay = int(self.max_delay_input.text() or 0)
                current_delay = int(average_progress * (max_delay - min_delay) / 100 + min_delay)
                self.current_delay_label.setText(f"Текущая задержка: {current_delay} сек.")
            except (ValueError, AttributeError):
                self.current_delay_label.setText("Текущая задержка: 0 сек.")
    def update_parser_stats(self, stat_key: str, value: int = 1, *args, **kwargs):
        if stat_key in self.parser_stats:
            if stat_key == 'emergency_stop':
                self.parser_stats[stat_key] = True
            else:
                self.parser_stats[stat_key] += value
    def reset_parser_stats(self, *args, **kwargs):
        self.parser_stats = {
            'total_groups': 0,
            'processed_groups': 0,
            'users_found': 0,
            'failed_groups': 0,
            'no_permissions': 0,
            'spam_blocked': 0,
            'unauthorized': 0,
            'emergency_stop': False
        }
    def generate_parser_report(self, *args, **kwargs):
        report = "\n📊 ИТОГОВЫЙ ОТЧЕТ ПАРСИНГА:\n"
        report += f"├─ Всего собрано пользователей: {len(self.collected_users)}\n"
        report += f"├─ Неавторизованных сессий: {self.parser_stats['unauthorized']}\n"
        report += f"├─ Сессий в спам-блоке: {self.parser_stats['spam_blocked']}\n"
        report += f"└─ Аварийная остановка: {'Да' if self.parser_stats['emergency_stop'] else 'Нет'}"
        return report
    def update_current_delay(self, delay):
        self.current_delay_label.setText(f"Текущая задержка: {delay} сек.")
    def toggle_advanced_settings(self, checked):
        self.advanced_settings_group.setVisible(checked)
    def get_filter_config(self):
        if not self.advanced_settings_checkbox.isChecked():
            return {'distribute_accounts': False}
        return {
            'filter_by_last_seen': self.filter_last_seen_checkbox.isChecked(),
            'last_seen_days': self.last_seen_days_spinbox.value(),
            'filter_by_gender': self.gender_male_checkbox.isChecked() != self.gender_female_checkbox.isChecked(),
            'gender_male': self.gender_male_checkbox.isChecked(),
            'gender_female': self.gender_female_checkbox.isChecked(),
            'filter_by_avatar': self.filter_avatar_checkbox.isChecked(),
            'has_avatar': True,
            'filter_by_premium': self.filter_premium_checkbox.isChecked(),
            'has_premium': True,
            'export_to_excel': self.export_to_excel_checkbox.isChecked(),
            'separate_source_files': self.separate_files_checkbox.isChecked(),
            'distribute_accounts': self.distribute_accounts_checkbox.isChecked()
        }
    def get_common_styles(self, *args, **kwargs):
        return {}
SubsWindow = SubscriberWindow
