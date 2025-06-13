import os, asyncio, random, string, time
from aiogram.exceptions import TelegramForbiddenError
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QMutex, QMutexLocker, QTimer, QThreadPool
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QCheckBox, QTextEdit,
    QGroupBox, QFileDialog, QSizePolicy,
    QApplication, QLineEdit, QLabel, QSplitter, QHBoxLayout, QListWidget
)
from ui.okak import ErrorReportDialog
from ui.loader import load_config
from ui.timer import Timer
from ui.progress import ProgressWidget
from ui.proxy_utils import parse_proxies_from_txt
from ui.bots_win import BotTokenWindow
from ui.thread_base import BaseThread, ThreadManager
from ui.appchuy import AiogramBotConnection, select_proxy
def generate_random_message(*args):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))
class BotWorker(BaseThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(str, int, int, int)
    finished_signal = pyqtSignal(str, str)
    def __init__(self, token, proxy=None, text=None, min_delay=1, max_delay=5,
                react_to_start=True, react_to_messages=True, parent=None):
        super().__init__(session_file=token, parent=parent)
        self.token = token
        self.proxy = proxy
        self.text = text
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.react_to_start = react_to_start
        self.react_to_messages = react_to_messages
        self.timer = Timer(min_delay, max_delay)
        self._running = True
        self._stop_event = None
        self.bot_username = "unknown"
        self.start_count = 0
        self.reply_count = 0
        self.premium_count = 0
        self.started_users = set()
        self.premium_users = set()
        self.mutex = QMutex()
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 5
        self._already_stopped = False
        self._active_bots = set()
        self.bot_manager = AiogramBotConnection(token, proxy)
        self.bot_manager.log_signal.connect(self.log_signal.emit)
        self.bot_manager.error_signal.connect(lambda t, e: self.error_signal.emit(f"{t}: {e.message}"))
    def safe_emit(self, signal, *args):
        with QMutexLocker(self.mutex):
            signal.emit(*args)
    def safe_add_user(self, user_id, user_set, *args):
        with QMutexLocker(self.mutex):
            user_set.add(user_id)
    def stop(self, *args):
        if self._already_stopped:
            return
        self._already_stopped = True
        self._running = False
        self._active_bots.clear()
        if self._stop_event is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self._stop_event.set)
            except Exception:
                pass
        super()
    async def process(self, *args, **kwargs):
        try:
            self._already_stopped = False
            self._stop_event = asyncio.Event()
            await self.bot_worker()
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка в потоке бота {self.token}: {str(e)}")
        finally:
            self._running = False
            if not self._already_stopped:
                self.safe_emit(self.finished_signal, self.token, self.bot_username)
    async def _setup_bot(self, bot, *args):
        try:
            await bot.delete_webhook()
            await asyncio.sleep(2)
        except Exception as e:
            self.safe_emit(self.log_signal, f"⚠️ Ошибка при удалении вебхука: {e}")
            await asyncio.sleep(2)
        bot_info = await bot.get_me()
        self.bot_username = bot_info.username
        self.safe_emit(self.log_signal, f"✅ Бот {self.bot_username} успешно запущен")
    async def _handle_start_command(self, message, *args):
        user_id = message.from_user.id
        if user_id not in self.started_users:
            self.safe_add_user(user_id, self.started_users)
            self.safe_update_stats(
                start_count=self.start_count + 1,
                reply_count=self.reply_count + 1
            )
            if getattr(message.from_user, "is_premium", False) and user_id not in self.premium_users:
                self.safe_update_stats(premium_count=self.premium_count + 1)
                self.safe_add_user(user_id, self.premium_users)
            await self.save_user_id(user_id)
            await self._send_response(message)
    async def _handle_regular_message(self, message, *args):
        if self.react_to_messages:
            user_id = message.from_user.id
            await self.save_user_id(user_id)
            self.safe_update_stats(reply_count=self.reply_count + 1)
            await self._send_response(message)
    async def _send_response(self, message, *args):
        await self.timer.apply_delay()
        reply_text = self.text or self.generate_random_text()
        try:
            await message.reply(reply_text)
        except Exception as e:
            if "message to be replied not found" in str(e):
                self.safe_emit(self.log_signal, f"❗ Сообщение для ответа не найдено. Отправляю без reply. Подробнее: {e}")
                try:
                    await message.answer(reply_text)
                except Exception as e2:
                    self.safe_emit(self.log_signal, f"❗ Не удалось отправить сообщение даже без reply: {e2}")
            else:
                raise
        self._update_stats_and_log()
    def _update_stats_and_log(self, *args):
        self.safe_emit(self.stats_signal, self.bot_username,
                      self.start_count, self.reply_count, self.premium_count)
        self.safe_emit(self.log_signal,
            f"{self.bot_username} — получил /start ({self.start_count}) / сообщение ({self.start_count}) / автоответов отправлено ({self.reply_count}) / Премиум: {self.premium_count}")
    async def _handle_update(self, update, *args):
        if update.message:
            message = update.message
            if message.text and message.text.startswith('/start') and self.react_to_start:
                await self._handle_start_command(message)
            elif not (message.text and message.text.startswith('/start')):
                await self._handle_regular_message(message)
    async def _process_updates(self, bot, *args):
        offset = 0
        while self._running and not self._stop_event.is_set():
            try:
                updates = await self.bot_manager.get_updates(offset=offset, timeout=3)
                if updates:
                    for update in updates:
                        if not self._running or self._stop_event.is_set():
                            break
                        offset = update.update_id + 1
                        try:
                            await self._handle_update(update)
                        except TelegramForbiddenError:
                            user_id = getattr(update.message, 'from_user', None)
                            user_id = getattr(user_id, 'id', 'неизвестный')
                            self.safe_emit(self.log_signal, f"Пользователь {user_id} заблокировал бота")
                        except Exception as e:
                            await self._handle_message_error(e, bot)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                if await self._handle_general_error(e):
                    break
    async def _handle_message_error(self, error, bot, *args):
        err_str = str(error).lower()
        if "message to be replied not found" in err_str:
            self.safe_emit(self.log_signal, f"❗ Сообщение для ответа не найдено. Подробнее: {error}")
        elif any(x in err_str for x in ["ssl", "certificate", "handshake"]):
            raise
        elif "timed out" in err_str:
            self.safe_emit(self.log_signal, f"❗ Таймаут соединения. Проверьте интернет: {error}")
        elif "bad gateway" in err_str:
            self.safe_emit(self.log_signal, f"❗ Проблема на стороне Telegram (Bad Gateway): {error}")
        else:
            self.safe_emit(self.error_signal, f"Ошибка при обработке сообщения: {error}")
    async def _handle_general_error(self, error, *args):
        error_str = str(error).lower()
        if "unauthorized" in error_str:
            self.safe_emit(self.log_signal, f"⚠️ Бот {self.bot_username} не авторизован")
            return True
        elif "flood control" in error_str or "too many requests" in error_str:
            self.safe_emit(self.log_signal, f"⚠️ Превышен лимит запросов для бота {self.bot_username}. Ожидание...")
            await asyncio.sleep(5)
        elif "terminated by other getupdates request" in error_str:
            self.safe_emit(self.log_signal, f"⚠️ Конфликт: бот {self.bot_username} уже запущен в другом месте")
            return True
        elif any(x in error_str for x in ["ssl", "certificate", "handshake", "bad gateway", "connection", "timeout"]):
            await self.bot_manager.check_connection()
            return False
        return False
    async def bot_worker(self, *args):
        bot = None
        connection_error_count = 0
        MAX_CONNECTION_RETRIES = 3
        RETRY_DELAY = 5
        try:
            if self.token in self._active_bots:
                self.safe_emit(self.log_signal, f"⚠️ Бот с токеном {self.token[:10]}... уже запущен")
                return
            self._active_bots.add(self.token)
            while self._running and connection_error_count < MAX_CONNECTION_RETRIES:
                try:
                    bot = await self.bot_manager.connect()
                    await self._setup_bot(bot)
                    connection_error_count = 0
                    await self._process_updates(bot)
                except Exception as e:
                    if not self._running:
                        break
                    connection_error_count += 1
                    if connection_error_count < MAX_CONNECTION_RETRIES:
                        self.safe_emit(self.log_signal, f"🔄 Ошибка соединения. Попытка переподключения {connection_error_count}/{MAX_CONNECTION_RETRIES}")
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        self.safe_emit(self.log_signal, "❌ Превышено количество попыток переподключения")
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.safe_emit(self.error_signal, f"Критическая ошибка в работе бота {self.bot_username}: {e}")
        finally:
            if self.token in self._active_bots:
                self._active_bots.remove(self.token)
            if bot:
                try:
                    await self.bot_manager.disconnect()
                except Exception:
                    pass
            if self.bot_username != "unknown":
                self.safe_emit(self.log_signal, f"Бот {self.bot_username} остановлен")
            else:
                self.safe_emit(self.log_signal, f"Бот с токеном {self.token[:10]}... остановлен")
    async def reconnect_bot(self, bot, max_attempts=None, *args):
        return await self.bot_manager.reconnect()
    async def check_bot_connection(self, bot, *args):
        return await self.bot_manager.check_connection()
    async def save_user_id(self, user_id, *args):
        try:
            import aiofiles
            users_folder = os.path.join(os.getcwd(), "users_bot")
            os.makedirs(users_folder, exist_ok=True)
            users_file_path = os.path.join(users_folder, f"{self.bot_username}.txt")
            if not os.path.exists(users_file_path):
                async with aiofiles.open(users_file_path, 'w') as f:
                    await f.write(f"{self.token}\n")
            async with aiofiles.open(users_file_path, 'r') as f:
                lines = await f.readlines()
            existing_ids = set(line.strip() for line in lines[1:])
            if str(user_id) not in existing_ids:
                async with aiofiles.open(users_file_path, 'a') as f:
                    await f.write(f"{user_id}\n")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка при сохранении user_id: {e}")
    def generate_random_text(self, *args):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    def safe_update_stats(self, start_count=None, reply_count=None, premium_count=None, *args):
        with QMutexLocker(self.mutex):
            if start_count is not None:
                self.start_count = start_count
            if reply_count is not None:
                self.reply_count = reply_count
            if premium_count is not None:
                self.premium_count = premium_count
