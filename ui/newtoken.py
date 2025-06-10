import os, re, asyncio, aiofiles, threading, sys, logging, random
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSizePolicy, QHBoxLayout, QCheckBox,
    QLineEdit, QPushButton, QGroupBox, QTextEdit,
    QToolTip, QRadioButton, QFileDialog
)
from telethon.errors import FloodWaitError, UsernameInvalidError
from ui.loader import load_config, load_proxy
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection, TelegramCustomError
)
import datetime
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
class NullWriter:
    def write(self, text): pass
    def flush(self): pass
sys.stdout = NullWriter()
sys.stderr = NullWriter()
for logger_name in ['', 'telethon', 'asyncio']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    null_handler = logging.NullHandler()
    logger.addHandler(null_handler)
class LogLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
class Logger:
    def __init__(self, log_area):
        self.log_area = log_area
    def log(self, message: str, level: LogLevel = LogLevel.INFO):
        prefix_map = {
            LogLevel.INFO: "ℹ️",
            LogLevel.WARNING: "⚠️",
            LogLevel.ERROR: "❌",
            LogLevel.SUCCESS: "✅"
        }
        if any(skip_msg in message.lower() for skip_msg in [
            "задержк", "подключение", "отправляем команду", "botfather ответил",
            "ожидание перед", "запуск сессии", "задержка выполнена"
        ]):
            return
        formatted_message_for_ui = message
        if not message.startswith(prefix_map[level]):
            formatted_message_for_ui = f"{prefix_map[level]} {message}"
        self.log_area.append(formatted_message_for_ui)
        try:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry_for_file = f"{timestamp} - {level.value} - {message}\n"
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(log_entry_for_file)
        except Exception as e:
            pass
class TokenCreationProcess(BaseThread):
    task_done_signal = pyqtSignal(str)
    def __init__(self, parent, session_folder, session_file, bot_names, bot_usernames, proxy=None):
        super().__init__(session_file=session_file, parent=parent)
        self.parent = parent
        self.session_folder = session_folder
        self.session_file = session_file
        self.bot_names = bot_names
        self.bot_usernames = bot_usernames
        self.proxy = proxy
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.emit_log)
        self.connection.error_signal.connect(self.emit_log)
        self.connection.flood_wait_signal.connect(lambda s, t: self.emit_log(f"⏳ {os.path.basename(s)} | Flood wait {t} сек."))
    async def process(self, *args):
        if not self.running:
            self.task_done_signal.emit(self.session_file)
            return
        success, me = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy), proxy=self.proxy)
        if not success or not me:
            self.task_done_signal.emit(self.session_file)
            return
        for i, (name, username) in enumerate(zip(self.bot_names, self.bot_usernames)):
            if not self.running:
                self.task_done_signal.emit(self.session_file)
                return
            if i > 0:
                await self.apply_delay()
                if not self.running:
                    self.task_done_signal.emit(self.session_file)
                    return
            result = await self.parent._create_and_process_bot(self.connection, self.session_file, name, username, self.proxy)
        self.task_done_signal.emit(self.session_file)
        if hasattr(self.connection, 'client') and self.connection.client:
            await self.connection.disconnect()
