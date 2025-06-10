import os, logging, asyncio, random, re
from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QCheckBox, QSizePolicy, QGroupBox
)
from telethon import TelegramClient
from telethon.tl.functions.messages import SendReactionRequest, ReadHistoryRequest
from telethon.tl.types import Channel, Chat, User, ReactionEmoji
from ui.okak import ErrorReportDialog
from ui.loader import load_config, load_proxy
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection, TelegramCustomError
)
from datetime import datetime
from typing import List, Optional, Dict, Any
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
from ui.thread_base import ThreadStopMixin, BaseThread
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
def extract_username(value):
    if isinstance(value, str):
        m = re.search(r"t\.me/(?:s/)?([^/?]+)", value)
        return m.group(1) if m else value
    return value
def validate_peer(entity, check_access_hash=True):
    if isinstance(entity, (Channel, Chat)):
        return True
    if isinstance(entity, User) and not entity.bot and not getattr(entity, 'deleted', False):
        return True
    if check_access_hash:
        return hasattr(entity, 'access_hash') and entity.access_hash is not None
    return False
class SessionCheckThread(BaseThread):
    session_finished_signal = pyqtSignal(object)
    def __init__(self, parent, session_path: str, proxy: Optional[Dict] = None):
        super().__init__(session_file=session_path, parent=parent)
        self.session_path = session_path
        self.session_file = os.path.basename(session_path)
        self.proxy = proxy
        self.session_folder = os.path.dirname(session_path)
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.log_signal.emit)
        self.connection.error_signal.connect(self.error_signal.emit)
        self.connection.progress_signal.connect(self.progress_signal.emit)
    async def process(self, *args, **kwargs):
        try:
            success, me = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy), proxy=self.proxy)
            if not success or not me:
                return
            spam_blocked, spam_block_end_date = await self.connection.check_spam_block()
            is_premium, premium_expires = await self.connection.check_premium()
            status_parts = []
            status_parts.append(f"✅ {os.path.basename(self.session_file)}")
            status_parts.append(f"{me.first_name or ''} {me.last_name or ''}")
            status_parts.append(me.phone or 'Номер не указан')
            if is_premium:
                if premium_expires:
                    expires_date = datetime.fromtimestamp(premium_expires)
                    status_parts.append(f"Premium до {expires_date.strftime('%d.%m.%Y')}")
                else:
                    status_parts.append("Premium бессрочно")
            if spam_blocked:
                if spam_block_end_date:
                    status_parts.append(f"Спамблок до {spam_block_end_date}")
                else:
                    status_parts.append("Спамблок есть")
            else:
                status_parts.append("Спамблока нет")
            self.log_signal.emit(" | ".join(status_parts))
            await self.connection.update_session_info(
                self.session_path,
                me,
                spam_blocked=spam_blocked,
                spam_block_end_date=spam_block_end_date
            )
            if self.connection.client and self.running:
                await self.perform_human_actions(self.connection.client)
        except TelegramCustomError:
            pass
        finally:
            if self.connection:
                await self.connection.disconnect()
            self.session_finished_signal.emit(self)
    async def perform_human_actions(self, client: TelegramClient, *args, **kwargs):
        try:
            dialogs = await client.get_dialogs()
            chats = [d for d in dialogs if validate_peer(getattr(d, 'entity', d))]
            if not chats:
                return
            actions = [
                self._simulate_reading_messages,
                self._add_reactions,
                self._scroll_history,
                self._fake_typing,
            ]
            random.shuffle(actions)
            chosen_actions = random.sample(actions, random.randint(2, 4))
            for _ in range(random.randint(2, 5)):
                if not self.running:
                    return
                chat = random.choice(chats)
                for action in chosen_actions:
                    try:
                        await action(client, chat)
                    except Exception:
                        pass
                    await asyncio.sleep(random.uniform(0.2, 0.7))
        except Exception:
            pass
    async def _fake_typing(self, client: TelegramClient, chat, *args, **kwargs):
        try:
            entity = chat.entity if hasattr(chat, 'entity') else chat
            if not validate_peer(entity, check_access_hash=False):
                return
            await client.send_message(entity, " ", typing=True)
            await asyncio.sleep(random.uniform(0.2, 0.7))
        except Exception:
            pass
    async def _simulate_reading_messages(self, client: TelegramClient, chat, *args, **kwargs):
        try:
            entity = chat.entity if hasattr(chat, 'entity') else chat
            if not validate_peer(entity):
                return
            offset_ids = [random.randint(100, 5000) for _ in range(random.randint(1, 2))]
            for offset_id in offset_ids:
                await client.get_messages(entity, limit=1, offset_id=offset_id)
                await asyncio.sleep(random.uniform(0.2, 0.7))
            await client(ReadHistoryRequest(peer=entity, max_id=0))
        except Exception:
            return
    async def _scroll_history(self, client: TelegramClient, chat, *args, **kwargs):
        try:
            entity = chat.entity if hasattr(chat, 'entity') else chat
            if not validate_peer(entity, check_access_hash=False):
                return
            for _ in range(random.randint(1, 2)):
                offset_id = random.randint(50, 5000)
                await client.get_messages(entity, limit=random.randint(1, 3), offset_id=offset_id)
                await asyncio.sleep(random.uniform(0.2, 0.7))
        except Exception:
            return
    async def _add_reactions(self, client: TelegramClient, chat, *args, **kwargs):
        try:
            entity = chat.entity if hasattr(chat, 'entity') else chat
            if not validate_peer(entity):
                return
            messages = await client.get_messages(entity, limit=1)
            if messages:
                message = messages[0]
                me = await client.get_me()
                if message.from_id and getattr(message.from_id, 'user_id', None) == me.id:
                    return
                reaction_list = ['👍', '❤️', '🔥', '👏', '😁', '🤩']
                chosen_reaction = random.choice(reaction_list)
                try:
                    await client(SendReactionRequest(
                        peer=entity,
                        msg_id=message.id,
                        reaction=[ReactionEmoji(emoticon=chosen_reaction)],
                        big=False
                    ))
                except Exception:
                    return
                await asyncio.sleep(random.uniform(0.2, 0.7))
        except Exception:
            return