class AutoReplyAiogramWorker(QObject):
    log_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(int, int)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    def __init__(self, tokens, running_flag: list, proxy=None, text=None, min_interval=1, max_interval=5, react_to_start=True, react_to_messages=True, parent=None):
        super().__init__(parent)
        self.tokens = tokens
        self.running_flag = running_flag[0]
        self.proxy = proxy
        self.text = text
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.react_to_start = react_to_start
        self.react_to_messages = react_to_messages
        self.mutex = QMutex()
        self._is_stopping = False
        self.thread_manager = ThreadManager(self)
        self.bot_threads = []
        self.start_count = {}
        self.reply_count = {}
        self.premium_count = {}
        self.bot_usernames = {}
        self.last_status_text = None
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_threads)
        self.check_timer.start(500)
    def safe_emit(self, signal, *args):
        with QMutexLocker(self.mutex):
            signal.emit(*args)
    def update_stats(self, bot_username, start_count, reply_count, premium_count, *args):
        with QMutexLocker(self.mutex):
            self.start_count[bot_username] = start_count
            self.reply_count[bot_username] = reply_count
            self.premium_count[bot_username] = premium_count
            total_starts = sum(self.start_count.values())
            total_replies = sum(self.reply_count.values())
            self.stats_signal.emit(total_starts, total_replies)
    def run(self, *args):
        if self._is_stopping:
            return
        self.running_flag = True
        self.safe_emit(self.log_signal, "Запуск процесса обработки ботов...")
        self.bot_threads = []
        for i, token in enumerate(self.tokens):
            thread = BotWorker(
                token=token,
                proxy=self.proxy,
                text=self.text,
                min_delay=self.min_interval,
                max_delay=self.max_interval,
                react_to_start=self.react_to_start,
                react_to_messages=self.react_to_messages,
                parent=None
            )
            thread.log_signal.connect(self.log_signal.emit)
            thread.error_signal.connect(self.error_signal.emit)
            thread.stats_signal.connect(self.update_stats)
            thread.finished_signal.connect(self.on_thread_finished)
            self.thread_manager.add_thread(thread)
            self.bot_threads.append(thread)
            progress = min(75, 50 + int((i + 1) / len(self.tokens) * 25))
            self.safe_emit(self.progress_signal, progress, f"Запуск ботов {i+1}/{len(self.tokens)}...")
        for thread in self.bot_threads:
            self.thread_manager.start_thread(thread)
        self.safe_emit(self.log_signal, f"Всего запущено ботов: {len(self.bot_threads)}")
    def on_thread_finished(self, token, username, *args):
        if username == "unknown":
            self.safe_emit(self.log_signal, f"Бот с токеном {token[:10]}... завершил работу")
        else:
            self.safe_emit(self.log_signal, f"Бот {username} завершил работу")
    def check_threads(self, *args):
        if not self.running_flag or self._is_stopping:
            return
        active_threads = []
        authorized_threads = []
        for thread in self.bot_threads:
            if thread.isRunning():
                active_threads.append(thread)
                if getattr(thread, 'bot_username', 'unknown') != "unknown":
                    authorized_threads.append(thread)
                    self.bot_usernames[thread.token] = thread.bot_username
        total_bots = len(self.bot_threads)
        active_bots = len(active_threads)
        authorized_bots = len(authorized_threads)
        progress = int((authorized_bots / total_bots) * 100) if total_bots > 0 else 0
        status_text = f"Активно {authorized_bots}/{total_bots} ботов"
        if active_bots > authorized_bots:
            status_text += f" ({active_bots - authorized_bots} не авторизовано)"
        if status_text != self.last_status_text:
            self.safe_emit(self.log_signal, status_text)
            self.last_status_text = status_text
        if authorized_bots == total_bots and total_bots > 0:
            progress = 100
        self.safe_emit(self.progress_signal, progress, status_text)
        self.bot_threads = active_threads
    def stop(self, *args):
        if self._is_stopping:
            return
        self.safe_emit(self.log_signal, "Начинаем остановку всех ботов...")
        self._is_stopping = True
        self.running_flag = False
        try:
            if hasattr(self, 'check_timer') and self.check_timer.isActive():
                QTimer.singleShot(0, lambda: self.check_timer.stop())
            self.thread_manager.stop_all_threads()
            self.bot_threads.clear()
            self.start_count.clear()
            self.reply_count.clear()
            self.premium_count.clear()
            self.bot_usernames.clear()
            import gc
            gc.collect()
            self.safe_emit(self.log_signal, "Все боты успешно остановлены")
        except Exception as e:
            self.safe_emit(self.log_signal, f"Ошибка при остановке ботов: {e}")
        finally:
            self._is_stopping = False