class NewTokenWindow(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, main_window):
        super().__init__()
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.main_window = main_window
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.connection = None
        self.setWindowTitle("Создать ботов")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._lock = asyncio.Lock()
        self.created_bots = 0
        self.failed_bots = 0
        self.skipped_sessions = 0
        self.unauthorized_sessions = 0
        self.limit_reached_sessions = 0
        self.active_tasks = 0
        self.completed_tasks = 0
        self.total_bots = 0
        main_layout = QHBoxLayout(self)
        left_groupbox = QGroupBox("")
        left_layout = self.create_left_layout()
        left_groupbox.setLayout(left_layout)
        self.session_window = SessionWindow(session_folder, self)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        if hasattr(self.main_window, 'config_changed'):
            self.main_window.config_changed.connect(self.session_window.on_config_changed)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(self.session_window, 1)
        self.logger = Logger(self.log_area)
        self.update_ui_state(False)
        if hasattr(self, 'delayed_starter') and self.delayed_starter:
            self.delayed_starter.delay_signal.connect(self.update_delay)
    def get_bots_per_session(self, *args, **kwargs):
        if self.two_bots_checkbox.isChecked():
            return 2
        return 1
    def create_left_layout(self, *args, **kwargs):
        left_layout = QVBoxLayout()
        settings_layout = QVBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси", self)
        self.use_proxy_txt_checkbox = QCheckBox("Использовать прокси из txt-файла", self)
        settings_layout.addWidget(self.use_proxy_checkbox)
        settings_layout.addWidget(self.use_proxy_txt_checkbox)
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
        self.proxies_list = []
        self.proxy_txt_path = None
        count_layout = QVBoxLayout()
        self.one_bot_checkbox = QRadioButton("1️⃣ Создать 1 бота")
        self.two_bots_checkbox = QRadioButton("2️⃣ Создать 2 бота")
        self.one_bot_checkbox.setChecked(True)
        count_layout.addWidget(self.one_bot_checkbox)
        count_layout.addWidget(self.two_bots_checkbox)
        settings_layout.addLayout(count_layout)
        self.force_random_username_checkbox = QCheckBox("Сразу генерировать случайный username")
        settings_layout.addWidget(self.force_random_username_checkbox)
        left_layout.addLayout(settings_layout)
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("👤 Введите имя бота или несколько имен через запятую")
        self.name_input.setMinimumHeight(30)
        left_layout.addWidget(self.name_input)
        self.username_input = QLineEdit(self)
        self.username_input.setPlaceholderText("🤖 Введите username бота через запятую")
        self.username_input.setMinimumHeight(30)
        left_layout.addWidget(self.username_input)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Задержка:"))
        self.min_delay_input = QLineEdit(self)
        self.min_delay_input.setPlaceholderText("от")
        self.min_delay_input.setMinimumHeight(30)
        delay_layout.addWidget(self.min_delay_input)        
        self.max_delay_input = QLineEdit(self)
        self.max_delay_input.setPlaceholderText("до")
        self.max_delay_input.setMinimumHeight(30)
        delay_layout.addWidget(self.max_delay_input)
        left_layout.addLayout(delay_layout)
        button_layout = QHBoxLayout()
        self.create_button = QPushButton("▶ Создать ботов")
        button_layout.addWidget(self.create_button)        
        self.stop_button = QPushButton("⏹ Остановить")
        button_layout.addWidget(self.stop_button)
        left_layout.addLayout(button_layout)
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        left_layout.addWidget(self.log_area)
        self.delay_label = QLabel("⏱ Текущая задержка: 0 секунд", self)
        left_layout.addWidget(self.delay_label)
        self.create_button.clicked.connect(self.handle_create)
        self.stop_button.clicked.connect(self.handle_stop)
        self.progress_widget = ProgressWidget(self)
        left_layout.addWidget(self.progress_widget)
        self.setup_validation()
        self.setup_tooltips()
        return left_layout
    def on_sessions_updated(self, valid_sessions, *args, **kwargs):
        if not valid_sessions:
            self.create_button.setEnabled(False)
        else:
            self.create_button.setEnabled(True)
    def validate_bot_creation(self, *args, **kwargs):
        if not self.username_input.text().strip():
            self.logger.log("Не указаны username для ботов", LogLevel.ERROR)
            return False, None, None
        sessions = self.session_window.get_selected_sessions()
        if not sessions:
            self.logger.log("Не выбрано ни одной сессии для создания ботов", LogLevel.ERROR)
            return False, None, None
        return True, sessions, self.username_input.text().strip()
    def handle_create(self, *args):
        if self.running:
            self.logger.log("Процесс уже запущен", LogLevel.WARNING)
            return
        valid, sessions, username_input = self.validate_bot_creation()
        if not valid:
            return
        valid_bots, usernames, names = self.prepare_bot_data(username_input)
        if not valid_bots:
            return
        bots_per_session = self.get_bots_per_session()
        session_assignments, total_bots = self.assign_bots_to_sessions(sessions, usernames, names)
        use_proxy = self.use_proxy_checkbox.isChecked()
        use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
        threads = []
        min_delay, max_delay = self._setup_delay_values()
        self.proxies_list = self.proxies_list or []
        for idx, assignment in enumerate(session_assignments):
            proxy = None
            if use_proxy_txt and self.proxies_list:
                proxy = load_proxy_from_list(idx, self.proxies_list)
                if proxy:
                    self.logger.log(f"🌐 [{assignment['session']}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}")
            elif use_proxy:
                config = load_config()
                proxy = load_proxy(config)
                if proxy:
                    self.logger.log(f"🌐 [{assignment['session']}] Используется прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.logger.log(f"ℹ️ [{assignment['session']}] Прокси не используется")
            thread = TokenCreationProcess(
                self,
                self.session_window.session_folder,
                assignment['session'],
                assignment['names'],
                assignment['usernames'],
                proxy
            )
            thread.log_signal.connect(self.logger.log)
            thread.task_done_signal.connect(self.on_task_done)
            thread.delay_signal.connect(self.update_delay, Qt.ConnectionType.QueuedConnection)
            thread.set_delay_range(min_delay, max_delay)
            threads.append(thread)
        self.total_threads = len(threads)
        self.completed_threads = 0
        self.progress_widget.progress_bar.setValue(0)
        self.progress_widget.status_label.setText(f"Выполняется задача для {self.total_threads} сессий...")
        if min_delay > 0 and max_delay > 0:
            self.logger.log("Запуск потоков последовательно с задержкой...")
            self.start_threads_with_delay(threads, min_delay, max_delay)
        else:
            self.logger.log("Запуск потоков параллельно...")
            for thread in threads:
                self.thread_manager.start_thread(thread)
        self.running = True
        self.update_ui_state(True)
    def on_task_done(self, session_file, *args):
        if not hasattr(self, '_already_done'):
            self._already_done = set()
        if session_file in self._already_done:
            return
        self._already_done.add(session_file)
        self.completed_threads += 1
        percent = int((self.completed_threads / self.total_threads) * 100) if self.total_threads else 100
        self.progress_widget.progress_bar.setValue(percent)
        self.progress_widget.status_label.setText(f"Выполнено {self.completed_threads} из {self.total_threads} сессий")
        if self.completed_threads >= self.total_threads:
            self.logger.log("✅ Все задачи завершены.")
            self.progress_widget.progress_bar.setValue(100)
            self.progress_widget.status_label.setText("Задача завершена.")
            self.create_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.running = False
            self.update_ui_state(False)
    def update_delay(self, delay, *args, **kwargs):
        self.delay_label.setText(f"⏱ Текущая задержка: {int(delay)} секунд")
    def prepare_bot_data(self, username_input, *args, **kwargs):
        usernames = [u.strip() for u in username_input.split(',') if u.strip()]
        if not usernames:
            self.logger.log("Не указаны корректные username для ботов", LogLevel.ERROR)
            return False, None, None
        name_input = self.name_input.text().strip()
        names = [n.strip() for n in name_input.split(',') if n.strip()]
        if not names:
            names = ["Telegram Bot"]
        elif len(names) == 1:
            names = names * len(usernames)
        elif len(names) != len(usernames):
            self.logger.log("Количество имен не соответствует количеству username. Пожалуйста, укажите одно имя для всех или равное количество имен и username.", LogLevel.ERROR)
            return False, None, None
        if self.force_random_username_checkbox.isChecked():
            new_usernames = []
            for _ in usernames:
                random_digit1 = random.randint(0, 9)
                random_letter = random.choice('abcdefghijklmnopqrstuvwxyz')
                random_digit2 = random.randint(0, 9)
                base_username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=12))
                new_suffix = f"{random_digit1}{random_letter}{random_digit2}"
                if len(base_username) + len(new_suffix) + 3 > 32:
                    base_username = base_username[:32 - len(new_suffix) - 3]
                new_usernames.append(f"{base_username}{new_suffix}bot")
            usernames = new_usernames
        else:
            for i in range(len(usernames)):
                if 'bot' not in usernames[i].lower():
                    usernames[i] += 'bot'
        return True, usernames, names
    def assign_bots_to_sessions(self, sessions, usernames, names, *args, **kwargs):
        bots_per_session = self.get_bots_per_session()
        self.logger.log(f"Выбран режим: {bots_per_session} бот(а/ов) на сессию", LogLevel.INFO)
        total_bots = len(usernames)
        required_sessions = (total_bots + bots_per_session - 1) // bots_per_session
        if len(sessions) < required_sessions:
            self.logger.log(f"⚠️ Для создания {total_bots} ботов (по {bots_per_session} на сессию) требуется {required_sessions} сессий, но выбрано только {len(sessions)}", LogLevel.WARNING)
        session_assignments = []
        for i in range(min(required_sessions, len(sessions))):
            start_idx = i * bots_per_session
            end_idx = min(start_idx + bots_per_session, total_bots)
            if start_idx >= total_bots:
                break
            session_assignments.append({
                'session': sessions[i],
                'usernames': usernames[start_idx:end_idx],
                'names': names[start_idx:end_idx]
            })
        return session_assignments, total_bots
    def _setup_delay_values(self, *args, **kwargs):
        try:
            min_delay = int(self.min_delay_input.text()) if self.min_delay_input.text().strip().isdigit() else 2
            max_delay = int(self.max_delay_input.text()) if self.max_delay_input.text().strip().isdigit() else 5
            if min_delay is None:
                min_delay = 2
            if max_delay is None:
                max_delay = 5
            min_delay = max(2, min_delay)
            max_delay = max(min_delay, max_delay)
        except ValueError as e:
            self.logger.log(f"Ошибка в настройках задержки, используются значения по умолчанию: 2-5 сек.", LogLevel.WARNING)
            min_delay, max_delay = 2, 5
        return min_delay, max_delay
    def log_bot_error(self, session_basename, message, username=None, *args, **kwargs):
        if username:
            self.logger.log(f"❌ {session_basename} | Не удалось создать бота @{username}: {message}", LogLevel.ERROR)
        else:
            self.logger.log(f"❌ {session_basename} | Не удалось создать бота: {message}", LogLevel.ERROR)
    def log_session_warning(self, session_basename, message, *args, **kwargs):
        self.logger.log(f"⚠️ {session_basename} | {message}", LogLevel.WARNING)
    def log_session_success(self, session_basename, message, *args, **kwargs):
        if ("Создано 2 ботов" in message) or ("Создан 2 бота" in message):
            emoji = "➕"
        else:
            emoji = "✅"
        self.logger.log(f"{emoji} {session_basename} | {message}", LogLevel.SUCCESS)
    async def _handle_bot_creation_result(self, result, session_basename, username):
        async with self._lock:
            if result == 'skip' or result == 'limit_reached':
                self.log_session_warning(session_basename, "Сессия достигла лимита в 20 ботов")
                self.limit_reached_sessions += 1
                return 'break_session'
            elif result:
                self.created_bots += 1
            else: 
                self.failed_bots += 1
            self._update_progress()
        return None
    async def _create_and_process_bot(self, connection, session_file, name, username, proxy):
        session_basename = os.path.basename(session_file)
        result = await self._create_single_bot_with_connection(connection, session_file, name, username, proxy)
        handling_result = await self._handle_bot_creation_result(result, session_basename, username)
        return handling_result
    async def _process_session(self, session_file, names, usernames, proxy):
        session_basename = os.path.basename(session_file)
        created_in_session = 0
        failed_in_session = 0 
        connection = None
        try:
            if not await self._check_running():
                return
            connection = TelegramConnection(self.session_window.session_folder)
            success, me = await connection.connect(session_file, use_proxy=bool(proxy))
            if not await self._check_running():
                if connection.client and connection.client.is_connected():
                    await connection.disconnect()
                return
            if not success or not me:
                self.logger.log(f"⚠️ {session_basename} не авторизована", LogLevel.WARNING)
                async with self._lock:
                    self.unauthorized_sessions += 1
                return
            for i, (name, username) in enumerate(zip(names, usernames)):
                if not await self._check_running():
                    break
                action = await self._create_and_process_bot(connection, session_file, name, username, proxy)
                if action == 'break_session':
                    break
                if i < len(names) - 1 and self.two_bots_checkbox.isChecked():
                    self.logger.log(f"⏳ {session_basename} | Ожидание 10 секунд перед созданием следующего бота...", LogLevel.INFO)
                    await asyncio.sleep(10)
        except TelegramCustomError as tce:
            self.log_session_warning(session_basename, f"Ошибка Telegram: {tce.message}")
            async with self._lock:
                self.failed_bots += len(usernames)
                self._update_progress()
        except Exception as e:
            self.logger.log(f"❌ Критическая ошибка обработки сессии {session_basename}: {str(e)}", LogLevel.ERROR)
        finally:
            if connection and connection.client and connection.client.is_connected():
                await connection.disconnect()
            async with self._lock:
                self.completed_tasks += 1
                self._update_progress()
    def _filter_connection_log(self, msg, *args, **kwargs):
        if any(skip_text in msg.lower() for skip_text in [
            "подключение", "отправляем", "botfather ответил", "задержка"
        ]):
            return
        self.logger.log(msg, LogLevel.INFO)
    async def _ensure_botfather_available(self, client, session_basename):
        try:
            bf = await client.get_entity('BotFather')
            if not bf:
                self.log_session_warning(session_basename, "Не удалось найти BotFather")
                return None
            return bf
        except Exception as e:
            self.log_session_warning(session_basename, f"Ошибка при получении BotFather: {str(e)}")
            return None
    async def _attempt_username_and_retry_if_needed(self, client, bf, initial_username, name, session_file, session_basename, *args, **kwargs):
        if self.force_random_username_checkbox.isChecked():
            max_retries = 2
            for attempt in range(max_retries + 1):
                random_digit1 = random.randint(0, 9)
                random_letter = random.choice('abcdefghijklmnopqrstuvwxyz')
                random_digit2 = random.randint(0, 9)
                base_username = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=12))
                new_suffix = f"{random_digit1}{random_letter}{random_digit2}"
                if len(base_username) + len(new_suffix) + 3 > 32:
                    base_username = base_username[:32 - len(new_suffix) - 3]
                current_username_to_try = f"{base_username}{new_suffix}bot"
                self.logger.log(f"ℹ️ {session_basename} | Попытка создания с новым username: @{current_username_to_try}", LogLevel.INFO)
                response = await self._send_command_and_read_response(client, bf, current_username_to_try, session_basename)
                if not response: return None
                if response.get('flood') == 'skip': return 'skip'
                if response.get('limit'): return 'limit_reached'
                is_successful_creation = False
                if 'token' in response:
                    is_successful_creation = True
                else:
                    response_text = response.get('text', '').lower()
                    raw_response_text = response.get('raw', '')
                    if "congratulations" in response_text or "done!" in response_text:
                        is_successful_creation = True            
                if is_successful_creation:
                    return await self._finalize_bot_creation(response, current_username_to_try, name, session_file, session_basename, new_username_attempted=True)
                if response.get('limit') or response.get('flood') == 'skip':
                    break
                if attempt < max_retries:
                    response_text_check = response.get('text', '').lower()
                    if not any(phrase in response_text_check for phrase in ['username is invalid', 'already taken', 'choose a different', 'sorry, this username is already taken']):
                        self.log_bot_error(session_basename, f"Неожиданный ответ BotFather после ввода username @{current_username_to_try} (попытка {attempt+1}): {response_text_check[:100]}...", current_username_to_try)
                        return None
                else:
                    self.log_bot_error(session_basename, f"Не удалось зарегистрировать username @{current_username_to_try} после {max_retries + 1} попыток.", current_username_to_try)
                    return None
            return None
        current_username_to_try = initial_username
        max_retries = 2
        start_attempt = 0
        for attempt in range(start_attempt, max_retries + 1):
            if attempt > 0:
                if attempt == 1:
                    self.log_bot_error(session_basename, f"Username @{initial_username} недоступен или неверный.", initial_username)
                else:
                    self.log_bot_error(session_basename, f"Username @{current_username_to_try} недоступен или неверный (попытка {attempt}).", current_username_to_try)
                random_digit1 = random.randint(0, 9)
                random_letter = random.choice('abcdefghijklmnopqrstuvwxyz')
                random_digit2 = random.randint(0, 9)
                base_username = initial_username.lower().removesuffix('bot')
                new_suffix = f"{random_digit1}{random_letter}{random_digit2}"
                if len(base_username) + len(new_suffix) + 3 > 32:
                    available_len_for_base = 32 - len(new_suffix) - 3
                    if available_len_for_base < 1:
                        self.log_bot_error(session_basename, "Невозможно сгенерировать короткий username, базовое имя слишком длинное.", initial_username)
                        return None
                    base_username = base_username[:available_len_for_base]
                current_username_to_try = f"{base_username}{new_suffix}bot"
                self.logger.log(f"ℹ️ {session_basename} | Попытка создания с новым username: @{current_username_to_try}", LogLevel.INFO)
            response = await self._send_command_and_read_response(client, bf, current_username_to_try, session_basename)
            if not response: return None
            if response.get('flood') == 'skip': return 'skip'
            if response.get('limit'): return 'limit_reached'
            is_successful_creation = False
            if 'token' in response:
                is_successful_creation = True
            else:
                response_text = response.get('text', '').lower()
                raw_response_text = response.get('raw', '')
                if "congratulations" in response_text or "done!" in response_text:
                    is_successful_creation = True            
            if is_successful_creation:
                return await self._finalize_bot_creation(response, current_username_to_try, name, session_file, session_basename, new_username_attempted=(attempt > 0))
            if response.get('limit') or response.get('flood') == 'skip':
                break
            if attempt < max_retries:
                response_text_check = response.get('text', '').lower()
                if not any(phrase in response_text_check for phrase in ['username is invalid', 'already taken', 'choose a different', 'sorry, this username is already taken']):
                    self.log_bot_error(session_basename, f"Неожиданный ответ BotFather после ввода username @{current_username_to_try} (попытка {attempt+1}): {response_text_check[:100]}...", current_username_to_try)
                    return None
            else:
                self.log_bot_error(session_basename, f"Не удалось зарегистрировать username @{current_username_to_try} после {max_retries + 1 - start_attempt} попыток.", current_username_to_try)
                return None
        return None
    async def _finalize_bot_creation(self, response, username_to_save, name_to_save, session_file, session_basename, new_username_attempted=False, *args, **kwargs):
        actual_username_for_log = username_to_save
        if new_username_attempted and response and ('token' in response or "congratulations" in response.get('raw', '').lower()):
            pass 
        if response and 'token' in response:
            return await self._save_and_return_token(response['token'], username_to_save, name_to_save, session_file)
        raw_text = response.get('raw', '') if response else ''
        if ("congratulations" in raw_text.lower() or "done!" in raw_text.lower()):
            token = self._extract_token(raw_text)
            if token:
                return await self._save_and_return_token(token, username_to_save, name_to_save, session_file)
        self.log_bot_error(session_basename, f"Не удалось извлечь токен для @{username_to_save} после ответа BotFather.", username_to_save)
        return None
    async def _create_single_bot_with_connection(self, connection, session_file, name, username, proxy=None, *args, **kwargs):
        session_basename = os.path.basename(session_file)
        if not await self._check_running(): return None
        client = connection.client
        if not client:
            self.log_session_warning(session_basename, "Не удалось получить клиент Telegram")
            return None
        bf = await self._ensure_botfather_available(client, session_basename)
        if not bf: return None
        start_resp = await self._send_command_and_read_response(client, bf, '/start', session_basename)
        if not start_resp: return None 
        if start_resp.get('flood') == 'skip': return 'skip'
        if start_resp.get('limit'): return 'limit_reached' 
        if 'token' in start_resp: 
            return await self._finalize_bot_creation(start_resp, username, name, session_file, session_basename)
        newbot_resp = await self._send_command_and_read_response(client, bf, '/newbot', session_basename)
        if not newbot_resp: return None
        if newbot_resp.get('flood') == 'skip': return 'skip'
        if newbot_resp.get('limit'): return 'limit_reached'
        if 'token' in newbot_resp:
            return await self._finalize_bot_creation(newbot_resp, username, name, session_file, session_basename)
        newbot_response_text = newbot_resp.get('text', '').lower()
        if "alright, a new bot" in newbot_response_text or "please choose a name" in newbot_response_text:
            name_resp = await self._send_command_and_read_response(client, bf, name, session_basename)
            if not name_resp: return None
            if name_resp.get('flood') == 'skip': return 'skip'
            if name_resp.get('limit'): return 'limit_reached'
            if 'token' in name_resp:
                return await self._finalize_bot_creation(name_resp, username, name, session_file, session_basename)
            name_response_text = name_resp.get('text', '').lower()
            if "good" in name_response_text or "now let's choose a username" in name_response_text:
                return await self._attempt_username_and_retry_if_needed(client, bf, username, name, session_file, session_basename)
            else:
                self.log_bot_error(session_basename, f"Неожиданный ответ после отправки имени бота: {name_response_text[:100]}", username)
                return None
        elif "good" in newbot_response_text or "now let's choose a username" in newbot_response_text:
            return await self._attempt_username_and_retry_if_needed(client, bf, username, name, session_file, session_basename)
        else:
            self.log_bot_error(session_basename, f"Неожиданный ответ BotFather на /newbot: {newbot_response_text[:100]}", username)
            return None
        return None
    async def _send_command_and_read_response(self, client, bf, command, session_basename, delay=2, *args, **kwargs):
        if not await self._check_running():
            return None
        await client.send_message(bf, command)
        await asyncio.sleep(delay)
        if not await self._check_running():
            return None
        resp = await client.get_messages(bf, limit=1)
        if not resp or not resp[0] or not resp[0].text:
            self.log_bot_error(session_basename, "Не получен ответ от BotFather")
            return None
        resp_text = resp[0].text.lower()
        resp_full = resp[0].text
        flood_result = await self._handle_flood_wait(resp_text, bf, session_basename)
        if flood_result:
            return {'flood': flood_result}
        if "can't add more than 20 bots" in resp_text:
            return {'limit': True}
        token = self._extract_token(resp_full)
        if token:
            bot_name = command
            if command == '/start' or command == '/newbot':
                bot_name = 'нового бота'
            elif command.startswith('/'):
                bot_name = 'бота'
            return {'token': token}
        return {'text': resp_text, 'raw': resp_full}
    async def _handle_flood_wait(self, response_text, botfather_entity, session_name="", *args, **kwargs):
        if 'too many attempts' in response_text and 'second' in response_text:
            m = re.search(r'(\d{1,})\s*second', response_text)
            sec = int(m.group(1)) if m else 60
            session_basename = os.path.basename(session_name) if session_name else ""
            if sec > 50:
                self.log_session_warning(session_basename, f"⏳ Flood wait {sec} сек. слишком большая, сессия пропущена")
                return 'skip'
            else:
                await asyncio.sleep(sec + 1)
                return True
        return False
    def _update_progress(self, *args, **kwargs):
        total = self.total_bots
        completed = self.created_bots + self.failed_bots
        if total > 0:
            progress = int((completed / total) * 100)
            self.progress_widget.progress_bar.setValue(progress)
            if self.created_bots > 0:
                self.progress_widget.status_label.setText(
                    f"Создано {self.created_bots}/{total} ботов ({self.completed_tasks}/{self.active_tasks} сессий)"
                )
            else:
                self.progress_widget.status_label.setText(
                    f"Обработано {completed}/{total} ботов ({self.completed_tasks}/{self.active_tasks} сессий)"
                )
    def _show_final_report(self, *args, **kwargs):
        self.logger.log("📊 Итоговый отчет о создании ботов:", LogLevel.INFO)
        if self.unauthorized_sessions > 0:
            self.logger.log(f"⚠️ Пропущено {self.unauthorized_sessions} неавторизованных сессий", LogLevel.WARNING)
        if self.skipped_sessions > 0:
            self.logger.log(f"⚠️ Пропущено {self.skipped_sessions} сессий из-за лимита попыток BotFather", LogLevel.WARNING)
        if self.limit_reached_sessions > 0:
            self.logger.log(f"⚠️ Пропущено {self.limit_reached_sessions} сессий из-за лимита в 20 ботов", LogLevel.WARNING)
        if self.created_bots > 0:
            self.logger.log(f"✅ Успешно создано {self.created_bots} ботов из {self.total_bots} запланированных", LogLevel.SUCCESS)
        if self.failed_bots > 0:
            self.logger.log(f"❌ Не удалось создать {self.failed_bots} ботов", LogLevel.ERROR)
        if self.created_bots == 0 and self.total_bots > 0:
            self.logger.log("❌ Процесс завершен без создания ботов", LogLevel.ERROR)
        elif self.created_bots == self.total_bots:
            self.logger.log("✅ Все запланированные боты успешно созданы!", LogLevel.SUCCESS)
        else:
            self.logger.log("⚠️ Процесс завершен, некоторые боты не были созданы", LogLevel.WARNING)
        self.progress_widget.progress_bar.setValue(100)
        if self.created_bots > 0:
            self.progress_widget.status_label.setText(f"Готово: создано {self.created_bots}/{self.total_bots} ботов")
        else:
            self.progress_widget.status_label.setText("Готово")
    def setup_validation(self, *args):
        self.name_input.textChanged.connect(self.validate_name)
        self.username_input.textChanged.connect(self.validate_username)
        self.min_delay_input.textChanged.connect(self.validate_delays)
        self.max_delay_input.textChanged.connect(self.validate_delays)
    def setup_tooltips(self, *args):
        self.name_input.setToolTip("Введите имя бота или несколько имен через запятую. Если введено одно имя, оно будет использовано для всех ботов.")
        self.username_input.setToolTip("Введите username бота или несколько username через запятую.")
        self.min_delay_input.setToolTip("Минимальная задержка между действиями в секундах")
        self.max_delay_input.setToolTip("Максимальная задержка между действиями в секундах")
    def validate_name(self, *args):
        self.validate_input(
            self.name_input,
            3,
            "Каждое имя должно содержать минимум 3 символа"
        )
    def validate_username(self, *args):
        username = self.username_input.text()
        name = self.name_input.text()
        if not username:
            self.username_input.setStyleSheet("")
            return
        usernames = [u.strip() for u in username.split(',')]
        names = [n.strip() for n in name.split(',')]
        def check_names_match(items):
            return names and len(names) > 1 and len(names) != len(items) and len(names) != 1
        def validate_username_chars(username):
            if not re.match(r'^[a-zA-Z0-9_]*$', username):
                self.username_input.setStyleSheet("border: 1px solid red;")
                QToolTip.showText(self.username_input.mapToGlobal(self.username_input.rect().bottomRight()),
                                "Юзернейм может содержать только латинские буквы, цифры и подчеркивания")
                return False
            return True
        for u in usernames:
            if not validate_username_chars(u):
                return
            if u and len(u) < 3:
                self.username_input.setStyleSheet("border: 1px solid red;")
                QToolTip.showText(self.username_input.mapToGlobal(self.username_input.rect().bottomRight()),
                                "Юзернейм должен быть не менее 3 символов")
                return
        self.validate_input(
            self.username_input,
            3,
            "Юзернейм должен быть не менее 3 символов",
            check_names_match,
            "Количество юзернеймов не соответствует количеству имен. Используйте одно имя для всех или равное количество."
        )
    def validate_delays(self, *args):
        try:
            min_delay = int(self.min_delay_input.text()) if self.min_delay_input.text().strip().isdigit() else 2
            max_delay = int(self.max_delay_input.text()) if self.max_delay_input.text().strip().isdigit() else 5
            if min_delay > max_delay:
                raise ValueError("Минимальная задержка должна быть меньше или равна максимальной")
            self.min_delay_input.setStyleSheet("")
            self.max_delay_input.setStyleSheet("")
        except ValueError as e:
            self.min_delay_input.setStyleSheet("border: 1px solid red;")
            self.max_delay_input.setStyleSheet("border: 1px solid red;")
            QToolTip.showText(self.min_delay_input.mapToGlobal(self.min_delay_input.rect().bottomRight()),
                            str(e))
    async def _save_and_return_token(self, token, username, name, session_file, *args, **kwargs):
        if not token:
            return None
        successful_save = await self.save_token(token, username, name, session_file)
        return token if successful_save else None
    async def save_token(self, token, username, name=None, session_file=None, *args, **kwargs):
        if not token or not username:
            self.logger.log(f"❌ Невозможно сохранить токен: отсутствуют данные", LogLevel.ERROR)
            return False
        token_path = os.path.join(os.getcwd(), 'newtoken.txt')
        users_path = os.path.join(os.getcwd(), 'newusers.txt')
        info_path = os.path.join(os.getcwd(), 'botinfo.txt')
        if username.startswith('@'):
            username = username[1:]
        bot_url = f"https://t.me/{username}"
        try:
            async with aiofiles.open(token_path, 'a', encoding='utf-8') as f:
                await f.write(f"{token}\n")
            async with aiofiles.open(users_path, 'a', encoding='utf-8') as f:
                await f.write(f"{bot_url}\n")
            session_name = os.path.basename(session_file) if session_file else "неизвестная сессия"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            name_str = name if name else "Без имени"
            info_line = f"[{timestamp}] @{username} | {token} | Имя: {name_str} | Сессия: {session_name}\n"
            async with aiofiles.open(info_path, 'a', encoding='utf-8') as f:
                await f.write(info_line)
            self.logger.log(f"✅ Создан бот @{username}", LogLevel.SUCCESS)
            return True
        except Exception as e:
            self.logger.log(f"❌ Ошибка при сохранении токена для @{username}: {str(e)}", LogLevel.ERROR)
            return False
    def handle_stop(self, *args):
        if not self.running:
            return
        self.running = False
        self.stop_button.setEnabled(False)
        self.create_button.setEnabled(False)
        self.stop_all_operations()
        self.logger.log("Остановка процесса... (дождитесь завершения текущей операции)", LogLevel.WARNING)
        self.progress_widget.status_label.setText("Останавливается...")
        self.progress_widget.progress_bar.setValue(100)
        self.update_ui_state(False)
    def update_ui_state(self, is_running, *args, **kwargs):
        self.create_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
        self.username_input.setEnabled(not is_running)
        self.name_input.setEnabled(not is_running)
        self.min_delay_input.setEnabled(not is_running)
        self.max_delay_input.setEnabled(not is_running)
        self.one_bot_checkbox.setEnabled(not is_running)
        self.two_bots_checkbox.setEnabled(not is_running)
        self.use_proxy_checkbox.setEnabled(not is_running)
        self.use_proxy_txt_checkbox.setEnabled(not is_running)
        self.force_random_username_checkbox.setEnabled(not is_running)
        self.session_window.setEnabled(not is_running)
    def __del__(self, *args):
        self.executor.shutdown(wait=False)
        if hasattr(self, 'connection') and self.connection:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.connection.disconnect())
                else:
                    loop.run_until_complete(self.connection.disconnect())
            except Exception:
                pass
    def _extract_token(self, text, *args, **kwargs):
        if not text:
            return None
        token_pattern = r'(\d+:[A-Za-z0-9_-]{35,})'
        match = re.search(token_pattern, text)
        if match:
            return match.group(1)
        return None
    async def _check_running(self, session_basename=None):
        return self.running
    def validate_input(self, input_field, min_length, error_message, warning_condition=None, warning_message=None, *args, **kwargs):
        text = input_field.text()
        if not text:
            input_field.setStyleSheet("")
            return
        items = [item.strip() for item in text.split(',')]
        for item in items:
            if len(item) < min_length:
                input_field.setStyleSheet("border: 1px solid red;")
                QToolTip.showText(input_field.mapToGlobal(input_field.rect().bottomRight()), error_message)
                return
        if warning_condition and warning_condition(items):
            input_field.setStyleSheet("border: 1px solid orange;")
            QToolTip.showText(input_field.mapToGlobal(input_field.rect().bottomRight()), warning_message)
            return
        input_field.setStyleSheet("")
    def on_use_proxy_txt_toggled(self, checked, *args):
        if checked:
            file_path, _ = QFileDialog.getOpenFileName(self, "Выберите txt-файл с прокси", "", "Text Files (*.txt)")
            if file_path:
                self.proxy_txt_path = file_path
                self.proxies_list = parse_proxies_from_txt(file_path)
                self.logger.log(f"✅ Загружено прокси из файла: {len(self.proxies_list)}")
            else:
                self.use_proxy_txt_checkbox.setChecked(False)
        else:
            self.proxy_txt_path = None
            self.proxies_list = []
