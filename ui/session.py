import os, asyncio, random, string, time
import aiofiles
import aiofiles.os as aio_os
from aiogram.exceptions import TelegramForbiddenError
from PyQt6.QtCore import pyqtSignal, QObject, QMutex, QMutexLocker, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QCheckBox, QTextEdit,
    QGroupBox, QFileDialog, QSizePolicy,
    QLineEdit, QLabel, QSplitter, QHBoxLayout, QListWidget
)
from ui.okak import ErrorReportDialog
from ui.loader import load_config
from ui.progress import ProgressWidget
from ui.proxy_utils import parse_proxies_from_txt
from ui.bots_win import BotTokenWindow
from ui.thread_base import BaseThread, ThreadManager, ThreadStopMixin
from ui.appchuy import AiogramBotConnection, select_proxy, AiogramCustomError, AiogramErrorType
class BotWorker(BaseThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(str, int, int, int)
    finished_signal = pyqtSignal(str, str)
    _active_bots = set()
    def __init__(self, token, proxy=None, text=None, min_delay=0, max_delay=0,
                 reply_to_all=False, parent=None):
        super().__init__(session_file=token, parent=parent)
        self.token = token
        self.proxy = proxy
        self.text = text
        self.reply_to_all = reply_to_all
        self.set_delay_range(min_delay, max_delay)
        self.bot_username = "unknown"
        self.start_count = 0
        self.reply_count = 0
        self.premium_count = 0
        self.started_users = set()
        self.premium_users = set()
        self.mutex = QMutex()
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 5
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
        super().stop()
    async def process(self, *args, **kwargs):
        try:
            await self.bot_worker()
        except asyncio.CancelledError:
            self.safe_emit(self.log_signal, f"Бот {self.bot_username or self.token[:10]}... отменен.")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка в потоке бота {self.token}: {str(e)}")
        finally:
            self.running = False
            self.safe_emit(self.finished_signal, self.token, self.bot_username)
    async def _setup_bot(self, *args):
        try:
            await self.bot_manager.bot.delete_webhook()
            await asyncio.sleep(2)
        except Exception as e:
            self.safe_emit(self.log_signal, f"⚠️ Ошибка при удалении вебхука: {e}")
            await asyncio.sleep(2)
        bot_info = await self.bot_manager.bot.get_me()
        self.bot_username = bot_info.username
        self.safe_emit(self.log_signal, f"✅ Бот {self.bot_username} успешно запущен")
    async def _handle_start_command(self, message, *args):
        user_id = message.from_user.id
        is_new_user = user_id not in self.started_users
        if is_new_user:
            self.safe_add_user(user_id, self.started_users)
            self.safe_update_stats(start_count=self.start_count + 1)
            if getattr(message.from_user, "is_premium", False) and user_id not in self.premium_users:
                self.safe_update_stats(premium_count=self.premium_count + 1)
                self.safe_add_user(user_id, self.premium_users)
            await self.save_user_id(user_id)
        if self.reply_to_all:
            self.safe_update_stats(reply_count=self.reply_count + 1)
            await self._send_response(message)
    async def _handle_regular_message(self, message, *args):
        user_id = message.from_user.id
        await self.save_user_id(user_id)
        if self.reply_to_all:
            self.safe_update_stats(reply_count=self.reply_count + 1)
            await self._send_response(message)
    async def _send_response(self, message, *args):
        await self.apply_delay()
        reply_text = self.text or self.generate_random_text()
        try:
            await message.reply(reply_text)
        except Exception as e:
            error_msg = str(e).lower()
            if "message to be replied not found" in error_msg:
                self.safe_emit(self.log_signal, f"❗ Сообщение для ответа не найдено. Отправляю без reply. Подробнее: {e}")
                try:
                    await message.answer(reply_text)
                except Exception as e2:
                    self.safe_emit(self.log_signal, f"❗ Не удалось отправить сообщение даже без reply: {e2}")
            elif "have no write access to the chat" in error_msg:
                self.safe_emit(self.log_signal, f"⛔ Нет прав на запись в чат: {message.chat.id}")
            else:
                self.safe_emit(self.error_signal, f"Ошибка при отправке ответа: {e}")
        self._update_stats_and_log()
    def _update_stats_and_log(self, *args):
        self.safe_emit(self.stats_signal, self.bot_username,
                      self.start_count, self.reply_count, self.premium_count)
        self.safe_emit(self.log_signal,
            f"{self.bot_username} — получил /start ({self.start_count}) / сообщение ({self.start_count}) / автоответов отправлено ({self.reply_count}) / Премиум: {self.premium_count}")
    async def _handle_update(self, update, *args):
        if update.message:
            message = update.message
            if message.text and message.text.startswith('/start') and self.reply_to_all:
                await self._handle_start_command(message)
            elif not (message.text and message.text.startswith('/start')):
                await self._handle_regular_message(message)
    async def _process_updates(self, *args):
        offset = 0
        while self.running:
            try:
                updates = await self.bot_manager.get_updates(offset=offset, timeout=3)
                if updates:
                    for update in updates:
                        if not self.running:
                            break
                        offset = update.update_id + 1
                        try:
                            await self._handle_update(update)
                        except TelegramForbiddenError:
                            user_id = getattr(update.message, 'from_user', None)
                            user_id = getattr(user_id, 'id', 'неизвестный')
                            self.safe_emit(self.log_signal, f"Пользователь {user_id} заблокировал бота")
                        except Exception as e:
                            self.safe_emit(self.error_signal, f"Ошибка при обработке сообщения: {e}")
            except AiogramCustomError as e:
                if e.error_type in [AiogramErrorType.UNAUTHORIZED, AiogramErrorType.BAD_GATEWAY]:
                    self.safe_emit(self.log_signal, f"Критическая ошибка {self.bot_username}: {e.message}. Поток будет остановлен.")
                    break
                elif e.error_type == AiogramErrorType.CONNECTION:
                    self.safe_emit(self.log_signal, f"Проблемы с соединением у {self.bot_username}. Запускаю переподключение...")
                    if not await self.bot_manager.reconnect():
                        self.safe_emit(self.log_signal, f"Не удалось переподключить {self.bot_username}. Поток остановлен.")
                        break
                    else:
                        offset = 0
                else:
                    self.safe_emit(self.error_signal, f"Ошибка в цикле обновлений: {e.message}")
                    await asyncio.sleep(self.reconnect_delay)
            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                self.safe_emit(self.error_signal, f"Неизвестная ошибка в цикле обновлений: {e}")
                await asyncio.sleep(self.reconnect_delay)
    async def bot_worker(self, *args):
        try:
            if self.token in BotWorker._active_bots:
                self.safe_emit(self.log_signal, f"⚠️ Бот с токеном {self.token[:10]}... уже запущен")
                return
            BotWorker._active_bots.add(self.token)
            if await self.bot_manager.connect():
                await self._setup_bot()
                await self._process_updates()
            else:
                self.safe_emit(self.log_signal, f"Не удалось запустить бота {self.token[:10]}")
        except asyncio.CancelledError:
            self.safe_emit(self.log_signal, f"Работа bot_worker для {self.bot_username} отменена.")
            raise
        except Exception as e:
            self.safe_emit(self.error_signal, f"Критическая ошибка в работе бота {self.bot_username}: {e}")
        finally:
            if self.token in BotWorker._active_bots:
                BotWorker._active_bots.remove(self.token)
            if self.bot_manager.is_connected:
                try:
                    await self.bot_manager.disconnect()
                except Exception:
                    pass
            if self.bot_username != "unknown":
                self.safe_emit(self.log_signal, f"Бот {self.bot_username} остановлен")
            else:
                self.safe_emit(self.log_signal, f"Бот с токеном {self.token[:10]}... остановлен")
    async def save_user_id(self, user_id, *args):
        try:
            if not self.bot_username or self.bot_username == "unknown":
                self.safe_emit(self.log_signal, f"⚠️ Не удалось сохранить user_id {user_id}: имя бота ({self.bot_username}) не определено.")
                return
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            users_folder = os.path.join(project_root, "users_bot")
            os.makedirs(users_folder, exist_ok=True)
            users_file_path = os.path.join(users_folder, f"{self.bot_username}.txt")
            existing_ids = set()
            file_exists = os.path.exists(users_file_path)
            if file_exists:
                try:
                    with open(users_file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    existing_ids = set(line.strip() for line in lines[1:] if line.strip())
                except Exception as e:
                    self.safe_emit(self.error_signal, f"Ошибка чтения файла {users_file_path}: {e}")
                    return
            if str(user_id) not in existing_ids:
                try:
                    with open(users_file_path, 'a', encoding='utf-8') as f:
                        if not file_exists:
                            f.write(f"{self.token}\n")
                        f.write(f"{user_id}\n")
                except Exception as e:
                    self.safe_emit(self.error_signal, f"Ошибка записи в файл {users_file_path}: {e}")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка при сохранении user_id для бота {self.bot_username}: {e}")
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
    def __init__(self, tokens, running_flag: list, proxy=None, text=None, min_interval=1, max_interval=5, reply_to_all=False, parent=None):
        super().__init__(parent)
        self.tokens = tokens
        self.running_flag = running_flag[0]
        self.proxy = proxy
        self.text = text
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.reply_to_all = reply_to_all
        self.mutex = QMutex()
        self._is_stopping = False
        self.thread_manager = ThreadManager(self)
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
        self.thread_manager.clear_completed()
        for i, token in enumerate(self.tokens):
            thread = BotWorker(
                token=token,
                proxy=self.proxy,
                text=self.text,
                min_delay=self.min_interval,
                max_delay=self.max_interval,
                reply_to_all=self.reply_to_all,
                parent=None
            )
            thread.log_signal.connect(self.log_signal.emit)
            thread.error_signal.connect(self.error_signal.emit)
            thread.stats_signal.connect(self.update_stats)
            thread.finished_signal.connect(self.on_thread_finished)
            self.thread_manager.add_thread(thread)
            progress = min(75, 50 + int((i + 1) / len(self.tokens) * 25))
            self.safe_emit(self.progress_signal, progress, f"Запуск ботов {i+1}/{len(self.tokens)}...")
        for thread in self.thread_manager.threads:
            self.thread_manager.start_thread(thread)
        self.safe_emit(self.log_signal, f"Всего запущено ботов: {self.thread_manager.get_total_count()}")
    def on_thread_finished(self, token, username, *args):
        if username == "unknown":
            self.safe_emit(self.log_signal, f"Бот с токеном {token[:10]}... завершил работу")
        else:
            self.safe_emit(self.log_signal, f"Бот {username} завершил работу")
    def check_threads(self, *args):
        if not self.running_flag or self._is_stopping:
            return
        active_threads = self.thread_manager.active_threads
        authorized_threads = []
        for thread in active_threads:
            if getattr(thread, 'bot_username', 'unknown') != "unknown":
                authorized_threads.append(thread)
                self.bot_usernames[thread.token] = thread.bot_username
        total_bots = self.thread_manager.get_total_count()
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
    def stop(self, *args):
        """Неблокирующая остановка по образцу ThreadStopMixin"""
        if self._is_stopping:
            return
        self.safe_emit(self.log_signal, "⏹️ Начинаем остановку всех ботов...")
        self._is_stopping = True
        self.running_flag = False
        
        try:
            # Останавливаем таймер
            if hasattr(self, 'check_timer') and self.check_timer.isActive():
                self.check_timer.stop()
            
            # Используем стандартный ThreadManager для остановки
            self.thread_manager.stop_all_threads()
            
            # Быстрая очистка без блокирующих операций
            self.start_count.clear()
            self.reply_count.clear()
            self.premium_count.clear()
            self.bot_usernames.clear()
            BotWorker._active_bots.clear()
            
            self.safe_emit(self.log_signal, "✅ Все боты успешно остановлены")
            
        except Exception as e:
            self.safe_emit(self.log_signal, f"❌ Ошибка при остановке ботов: {e}")
        finally:
            self._is_stopping = False

class BotWindow(QWidget, ThreadStopMixin):
    def __init__(self, parent=None, *args):
        super().__init__(parent, *args)
        ThreadStopMixin.__init__(self)
        self.main_window = parent
        self._error_log_path = None
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
        self.reply_to_all_checkbox = QCheckBox("Отвечать на все сообщения (общий флаг)")
        self.reply_to_all_checkbox.setChecked(True)
        left_layout.addWidget(self.reply_to_all_checkbox)
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
        self.auto_reply_worker = None
        self.text_content = None
        self.proxies_list = []
        self.proxy_txt_path = None
        self.selected_tokens = []
    
    def _on_thread_finished(self, thread, *args):
        """Обработчик завершения потока для ThreadStopMixin"""
        pass
    
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
            min_delay_str = self.min_interval_input.text()
            max_delay_str = self.max_interval_input.text()
            min_delay = int(min_delay_str) if min_delay_str else 0
            max_delay = int(max_delay_str) if max_delay_str else 0
            if min_delay < 0 or max_delay < 0:
                raise ValueError("Задержка не может быть отрицательной.")
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
        self.stats_list.clear()
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
            if self.auto_reply_worker is not None:
                self.log_message("Остановка предыдущего процесса...")
                self.progress_widget.update_progress(25, "Остановка предыдущего процесса...")
                try:
                    self.auto_reply_worker.stop()
                    self.auto_reply_worker = None
                except Exception as e:
                    self.log_message(f"Ошибка при остановке предыдущего процесса: {e}")
            self.progress_widget.update_progress(50, "Инициализация ботов...")
            self.auto_reply_worker = AutoReplyAiogramWorker(
                self.selected_tokens, self.running_flag, proxy,
                self.text_content, min_interval, max_interval,
                reply_to_all=self.reply_to_all_checkbox.isChecked()
            )
            self.auto_reply_worker.log_signal.connect(self.log_message)
            self.auto_reply_worker.error_signal.connect(self.handle_thread_error)
            self.auto_reply_worker.stats_signal.connect(self.update_stats)
            self.auto_reply_worker.progress_signal.connect(
                lambda value, text: self.progress_widget.update_progress(value, text)
            )
            total_bots = len(self.selected_tokens)
            self.progress_widget.update_progress(75, f"Запуск {total_bots} ботов...")
            self.auto_reply_worker.run()
            self.progress_widget.update_progress(80, f"Проверка авторизации ботов...")
            self.log_message("Процесс запущен, проверяем авторизацию ботов...")
        except Exception as e:
            self.log_message(f"Критическая ошибка при запуске процесса: {e}")
            self.progress_widget.update_progress(0, "Ошибка запуска")
            self.stop_process()
    def handle_thread_error(self, error_message, *args):
        self.log_message(f"Ошибка: {error_message}")
        try:
            ErrorReportDialog.send_error_report(error_message)
            msg_label = QLabel(f"Произошла ошибка: {error_message}")
            msg_label.setWordWrap(True)
            QTimer.singleShot(100, lambda: self.log_message("Отчет об ошибке отправлен"))
        except Exception as e:
            self.log_message(f"Не удалось отправить отчет об ошибке: {e}")
    def stop_process(self, *args):
        """Остановка процесса по образцу subscribe.py - без блокировки UI"""
        try:
            self.log_message("⏹️ Остановка процесса...")
            self.stop_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.running_flag[0] = False
            self.stop_all_operations()
            if self.auto_reply_worker:
                self.auto_reply_worker.stop()
                self.auto_reply_worker = None
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_widget.update_progress(100, "Процесс остановлен")
            self.log_message("✅ Процесс остановлен, сессии ботов завершены.")
        except Exception as e:
            self.log_message(f"❌ Ошибка при остановке процесса: {e}")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
    def update_stats(self, total_starts, total_replies, *args):
        for i in range(self.stats_list.count()):
            if self.stats_list.item(i).text().startswith("Общая статистика:"):
                self.stats_list.takeItem(i)
                break
        self.stats_list.addItem(f"Общая статистика: /start: {total_starts}, ответов: {total_replies}")