class BotWindow(QWidget):
    def __init__(self, parent=None, *args):
        super().__init__(parent, *args)
        self.main_window = parent
        if hasattr(self.main_window, 'config_changed'):
            self.setWindowTitle("Управление ботами")
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QHBoxLayout()
        main_splitter = QSplitter()
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_layout.setContentsMargins(10, 10, 10, 10)
        self.progress_widget = ProgressWidget()
        left_layout.addWidget(self.progress_widget)
        proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси", self)
        proxy_layout.addWidget(self.use_proxy_checkbox)
        self.use_proxy_txt_checkbox = QCheckBox("Использовать прокси из txt-файла", self)
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
        proxy_layout.addWidget(self.use_proxy_txt_checkbox)
        left_layout.addLayout(proxy_layout)
        self.text_file_button = QPushButton("📝 Загрузить текст")
        self.text_file_button.clicked.connect(self.load_text_file)
        left_layout.addWidget(self.text_file_button)
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("⏱"))
        delay_layout.addWidget(QLabel("Мин:"))
        self.min_interval_input = QLineEdit()
        self.min_interval_input.setPlaceholderText("0")
        self.min_interval_input.setMaximumWidth(50)
        delay_layout.addWidget(self.min_interval_input)
        delay_layout.addWidget(QLabel("Макс:"))
        self.max_interval_input = QLineEdit()
        self.max_interval_input.setPlaceholderText("0")
        self.max_interval_input.setMaximumWidth(50)
        delay_layout.addWidget(self.max_interval_input)
        delay_layout.addWidget(QLabel("сек"))
        delay_layout.addStretch()
        left_layout.addLayout(delay_layout)
        self.react_to_start_checkbox = QCheckBox("Реагировать на /start")
        self.react_to_start_checkbox.setChecked(True)
        left_layout.addWidget(self.react_to_start_checkbox)
        self.react_to_messages_checkbox = QCheckBox("Реагировать на сообщения")
        self.react_to_messages_checkbox.setChecked(False)
        left_layout.addWidget(self.react_to_messages_checkbox)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("▶ Запустить")
        self.start_button.clicked.connect(self.start_process)
        button_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(QLabel("📊 Статистика:"))
        self.stats_list = QListWidget()
        left_layout.addWidget(self.stats_list)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("✓ Выберите ботов:"))
        self.bot_token_window = BotTokenWindow(token_folder_path=self.parent().bot_token_folder if self.parent() else "bots")
        self.bot_token_window.tokens_updated.connect(self.on_bots_win_tokens_updated)
        self.bot_token_window.files_updated.connect(self.on_bots_win_files_updated)
        right_panel.addWidget(self.bot_token_window)
        main_splitter.addWidget(left_groupbox)
        main_splitter.addWidget(self.log_output)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        main_splitter.addWidget(right_widget)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 1)
        main_layout.addWidget(main_splitter)
        self.setLayout(main_layout)
        self.running_flag = [False]
        self.auto_reply_thread = None
        self.text_content = None
        self.timer = Timer()
        self.proxies_list = []
        self.proxy_txt_path = None
        self.selected_tokens = []
    def on_bots_win_tokens_updated(self, tokens):
        if len(tokens) != len(self.selected_tokens):
            self.selected_tokens = tokens
            self.log_message(f"✓ Выбрано ботов: {len(tokens)}")
        else:
            self.selected_tokens = tokens
    def on_bots_win_files_updated(self, files):
        pass
    def log_message(self, message, *args):
        if "— получил /start" in message:
            token = message.split(" — ")[0]
            updated = False
            for i in range(self.stats_list.count()):
                item = self.stats_list.item(i)
                if item.text().startswith(token):
                    item.setText(message)
                    updated = True
                    break
            if not updated:
                self.stats_list.addItem(message)
        else:
            self.log_output.append(message)
    def load_text_file(self, *args):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите текстовый файл", "", "Text Files (*.txt)")
        if not file_path:
            self.log_message("Файл с текстом не выбран.")
            return
        try:
            with open(file_path, 'r') as file:
                self.text_content = file.read().strip()
            self.log_message("Текст для автоответов успешно загружен.")
        except Exception as e:
            self.log_message(f"Ошибка при загрузке текста: {e}")
    def get_delay_range(self, *args):
        try:
            min_delay, max_delay = Timer.parse_delay_input(
                self.min_interval_input.text(),
                self.max_interval_input.text()
            )
            self.timer.set_delay_range(min_delay, max_delay)
            return min_delay, max_delay
        except ValueError as e:
            self.log_message(f"Ошибка в интервалах задержки: {e}")
            return None, None
    def on_use_proxy_txt_toggled(self, checked, *args):
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
    def start_process(self, *args):
        if not self.selected_tokens:
            self.log_message("⛔ Загрузите токены ботов")
            return
        self.log_output.clear()
        self.log_message("✅ Начинаем запуск ботов...")
        try:
            error_text = None
            if not self.selected_tokens:
                error_text = "Ошибка: токены не загружены."
            if error_text:
                dlg = ErrorReportDialog(log_path=None)
                dlg.setWindowTitle("Ошибка API параметров")
                dlg.layout().insertWidget(1, QLabel(error_text))
                dlg.exec()
                self.log_message(error_text)
                return
            min_interval, max_interval = self.get_delay_range()
            if min_interval is not None and max_interval is not None and min_interval > max_interval:
                self.log_message("Ошибка: минимальная задержка больше максимальной.")
                return
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.log_message("Запуск процесса...")
            self.progress_widget.update_progress(0, "Запуск процесса...")
            self.running_flag[0] = True
            use_proxy = self.use_proxy_checkbox.isChecked()
            use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
            config = None
            if use_proxy:
                config = load_config()
            proxy, log_str = select_proxy(0, use_proxy, use_proxy_txt, self.proxies_list, config)
            self.log_message(log_str)
            if self.auto_reply_thread is not None:
                self.log_message("Остановка предыдущего процесса...")
                self.progress_widget.update_progress(25, "Остановка предыдущего процесса...")
                try:
                    self.auto_reply_thread.stop()
                    self.auto_reply_thread = None
                except Exception as e:
                    self.log_message(f"Ошибка при остановке предыдущего процесса: {e}")
            self.progress_widget.update_progress(50, "Инициализация ботов...")
            self.auto_reply_thread = AutoReplyAiogramWorker(
                self.selected_tokens, self.running_flag, proxy,
                self.text_content, min_interval or 1, max_interval or 5,
                react_to_start=self.react_to_start_checkbox.isChecked(),
                react_to_messages=self.react_to_messages_checkbox.isChecked()
            )
            self.auto_reply_thread.log_signal.connect(self.log_message)
            self.auto_reply_thread.error_signal.connect(self.handle_thread_error)
            self.auto_reply_thread.stats_signal.connect(self.update_stats)
            self.auto_reply_thread.progress_signal.connect(
                lambda value, text: self.progress_widget.update_progress(value, text)
            )
            total_bots = len(self.selected_tokens)
            self.progress_widget.update_progress(75, f"Запуск {total_bots} ботов...")
            self.auto_reply_thread.run()
            self.progress_widget.update_progress(80, f"Проверка авторизации ботов...")
            self.log_message("Процесс запущен, проверяем авторизацию ботов...")
        except Exception as e:
            self.log_message(f"Критическая ошибка при запуске процесса: {e}")
            self.progress_widget.update_progress(0, "Ошибка запуска")
            self.stop_process()
    def handle_thread_error(self, error_message, *args):
        self.log_message(f"Ошибка: {error_message}")
        try:
            ErrorReportDialog.send_error_report(None, error_text=error_message)
            msg_label = QLabel(f"Произошла ошибка: {error_message}")
            msg_label.setWordWrap(True)
            QTimer.singleShot(100, lambda: self.log_message("Отчет об ошибке отправлен"))
        except Exception as e:
            self.log_message(f"Не удалось отправить отчет об ошибке: {e}")
    def stop_process(self, *args):
        try:
            self.log_message("Остановка процесса...")
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.running_flag[0] = False
            class StopWorker(QThread):
                finished = pyqtSignal()
                progress = pyqtSignal(int, str)
                def __init__(self, auto_reply_thread, parent=None):
                    super().__init__(parent)
                    self.auto_reply_thread = auto_reply_thread
                def run(self, *args):
                    try:
                        if self.auto_reply_thread:
                            self.auto_reply_thread.stop()
                            self.progress.emit(50, "Останавливаем потоки...")
                            QApplication.processEvents()
                            threads_to_stop = list(self.auto_reply_thread.bot_threads) if hasattr(self.auto_reply_thread, 'bot_threads') else []
                            for thread in threads_to_stop:
                                if thread and thread.isRunning():
                                    try:
                                        thread.wait(2000)
                                    except Exception as e:
                                        pass
                            active_threads = [t for t in threads_to_stop if t and t.isRunning()]
                            if active_threads:
                                self.progress.emit(75, f"Осталось {len(active_threads)} незавершенных потоков")
                                QApplication.processEvents()
                                time.sleep(0.5)
                                for thread in active_threads:
                                    try:
                                        if thread and thread.isRunning():
                                            if hasattr(thread, 'terminate'):
                                                thread.terminate()
                                    except Exception:
                                        pass
                            QApplication.processEvents()
                            self.progress.emit(100, "Потоки остановлены")
                    except Exception as e:
                        self.progress.emit(100, f"Ошибка при остановке потоков: {e}")
                    finally:
                        self.finished.emit()
            def on_stop_finished():
                self.auto_reply_thread = None
                QApplication.processEvents()
                import gc
                gc.collect()
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.progress_widget.update_progress(100, "Процесс остановлен")
                self.log_message("Процесс остановлен, сессии ботов завершены.")
            worker = StopWorker(self.auto_reply_thread, self)
            worker.progress.connect(lambda value, text: self.progress_widget.update_progress(value, text))
            worker.finished.connect(on_stop_finished)
            worker.start()
        except Exception as e:
            self.log_message(f"Критическая ошибка при остановке процесса: {e}")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    def update_stats(self, total_starts, total_replies, *args):
        for i in range(self.stats_list.count()):
            if self.stats_list.item(i).text().startswith("Общая статистика:"):
                self.stats_list.takeItem(i)
                break
        self.stats_list.addItem(f"Общая статистика: /start: {total_starts}, ответов: {total_replies}")
