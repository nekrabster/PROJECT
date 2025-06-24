import os, asyncio, logging
from typing import Dict, List, Optional, Tuple, Set, Any
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox,
    QCheckBox, QSizePolicy, QScrollArea, QPushButton,
    QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QObject
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from ui.thread_base import BaseThread, ThreadManager
from ui.appchuy import AiogramBotConnection
MAX_CONCURRENT_FETCHERS = 1
async def get_bot_username_placeholder_async(token: str, executor: ThreadPoolExecutor) -> str:
    await asyncio.sleep(0.05)
    return f"User_{token[-6:]}"
class ToggleSwitch(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(QSize(50, 24))
        self.setStyleSheet('''
            QPushButton {
                background-color: rgba(0, 0, 0, 0.1);
                border: none;
                border-radius: 12px;
            }
            QPushButton:checked {
                background-color: #007AFF;
            }
        ''')
    def paintEvent(self, event, *args):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor("white"), 2))
        painter.setBrush(QColor("white"))
        if self.isChecked():
            painter.drawEllipse(26, 2, 20, 20)
        else:
            painter.drawEllipse(4, 2, 20, 20)
class BotInfoFetcherThread(BaseThread):
    bot_details_fetched = pyqtSignal(str, str, str)
    fetch_error = pyqtSignal(str, str)
    def __init__(self, token: str, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.token_to_fetch = token
        self.logger.info(f"BotInfoFetcherThread создан для токена ...{token[-6:]}")
        self.bot_manager = AiogramBotConnection(token)
        self.bot_manager.log_signal.connect(lambda msg: self.logger.info(msg))
        self.bot_manager.error_signal.connect(lambda t, e: self.logger.error(f"{t}: {e.message}"))
    async def process(self, *args, **kwargs):
        token = self.token_to_fetch
        self.logger.debug(f"Поток для токена ...{token[-6:]}: process начат.")
        bot = None
        try:
            bot = await self.bot_manager.connect()
            info = await bot.get_me()
            username = info.username or "Без имени"
            bot_name_obj = await bot.get_my_name()
            bot_name = bot_name_obj.name if bot_name_obj else username
            self.logger.debug(f"Поток для токена ...{token[-6:]}: API вызовы успешны. Username: {username}, Имя: {bot_name}")
            self.bot_details_fetched.emit(token, username, bot_name)
            self.logger.info(f"Поток для токена ...{token[-6:]}: Детали получены и отправлены.")
        except Exception as e:
            error_msg = f"Ошибка получения username для токена ...{token[-6:]}: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.fetch_error.emit(token, f"Ошибка: {str(e)[:150]}")
        finally:
            if self.bot_manager:
                try:
                    await self.bot_manager.disconnect()
                    self.logger.debug(f"Aiogram session closed for token ...{token[-6:]} in finally block.")
                except Exception as e_close:
                    self.logger.error(f"Error closing aiogram session for token ...{token[-6:]}: {e_close}")
            self.logger.debug(f"Поток для токена ...{token[-6:]}: process завершен.")
class TokenLoader(QObject):
    tokens_loaded = pyqtSignal(list)    
    def __init__(self, token_folder_path: str):
        super().__init__()
        self.token_folder_path = token_folder_path
        self.logger = logging.getLogger('TokenLoader')
        self._is_running = False
        self._current_task = None        
    async def run_async(self, *args, **kwargs):
        if self._is_running:
            self.logger.info("Token loading is already in progress.")
            return
        self._is_running = True
        self.logger.info(f"Starting asynchronous token loading from: {self.token_folder_path}")       
        tokens_with_paths = []
        try:
            if os.path.exists(self.token_folder_path):
                def _scan_and_read_files():
                    _tokens_with_paths = []
                    for root, _, files in os.walk(self.token_folder_path):
                        for file in files:
                            if file.endswith('.txt'):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        for line in f:
                                            token = line.strip()
                                            if token and not token.startswith('#'):
                                                _tokens_with_paths.append((token, file_path))
                                except Exception as e:
                                    self.logger.error(f"Ошибка чтения файла {file_path}: {e}")
                    return _tokens_with_paths               
                tokens_with_paths = await asyncio.to_thread(_scan_and_read_files)
                self.logger.info(f"Successfully loaded {len(tokens_with_paths)} tokens.")
            else:
                self.logger.warning(f"Token folder does not exist: {self.token_folder_path}")           
            self.tokens_loaded.emit(tokens_with_paths)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки токенов: {e}", exc_info=True)
            self.tokens_loaded.emit([])
        finally:
            self._is_running = False
            self._current_task = None
            self.logger.info("Asynchronous token loading finished.")
    def start(self, *args, **kwargs):
        if self._is_running and self._current_task and not self._current_task.done():
            self.logger.info("TokenLoader task is already running.")
            return
        self._current_task = asyncio.create_task(self.run_async())      
    def stop(self, *args, **kwargs):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self.logger.info("Token loading task cancellation requested.")
        self._is_running = False
class BotTokenWindow(QWidget):
    tokens_updated = pyqtSignal(list)
    files_updated = pyqtSignal(list)
    bot_details_updated = pyqtSignal(str, str, str)
    def __init__(self, token_folder_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        self.token_folder_path = os.path.abspath(token_folder_path)
        self.file_token_counts: Dict[str, int] = {}
        self.token_to_file_map: Dict[str, str] = {}
        self.token_usernames: Dict[str, Optional[str]] = {}
        self.token_names: Dict[str, Optional[str]] = {}
        self.token_descriptions: Dict[str, Optional[str]] = {}       
        self.file_checkboxes: Dict[str, QCheckBox] = {}
        self.token_checkboxes: Dict[str, QCheckBox] = {}
        self._last_folder_state: Dict[str, float] = {}
        self._default_selected = True
        self.show_files_mode = True
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = True
        self._initial_load_complete = False
        self.thread_manager = ThreadManager(self)
        self.active_fetcher_threads: Dict[str, BotInfoFetcherThread] = {}
        self.tokens_to_fetch_queue: List[str] = []       
        self.token_loader = TokenLoader(self.token_folder_path)
        self.token_loader.tokens_loaded.connect(self._on_tokens_loaded)
        self.setup_ui()      
        QTimer.singleShot(0, self.start_async_tasks)
    def setup_ui(self, *args, **kwargs):
        self.setFixedWidth(270)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("QWidget { font-size: 11pt; } ")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(8)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(5, 5, 5, 5)
        toggle_layout.setSpacing(10)
        self.mode_label = QLabel("Файлы")
        font_mode = self.mode_label.font()
        font_mode.setPointSize(12)
        font_mode.setBold(True)
        self.mode_label.setFont(font_mode)
        self.mode_label.setToolTip("Переключить режим отображения: Файлы/Токены")
        self.mode_toggle = ToggleSwitch()
        self.mode_toggle.setChecked(True)
        self.mode_toggle.setToolTip("Переключить режим отображения")
        self.mode_toggle.clicked.connect(self.on_display_mode_changed)
        toggle_layout.addWidget(self.mode_label)
        toggle_layout.addWidget(self.mode_toggle)
        toggle_layout.addStretch()
        self.main_layout.addLayout(toggle_layout)
        self.select_all_checkbox = QCheckBox("Выбрать все")
        font_select_all = self.select_all_checkbox.font()
        font_select_all.setPointSize(11)
        font_select_all.setBold(True)
        self.select_all_checkbox.setFont(font_select_all)
        self.select_all_checkbox.setToolTip("Выбрать или снять выделение со всех элементов")
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        self.main_layout.addWidget(self.select_all_checkbox)
        self.token_groupbox = QGroupBox("Выберите файлы с токенами")
        font_groupbox = self.token_groupbox.font()
        font_groupbox.setPointSize(12)
        font_groupbox.setBold(True)
        self.token_groupbox.setFont(font_groupbox)
        self.token_groupbox.setStyleSheet("QGroupBox { margin-top: 12px; padding: 8px 0 0 0; font-weight: bold; border: 1px solid #ccc; border-radius: 8px; } ")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('''
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        ''')
        container = QWidget()
        self.items_layout = QVBoxLayout(container)
        self.items_layout.setSpacing(8)
        self.items_layout.setContentsMargins(8, 8, 8, 8)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        self.token_groupbox.setLayout(QVBoxLayout())
        self.token_groupbox.layout().addWidget(scroll)
        self.main_layout.addWidget(self.token_groupbox)
    def start_async_tasks(self, *args, **kwargs):
        self.logger.info("start_async_tasks: Initializing asynchronous operations.")
        try:
            if not self._is_running:
                self.logger.warning("start_async_tasks: Not running, aborting.")
                return

            if self._monitor_task is None or self._monitor_task.done():
                self.logger.info("start_async_tasks: Creating monitor_folder_changes task.")
                self._monitor_task = asyncio.create_task(self.monitor_folder_changes())
            else:
                self.logger.info("start_async_tasks: monitor_folder_changes task already running or scheduled.")

            self.logger.info("start_async_tasks: Creating load_tokens_async task.")
            asyncio.create_task(self.load_tokens_async())
            
        except Exception as e:
            self.logger.error(f"Ошибка в start_async_tasks: {e}", exc_info=True)
    @lru_cache(maxsize=256)
    def _read_tokens_from_file_cached(self, file_path: str, *args, **kwargs) -> List[str]:
        tokens = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    token = line.strip()
                    if token and not token.startswith('#'):
                        tokens.append(token)
        except Exception as e:
            self.logger.error(f"Ошибка чтения файла с токенами {file_path}: {e}")
        return tokens
    def _scan_token_folder_sync(self, *args, **kwargs) -> List[str]:
        current_files = []
        try:
            for root, _, files in os.walk(self.token_folder_path):
                for file in files:
                    if file.endswith('.txt'):
                        current_files.append(os.path.join(root, file))
        except Exception as e:
            self.logger.error(f"Ошибка сканирования папки с токенами: {e}")
        return current_files
    async def load_tokens_async(self, *args, **kwargs):
        if not self._is_running:
            return
        self.logger.info("Запуск асинхронной загрузки токенов...")
        self.token_loader.start()
    def _on_tokens_loaded(self, tokens_with_paths: List[Tuple[str, str]], *args, **kwargs):
        try:
            self.token_to_file_map.clear()
            self.file_token_counts.clear()            
            all_tokens_list = []
            for token, file_path in tokens_with_paths:
                self.token_to_file_map[token] = file_path
                self.file_token_counts[file_path] = self.file_token_counts.get(file_path, 0) + 1
                all_tokens_list.append(token)            
            if not self._initial_load_complete:
                self._initial_load_complete = True                
            if self._is_running:
                QTimer.singleShot(0, self.update_tokens_list)
            self.files_updated.emit(list(self.file_token_counts.keys())) 
            self._fetch_bot_info_for_tokens(all_tokens_list)
        except Exception as e:
            self.logger.error(f"Ошибка обработки загруженных токенов: {e}")
    def _fetch_bot_info_for_tokens(self, tokens: List[str], *args, **kwargs):
        self.logger.info(f"Adding {len(tokens)} tokens to fetch queue.")
        self.tokens_to_fetch_queue.clear()
        for token in tokens:
            if token not in self.active_fetcher_threads:
                self.tokens_to_fetch_queue.append(token)
            else:
                self.logger.debug(f"Token {token[-6:]} is already being fetched, skipping add to queue.")
        self.logger.debug(f"Token fetch queue size: {len(self.tokens_to_fetch_queue)} tokens.")
        asyncio.create_task(self._launch_fetcher_tasks_from_queue_async()) 
    async def _launch_fetcher_tasks_from_queue_async(self, *args, **kwargs):
        self.thread_manager.clear_completed()
        can_launch_count = MAX_CONCURRENT_FETCHERS - len(self.active_fetcher_threads)
        self.logger.debug(f"Async Can launch {can_launch_count} new fetchers. Queue size: {len(self.tokens_to_fetch_queue)}.")        
        for _ in range(can_launch_count):
            if not self.tokens_to_fetch_queue:
                self.logger.debug("Async Token fetch queue is empty. No more fetchers to launch now.")
                break
            token = self.tokens_to_fetch_queue.pop(0)
            if token in self.active_fetcher_threads: 
                self.logger.warning(f"Async Token {token[-6:]} somehow in queue but also active, skipping launch.")
                continue            
            await asyncio.sleep(0.05)
            self.logger.info(f"Async Launching fetcher for token ...{token[-6:]}")            
            fetcher_thread = BotInfoFetcherThread(token, parent=self)
            fetcher_thread.bot_details_fetched.connect(self._handle_bot_details_fetched)
            fetcher_thread.fetch_error.connect(self._handle_bot_fetch_error)
            fetcher_thread.done_signal.connect(lambda t=token: self._on_fetcher_thread_completed(t))
            
            if self.thread_manager.start_thread(fetcher_thread):
                self.active_fetcher_threads[token] = fetcher_thread
            else:
                self.logger.error(f"Async Failed to start fetcher thread for token ...{token[-6:]}. Re-queuing.")
                self.tokens_to_fetch_queue.insert(0, token) 
    def _handle_bot_details_fetched(self, token: str, username: str, bot_name: str, *args, **kwargs):
        self.logger.info(f"Данные для токена ...{token[-6:]} получены: @{username}, Имя: {bot_name}")
        self.token_usernames[token] = username
        self.token_names[token] = bot_name
        self.bot_details_updated.emit(token, username, bot_name)
        QTimer.singleShot(0, lambda: self.update_tokens_list(refresh_ui_for_token=token))
    def _handle_bot_fetch_error(self, token: str, error_message: str, *args, **kwargs):
        self.logger.warning(f"Ошибка получения данных для токена ...{token[-6:]}: {error_message}")
        display_error = f"Ошибка: {token[:5]}..." if "Ошибка запуска потока" not in error_message else error_message
        self.token_usernames[token] = display_error
        self.token_names[token] = "Ошибка"
        self.bot_details_updated.emit(token, display_error, "Ошибка")
        if self._is_running:
            QTimer.singleShot(0, lambda: self.update_tokens_list(refresh_ui_for_token=token))
    def _on_fetcher_thread_completed(self, token: str, *args, **kwargs):
        self.logger.debug(f"Поток для получения информации о токене ...{token[-6:]} завершен.")
        if token in self.active_fetcher_threads:
            del self.active_fetcher_threads[token]
        asyncio.create_task(self._launch_fetcher_tasks_from_queue_async())
    async def monitor_folder_changes(self, *args, **kwargs):
        self.logger.info(f"Мониторинг папки: {self.token_folder_path}")
        while self._is_running:
            try:
                current_state_from_thread = {}   
                def scan_folder_sync_operations():
                    _current_state_locally = {}
                    _changed_locally = False
                    if not os.path.exists(self.token_folder_path):
                        if self._last_folder_state:
                            self.logger.warning(f"Папка с токенами {self.token_folder_path} не найдена (поток мониторинга).")
                            self._last_folder_state.clear() 
                            self.file_token_counts.clear()
                            self.token_to_file_map.clear()
                            self.token_usernames.clear()
                            self.token_names.clear()
                            self.token_descriptions.clear()
                            QTimer.singleShot(0, self.update_tokens_list)
                        return False, {}
                    for root, _, files in os.walk(self.token_folder_path):
                        for file_name in files:
                            if file_name.endswith('.txt'):
                                file_path = os.path.join(root, file_name)
                                try:
                                    mtime = os.path.getmtime(file_path)
                                    _current_state_locally[file_path] = mtime
                                    if self._last_folder_state.get(file_path) != mtime:
                                        _changed_locally = True
                                        self._read_tokens_from_file_cached.cache_clear()
                                except FileNotFoundError:
                                    if file_path in self._last_folder_state:
                                         _changed_locally = True
                                    continue     
                    if not _changed_locally:
                        if len(self._last_folder_state) != len(_current_state_locally):
                             _changed_locally = True                    
                    return _changed_locally, _current_state_locally
                if not os.path.exists(self.token_folder_path):
                    if self._last_folder_state:
                        self.logger.warning(f"Папка с токенами {self.token_folder_path} не найдена.")
                        self._last_folder_state.clear()
                        self.file_token_counts.clear()
                        self.token_to_file_map.clear()
                        self.token_usernames.clear()
                        self.token_names.clear()
                        self.token_descriptions.clear()
                        QTimer.singleShot(0, self.update_tokens_list)
                    await asyncio.sleep(5)
                    continue
                changed, current_state_from_thread = await asyncio.to_thread(scan_folder_sync_operations)
                if changed is False and not os.path.exists(self.token_folder_path):
                     await asyncio.sleep(5)
                     continue
                if changed:
                    self.logger.info("Обнаружены изменения в папке, обновление списка токенов...")
                    self._last_folder_state = current_state_from_thread.copy()
                    self.logger.debug("Полная перезагрузка токенов из-за изменений в файлах.")
                    await self.load_tokens_async()
                else:
                    if self._initial_load_complete:
                        await asyncio.sleep(1)                        
                        tokens_to_refetch = []
                        for token_str in list(self.token_to_file_map.keys()):
                            if token_str not in self.token_usernames or \
                               self.token_usernames.get(token_str) is None or \
                               (isinstance(self.token_usernames.get(token_str), str) and "Ошибка" in self.token_usernames[token_str]):
                                tokens_to_refetch.append(token_str)
                        if tokens_to_refetch:
                            self.logger.info(f"Монитор: Обнаружено {len(tokens_to_refetch)} токенов для повторного получения имен.")
                            added_to_queue_count = 0
                            for token_to_fetch in tokens_to_refetch:
                                if token_to_fetch in self.active_fetcher_threads or token_to_fetch in self.tokens_to_fetch_queue:
                                    self.logger.debug(f"Монитор: Токен {token_to_fetch[-6:]} уже активен или в очереди. Пропуск.")
                                    continue
                                self.tokens_to_fetch_queue.append(token_to_fetch)
                                added_to_queue_count += 1                            
                            if added_to_queue_count > 0:
                                self.logger.info(f"Монитор: Добавлено {added_to_queue_count} токенов в очередь на повторное получение.")
                                asyncio.create_task(self._launch_fetcher_tasks_from_queue_async()) # Запускаем обработку очереди
            except Exception as e:
                self.logger.error(f"Ошибка мониторинга изменений в папке: {e}", exc_info=True)
    def on_display_mode_changed(self, checked: bool, *args, **kwargs):
        self.show_files_mode = checked
        self.mode_label.setText("Файлы" if checked else "Токены")
        self.token_groupbox.setTitle(
            "Выберите файлы с токенами" if checked else "Выберите токены (по именам ботов)"
        )
        self.update_tokens_list(force_rebuild=True)
    def on_select_all_changed(self, state: int, *args, **kwargs):
        is_checked = bool(state)
        self._default_selected = is_checked
        self.blockSignals(True)
        try:
            target_checkboxes = self.file_checkboxes if self.show_files_mode else self.token_checkboxes
            for cb in target_checkboxes.values():
                cb.setChecked(is_checked)
        finally:
            self.blockSignals(False)        
        if hasattr(self, '_update_timer') and self._update_timer.isActive():
            self._update_timer.stop()
        self._delayed_state_update()
    def update_tokens_list(self, force_rebuild: bool = False, refresh_ui_for_token: Optional[str] = None, *args):
        self.logger.debug(f"update_tokens_list вызван. force_rebuild: {force_rebuild}, refresh_ui_for_token: {refresh_ui_for_token[-6:] if refresh_ui_for_token else 'None'}, show_files_mode: {self.show_files_mode}")
        if refresh_ui_for_token and not force_rebuild and not self.show_files_mode:
            cb = self.token_checkboxes.get(refresh_ui_for_token)
            if cb:
                username = self.token_usernames.get(refresh_ui_for_token)
                bot_name = self.token_names.get(refresh_ui_for_token, username)
                display_text = ""
                tooltip_username = username or 'Загрузка...'
                tooltip_bot_name = bot_name or 'N/A'
                if username and not ("Ошибка" in str(username)):
                    actual_bot_name_display = bot_name if bot_name and not ("Ошибка" in str(bot_name)) else username
                    display_text = f"@{username} ({actual_bot_name_display}) [{refresh_ui_for_token[:5]}...]"
                elif username is None:
                    display_text = f"Загрузка... [{refresh_ui_for_token[:5]}...]"
                else:
                    display_text = f"{username} [{refresh_ui_for_token[:5]}...]"           
                self.logger.debug(f"Обновление текста для чекбокса токена {refresh_ui_for_token[-6:]}: '{display_text}'")
                cb.setText(display_text)
                cb.setToolTip(f"Токен: {refresh_ui_for_token}\nИмя пользователя: {tooltip_username}\nИмя бота: {tooltip_bot_name}")
            else:
                self.logger.warning(f"Чекбокс для токена {refresh_ui_for_token[-6:] if refresh_ui_for_token else '???'} не найден для частичного обновления.")
            return
        self.logger.debug("Полная перестройка списка чекбоксов...")
        layout = self.items_layout
        prev_file_cb_states = {fp: cb.isChecked() for fp, cb in self.file_checkboxes.items()}
        prev_token_cb_states = {tk: cb.isChecked() for tk, cb in self.token_checkboxes.items()}
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                layout.removeWidget(widget)
                widget.deleteLater()
        self.file_checkboxes.clear()
        self.token_checkboxes.clear()
        item_font = QFont()
        item_font.setPointSize(11)
        item_font.setBold(False)
        if self.show_files_mode:
            sorted_files = sorted(self.file_token_counts.keys(), key=lambda x: os.path.basename(x).lower())
            for file_path in sorted_files:
                base_name = os.path.basename(file_path)
                token_count = self.file_token_counts.get(file_path, 0)
                file_cb = QCheckBox(f"{base_name} ({token_count} токен{'ов' if token_count != 1 else ''})")
                file_cb.setFont(item_font)
                file_cb.setToolTip(f"Файл: {base_name}\nТокенов: {token_count}")
                current_checked_state = prev_file_cb_states.get(file_path, self._default_selected)
                file_cb.setChecked(current_checked_state)
                file_cb.stateChanged.connect(self.on_file_or_token_state_changed)
                self.file_checkboxes[file_path] = file_cb
                layout.addWidget(file_cb)
        else:
            sorted_tokens = sorted(
                self.token_to_file_map.keys(),
                key=lambda t: (str(self.token_usernames.get(t, "")).lower(), t)
            )
            for token_str in sorted_tokens:
                username = self.token_usernames.get(token_str)
                bot_name = self.token_names.get(token_str, username)
                display_text = ""
                tooltip_username_full = username or 'Загрузка...'
                tooltip_bot_name_full = bot_name or 'N/A'
                if username and not ("Ошибка" in str(username)):
                    actual_bot_name_display_full = bot_name if bot_name and not ("Ошибка" in str(bot_name)) else username
                    display_text = f"@{username} ({actual_bot_name_display_full}) [{token_str[:5]}...]"
                elif username is None:
                    display_text = f"Загрузка... [{token_str[:5]}...]"
                else:
                    display_text = f"{username} [{token_str[:5]}...]"                
                token_cb = QCheckBox(display_text)
                token_cb.setFont(item_font)
                token_cb.setToolTip(f"Токен: {token_str}\nИмя пользователя: {tooltip_username_full}\nИмя бота: {tooltip_bot_name_full}")
                current_checked_state = prev_token_cb_states.get(token_str, self._default_selected)
                token_cb.setChecked(current_checked_state)
                token_cb.stateChanged.connect(self.on_file_or_token_state_changed)
                self.token_checkboxes[token_str] = token_cb
                layout.addWidget(token_cb)        
        self._update_select_all_checkbox_state()
        if force_rebuild:
            self._emit_selected_tokens()
        QTimer.singleShot(0, self._emit_selected_tokens)
    def on_file_or_token_state_changed(self, state: int, *args):
        if hasattr(self, '_update_timer') and self._update_timer.isActive():
            self._update_timer.stop()
        if not hasattr(self, '_update_timer'):
            self._update_timer = QTimer()
            self._update_timer.setSingleShot(True)
            self._update_timer.timeout.connect(self._delayed_state_update)        
        self._update_timer.start(100)
    def _delayed_state_update(self, *args):
        self._update_select_all_checkbox_state()
        self._emit_selected_tokens()
    def _update_select_all_checkbox_state(self, *args):
        target_checkboxes = self.file_checkboxes if self.show_files_mode else self.token_checkboxes
        if not target_checkboxes:
            self.select_all_checkbox.blockSignals(True)
            self.select_all_checkbox.setChecked(False)
            self.select_all_checkbox.setEnabled(False)
            self.select_all_checkbox.blockSignals(False)
            return
        self.select_all_checkbox.setEnabled(True)
        all_items_are_checked = all(cb.isChecked() for cb in target_checkboxes.values())        
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(all_items_are_checked)
        self.select_all_checkbox.blockSignals(False)
    def _emit_selected_tokens(self, *args):
        selected_raw_tokens = self.get_selected_tokens()
        self._last_emitted_tokens = selected_raw_tokens
        self.tokens_updated.emit(selected_raw_tokens)
        self.logger.debug(f"Выбрано токенов: {len(selected_raw_tokens)}")
    def get_selected_tokens(self, *args) -> List[str]:
        selected_raw_tokens: Set[str] = set()
        try:
            if self.show_files_mode:
                selected_files = {file_path for file_path, cb in self.file_checkboxes.items() if cb.isChecked()}
                for token, file_path in self.token_to_file_map.items():
                    if file_path in selected_files:
                        selected_raw_tokens.add(token)
            else:
                selected_raw_tokens = {token for token, cb in self.token_checkboxes.items() if cb.isChecked()}
            if not selected_raw_tokens and self._default_selected and self._initial_load_complete:
                self.logger.debug("Ничего не выбрано, по умолчанию выбраны все доступные токены.")
                return list(self.token_to_file_map.keys())
        except Exception as e:
            self.logger.error(f"Ошибка при получении выбранных токенов: {e}", exc_info=True)        
        return list(selected_raw_tokens)
    def get_all_tokens_from_files_combined(self, *args, **kwargs) -> List[str]:
        all_tokens = set()
        for file_path in self.file_token_counts.keys():
            tokens_in_file = self._read_tokens_from_file_cached(file_path)
            for token in tokens_in_file:
                all_tokens.add(token)
        return list(all_tokens)
    def update_token_folder(self, new_folder_path: str, *args, **kwargs):
        self.logger.info(f"Обновление папки с токенами на: {new_folder_path}")
        self.token_folder_path = new_folder_path
        self.file_token_counts.clear()
        self.token_to_file_map.clear()
        self.token_usernames.clear()
        self.token_names.clear()
        self.token_descriptions.clear()
        self.file_checkboxes.clear()
        self.token_checkboxes.clear()
        self._read_tokens_from_file_cached.cache_clear()
        self._last_folder_state.clear()
        self._initial_load_complete = False
        if hasattr(self, 'thread_manager'):
            self.thread_manager.stop_all_threads()
            self.active_fetcher_threads.clear()            
        if hasattr(self, 'token_loader'):
            self.token_loader.token_folder_path = new_folder_path        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()  
        async def reload():
            await self.load_tokens_async()
            if self._is_running and (self._monitor_task is None or self._monitor_task.done()):
                loop = asyncio.get_event_loop()
                self._monitor_task = loop.create_task(self.monitor_folder_changes())   
            QTimer.singleShot(0, lambda: self.update_tokens_list(force_rebuild=True))
        asyncio.create_task(reload())
    def refresh_tokens(self, *args, **kwargs):
        self.logger.info("Принудительное обновление списка токенов.")
        self._read_tokens_from_file_cached.cache_clear()
        self._initial_load_complete = False      
        if hasattr(self, 'thread_manager'):
             self.thread_manager.stop_all_threads()
             self.active_fetcher_threads.clear()
        self.token_loader.start()
    def closeEvent(self, event, *args, **kwargs):
        self.logger.info("Закрытие окна BotTokenWindow...")
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()        
        if hasattr(self, 'thread_manager'):
            self.logger.info("Остановка всех потоков получения информации о ботах...")
            self.thread_manager.stop_all_threads()    
        super().closeEvent(event)
        self.logger.info("Окно BotTokenWindow закрыто.")
    def __del__(self, *args, **kwargs):
        self.logger.debug("BotTokenWindow __del__ called.")
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            try:
                self._monitor_task.cancel()
            except Exception as e:
                self.logger.debug(f"Error cancelling monitor task in __del__: {e}")     
        if hasattr(self, 'thread_manager'):
            self.thread_manager.stop_all_threads()
        if hasattr(self, 'executor') and self.executor:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except Exception as e:
                self.logger.error(f"Error shutting down executor in __del__: {e}")