class ComponentsWindow(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, *args):
        super().__init__(*args)
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.session_window = SessionWindow(session_folder, self)
        if args and hasattr(args[0], 'config_changed'):
            self.main_window = args[0]
            self.main_window.config_changed.connect(self.session_window.on_config_changed)
        self.setWindowTitle("Check Sessions")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QHBoxLayout(self)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси", self)
        self.use_proxy_txt_checkbox = QCheckBox("Использовать прокси из txt-файла", self)
        proxy_layout.addWidget(self.use_proxy_checkbox)
        proxy_layout.addWidget(self.use_proxy_txt_checkbox)
        left_layout.addLayout(proxy_layout)
        self.label = QLabel("Проверка сессий", self)
        left_layout.addWidget(self.label)
        control_layout = QHBoxLayout()
        self.button = QPushButton("▶ Начать проверку", self)
        self.stop_button = QPushButton("⏹ Остановить проверку", self)
        self.button.clicked.connect(self.start_session)
        self.stop_button.clicked.connect(self.stop_session)
        control_layout.addWidget(self.button)
        control_layout.addWidget(self.stop_button)
        left_layout.addLayout(control_layout)
        self.log_output = QTextEdit(self)
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output)
        self.progress_widget = ProgressWidget(self)
        left_layout.addWidget(self.progress_widget)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)       
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(self.session_window, 1) 
        self.total_sessions = 0
        self.completed_threads = 0
        self.running = False
        self.proxies_list = []
        self.proxy_txt_path = None
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
    def log_message(self, message: str, *args, **kwargs):
        self.log_output.append(message)
        self.log_output.ensureCursorVisible()
    def on_use_proxy_txt_toggled(self, checked: bool, *args, **kwargs):
        if checked:
            from PyQt6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(self, "Выберите txt-файл с прокси", "", "Text Files (*.txt)")
            if file_path:
                self.proxy_txt_path = file_path
                self.proxies_list = parse_proxies_from_txt(file_path)
                self.log_message(f"✅ Загружено прокси из файла: {len(self.proxies_list)}")
            else:
                self.use_proxy_txt_checkbox.setChecked(False)
        else:
            self.proxy_txt_path = None
            self.proxies_list = []
    def start_session(self, *args, **kwargs):
        try:
            selected_sessions = self.session_window.get_selected_sessions()
            if not selected_sessions:
                self.log_message("⛔ Не выбрано ни одной сессии")
                return
            self.log_output.clear()
            self.log_message("✅ Начинаем проверку сессий...")
            self.button.setEnabled(False)
            use_proxy = self.use_proxy_checkbox.isChecked()
            use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
            threads = []
            self.completed_threads = 0
            self.total_sessions = len(selected_sessions)
            for idx, session_file in enumerate(selected_sessions):
                session_path = os.path.join(self.session_window.session_folder, session_file)
                proxy = None
                if use_proxy_txt and self.proxies_list:
                    proxy = load_proxy_from_list(idx, self.proxies_list)
                    if proxy:
                        self.log_message(f"🌐 [{session_file}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}")
                elif use_proxy:
                    config = load_config()
                    proxy = load_proxy(config)
                    if proxy:
                        self.log_message(f"🌐 [{session_file}] Используется прокси: {proxy.get('addr', 'не указан')}")
                else:
                    self.log_message(f"ℹ️ [{session_file}] Прокси не используется")
                thread = SessionCheckThread(self, session_path, proxy)
                thread.log_signal.connect(self.log_message)
                thread.error_signal.connect(self.show_error_dialog)
                thread.progress_signal.connect(self.update_session_progress)
                thread.session_finished_signal.connect(self.on_session_finished)
                threads.append(thread)
            for thread in threads:
                self.thread_manager.start_thread(thread)
            self.running = True
            self.label.setText("INFO: Проверка сессий в процессе...")
            self.progress_widget.update_progress(0, f"Выполняется проверка {self.total_sessions} сессий...")
        except Exception as e:
            logger.error(f"Error in start_session: {str(e)}")
            raise
    def update_session_progress(self, value: int, status_text: str, *args, **kwargs):
        sender = self.sender()
        if sender:
            sender.last_progress = value
        self.update_overall_progress(status_text)
    def update_overall_progress(self, status_text: Optional[str] = None, *args, **kwargs):
        total_progress = 0
        running_threads = 0
        for thread in self.thread_manager.threads:
            if hasattr(thread, 'last_progress'):
                total_progress += thread.last_progress
                running_threads += 1
        if self.total_sessions > 0:
            completed_percentage = (self.completed_threads * 100) / self.total_sessions
            progress_percentage = 0
            if running_threads > 0:
                remaining_threads = len(self.thread_manager.threads) - self.completed_threads
                if remaining_threads > 0 and remaining_threads * 100 > 0:
                    progress_percentage = (total_progress / (remaining_threads * 100)) * ((remaining_threads * 100) / self.total_sessions)
            total_percentage = int(completed_percentage + progress_percentage)
            if total_percentage > 100:
                total_percentage = 100
            self.progress_widget.update_progress(
                total_percentage,
                status_text or f"Выполнено {self.completed_threads} из {self.total_sessions} сессий"
            )
            if (self.completed_threads == self.total_sessions or not self.running) and self.running:
                self.label.setText("SUCCESS: Проверка сессий завершена! Результаты в логах.")
                self.button.setEnabled(True)
                self.running = False
    def on_session_finished(self, thread: SessionCheckThread):
        self.completed_threads += 1
        self.update_overall_progress()
        if self.completed_threads >= self.total_sessions:
            self.label.setText("INFO: Проверка завершена.")
            self.progress_widget.update_progress(100, "Проверка завершена.")
            self.button.setEnabled(True)
            self.running = False
    def stop_session(self, *args, **kwargs):
        self.stop_all_operations()
        self.label.setText("INFO: Проверка остановлена.")
        self.progress_widget.update_progress(0, "Проверка остановлена.")
        self.button.setEnabled(True)
        self.completed_threads = 0
        self.total_sessions = 0
        self.running = False
    def show_error_dialog(self, error_message: str, *args, **kwargs):
        ErrorReportDialog.send_error_report(None, error_text=error_message)
    def on_sessions_updated(self, valid_sessions: List[str]):
        self.button.setEnabled(bool(valid_sessions))
class ErrorDialogEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, error_message: str):
        super().__init__(self.EVENT_TYPE)
        self.error_message = error_message
