import os, asyncio, random, string, json, hashlib, platform
import aiofiles
import aiofiles.os as aio_os
import aiohttp
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
            import sys
            if hasattr(sys, 'frozen') and sys.frozen:
                project_root = os.path.dirname(sys.executable)
            else:
                try:
                    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                except Exception:
                    project_root = os.getcwd()
            users_folder = os.path.join(project_root, "users_bot")
            try:
                await aio_os.makedirs(users_folder, exist_ok=True)
            except Exception:
                os.makedirs(users_folder, exist_ok=True)
            safe_bot_name = "".join(c for c in self.bot_username if c.isalnum() or c in ('_', '-'))
            users_file_path = os.path.join(users_folder, f"{safe_bot_name}.txt")
            existing_ids = set()
            try:
                file_exists = await aio_os.path.exists(users_file_path)
            except Exception:
                file_exists = os.path.exists(users_file_path)
            if file_exists:
                try:
                    async with aiofiles.open(users_file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                    lines = content.splitlines()
                    existing_ids = set(line.strip() for line in lines[1:] if line.strip())
                except Exception:
                    pass
            user_id_str = str(user_id)
            if user_id_str not in existing_ids:
                try:
                    async with aiofiles.open(users_file_path, 'a', encoding='utf-8') as f:
                        if not file_exists:
                            await f.write(f"{self.token}\n")
                        await f.write(f"{user_id_str}\n")
                except Exception:
                    try:
                        with open(users_file_path, 'a', encoding='utf-8') as f:
                            if not file_exists:
                                f.write(f"{self.token}\n")
                            f.write(f"{user_id_str}\n")
                            f.flush()
                    except Exception as e:
                        self.safe_emit(self.error_signal, f"Ошибка записи файла {users_file_path}: {e}")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка сохранения user_id для {self.bot_username}: {e}")
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
class ServerApiClient:
    def __init__(self, server_url=None):
        if server_url is None:
            server_url = self.get_server_url()
        self.server_url = server_url
        self.ssh_key = self.get_ssh_key()
        self.activation_key = self.get_activation_key()
    def get_server_url(self, *args):
        try:
            with open("server_port.txt", 'r') as f:
                content = f.read().strip()
                if content.startswith('http'):
                    return content
                else:
                    port = content
                    return f"http://localhost:{port}"
        except Exception:
            return "http://5.129.207.183:8000"
    def get_ssh_key(self, *args):
        try:
            ssh_key_file = os.path.expanduser("~/.ssh/id_rsa.pub")
            if os.path.exists(ssh_key_file):
                with open(ssh_key_file, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return platform.node()
    def get_activation_key(self, *args):
        try:
            config_path = "config.txt"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('key='):
                            return line.strip().split('=', 1)[1]
        except Exception:
            pass
        return "default_key"
    async def start_bots(self, tokens, text=None, min_delay=0, max_delay=0, reply_to_all=True, proxy=None, *args):
        data = {
            "auth": {
                "ssh_key": self.ssh_key,
                "activation_key": self.activation_key
            },
            "tokens": tokens,
            "text": text,
            "min_delay": min_delay,
            "max_delay": max_delay,
            "reply_to_all": reply_to_all,
            "proxy": proxy
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/start_bots", json=data) as response:
                return await response.json()    
    async def stop_bots(self, *args):
        data = {
            "auth": {
                "ssh_key": self.ssh_key,
                "activation_key": self.activation_key
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/stop_bots", json=data) as response:
                return await response.json()    
    async def get_status(self, *args):
        async with aiohttp.ClientSession() as session:
            url = f"{self.server_url}/status/{self.ssh_key}/{self.activation_key}"
            async with session.get(url) as response:
                return await response.json()    
    async def get_users(self, *args):
        async with aiohttp.ClientSession() as session:
            url = f"{self.server_url}/users/{self.ssh_key}/{self.activation_key}"
            async with session.get(url) as response:
                return await response.json()
class AutoReplyAiogramWorker(QObject):
    log_signal = pyqtSignal(str)
    stats_signal = pyqtSignal(int, int)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    bot_stats_signal = pyqtSignal(str, int, int, int)
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
        self.api_client = ServerApiClient()
        self.start_count = {}
        self.reply_count = {}
        self.premium_count = {}
        self.bot_usernames = {}
        self.last_status_text = None
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_server_status)
        self.check_timer.start(1000)
    def safe_emit(self, signal, *args, **kwargs):
        with QMutexLocker(self.mutex):
            signal.emit(*args)
    def update_stats(self, bot_username, start_count, reply_count, premium_count, *args, **kwargs):
        with QMutexLocker(self.mutex):
            self.start_count[bot_username] = start_count
            self.reply_count[bot_username] = reply_count
            self.premium_count[bot_username] = premium_count
            total_starts = sum(self.start_count.values())
            total_replies = sum(self.reply_count.values())
            self.stats_signal.emit(total_starts, total_replies)
    def run(self, *args, **kwargs):
        if self._is_stopping:
            return
        self.running_flag = True
        self.safe_emit(self.log_signal, "Отправка запроса на сервер для запуска ботов...")
        asyncio.create_task(self._start_bots_on_server())
    async def _start_bots_on_server(self, *args, **kwargs):
        try:
            self.safe_emit(self.progress_signal, 25, "Подключение к серверу...")
            response = await self.api_client.start_bots(
                tokens=self.tokens,
                text=self.text,
                min_delay=self.min_interval,
                max_delay=self.max_interval,
                reply_to_all=self.reply_to_all,
                proxy=self.proxy
            )
            if response.get('status') == 'success':
                self.safe_emit(self.log_signal, f"✅ Боты отправлены на сервер: {response.get('message')}")
                self.safe_emit(self.progress_signal, 75, "Боты запускаются на сервере...")
            else:
                self.safe_emit(self.error_signal, f"Ошибка сервера: {response}")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка подключения к серверу: {e}")
    def on_thread_finished(self, token, username, *args, **kwargs):
        if username == "unknown":
            self.safe_emit(self.log_signal, f"Бот с токеном {token[:10]}... завершил работу")
        else:
            self.safe_emit(self.log_signal, f"Бот {username} завершил работу")
    def check_server_status(self, *args, **kwargs):
        if not self.running_flag or self._is_stopping:
            return
        asyncio.create_task(self._update_server_status())
    async def _update_server_status(self, *args, **kwargs):
        try:
            status_response = await self.api_client.get_status()
            active_bots = status_response.get('active_bots', 0)
            stats = status_response.get('stats', {}) 
            total_starts = sum(stat.get('start_count', 0) for stat in stats.values())
            total_replies = sum(stat.get('reply_count', 0) for stat in stats.values())
            self.stats_signal.emit(total_starts, total_replies)
            for bot_username, bot_stats in stats.items():
                start_count = bot_stats.get('start_count', 0)
                reply_count = bot_stats.get('reply_count', 0)
                premium_count = bot_stats.get('premium_count', 0)
                self.bot_stats_signal.emit(bot_username, start_count, reply_count, premium_count)
            if active_bots > 0:
                status_text = f"Активно на сервере: {active_bots} ботов"
                progress = 100
            else:
                status_text = "Боты не активны на сервере"
                progress = 0
            if status_text != self.last_status_text:
                self.safe_emit(self.log_signal, status_text)
                self.last_status_text = status_text            
            self.safe_emit(self.progress_signal, progress, status_text)
        except Exception as e:
            error_msg = str(e).lower()
            if "connection" in error_msg or "timeout" in error_msg:
                if self.last_status_text != "⚠️ Соединение с сервером потеряно":
                    self.safe_emit(self.log_signal, "⚠️ Соединение с сервером потеряно")
                    self.last_status_text = "⚠️ Соединение с сервером потеряно"
    def stop(self, *args):
        if self._is_stopping:
            return
        self.safe_emit(self.log_signal, "⏹️ Отправка команды остановки на сервер...")
        self._is_stopping = True
        self.running_flag = False
        asyncio.create_task(self._stop_bots_on_server())
    async def _stop_bots_on_server(self, *args, **kwargs):
        try:
            if hasattr(self, 'check_timer') and self.check_timer.isActive():
                self.check_timer.stop()
            response = await self.api_client.stop_bots()
            if response.get('status') == 'success':
                self.safe_emit(self.log_signal, "✅ Боты остановлены на сервере")
                await self._download_users_from_server()
            else:
                self.safe_emit(self.log_signal, f"❌ Ошибка остановки: {response}")
            self.start_count.clear()
            self.reply_count.clear()
            self.premium_count.clear()
            self.bot_usernames.clear()
        except Exception as e:
            self.safe_emit(self.log_signal, f"❌ Ошибка при остановке ботов: {e}")
        finally:
            self._is_stopping = False
    async def _download_users_from_server(self, *args, **kwargs):
        try:
            users_response = await self.api_client.get_users()
            users_data = users_response.get('users', {})
            if users_data:
                self.safe_emit(self.log_signal, "📥 Скачивание пользователей с сервера...")
                import sys
                if hasattr(sys, 'frozen') and sys.frozen:
                    project_root = os.path.dirname(sys.executable)
                else:
                    try:
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    except Exception:
                        project_root = os.getcwd()  
                users_folder = os.path.join(project_root, "users_bot")
                os.makedirs(users_folder, exist_ok=True)
                for bot_username, user_ids in users_data.items():
                    if user_ids:
                        safe_bot_name = "".join(c for c in bot_username if c.isalnum() or c in ('_', '-'))
                        users_file_path = os.path.join(users_folder, f"{safe_bot_name}.txt")   
                        existing_ids = set()
                        if os.path.exists(users_file_path):
                            with open(users_file_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                if lines:
                                    existing_ids = set(line.strip() for line in lines[1:] if line.strip())     
                        new_users = set(str(uid) for uid in user_ids) - existing_ids
                        if new_users:
                            with open(users_file_path, 'a', encoding='utf-8') as f:
                                for user_id in new_users:
                                    f.write(f"{user_id}\n")
                        self.safe_emit(self.log_signal, f"📥 {bot_username}: добавлено {len(new_users)} новых пользователей")
                self.safe_emit(self.log_signal, "✅ Пользователи успешно скачаны и сохранены")
        except Exception as e:
            self.safe_emit(self.log_signal, f"❌ Ошибка скачивания пользователей: {e}")
class BotWindowBeta (QWidget, ThreadStopMixin):
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
        self.api_client = ServerApiClient()
        self.startup_timer = QTimer(self)
        self.startup_timer.timeout.connect(self.check_server_on_startup)
        self.startup_timer.setSingleShot(True)
        self.startup_timer.start(2000)
    def check_server_on_startup(self, *args, **kwargs):
        asyncio.create_task(self._check_existing_bots())
    async def _check_existing_bots(self, *args, **kwargs):
        try:
            self.log_message("🔍 Проверка состояния ботов на сервере...")
            status_response = await self.api_client.get_status()
            active_bots = status_response.get('active_bots', 0)
            if active_bots > 0:
                self.log_message(f"🔄 Найдено {active_bots} активных ботов на сервере")
                self.running_flag[0] = True
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                if not self.auto_reply_worker:
                    self.auto_reply_worker = AutoReplyAiogramWorker(
                        [], self.running_flag, None, None, 0, 0, True
                    )
                    self.auto_reply_worker.log_signal.connect(self.log_message)
                    self.auto_reply_worker.stats_signal.connect(self.update_stats)
                    self.auto_reply_worker.bot_stats_signal.connect(self.update_bot_stats)
                await self._download_users_from_server()
                self.log_message("✅ Подключение к существующим ботам восстановлено")
            else:
                self.log_message("ℹ️ Активных ботов на сервере не найдено")
        except Exception as e:
            self.log_message(f"⚠️ Не удалось подключиться к серверу: {e}")
    async def _download_users_from_server(self, *args, **kwargs):
        try:
            users_response = await self.api_client.get_users()
            users_data = users_response.get('users', {})            
            if users_data:
                import sys
                if hasattr(sys, 'frozen') and sys.frozen:
                    project_root = os.path.dirname(sys.executable)
                else:
                    try:
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    except Exception:
                        project_root = os.getcwd()
                users_folder = os.path.join(project_root, "users_bot")
                os.makedirs(users_folder, exist_ok=True)
                for bot_username, user_ids in users_data.items():
                    if user_ids:
                        safe_bot_name = "".join(c for c in bot_username if c.isalnum() or c in ('_', '-'))
                        users_file_path = os.path.join(users_folder, f"{safe_bot_name}.txt")                        
                        existing_ids = set()
                        if os.path.exists(users_file_path):
                            with open(users_file_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                if lines:
                                    existing_ids = set(line.strip() for line in lines[1:] if line.strip())
                        new_users = set(str(uid) for uid in user_ids) - existing_ids
                        if new_users:
                            with open(users_file_path, 'a', encoding='utf-8') as f:
                                for user_id in new_users:
                                    f.write(f"{user_id}\n")
        except Exception:
            pass
    def _on_thread_finished(self, thread, *args, **kwargs):
        pass
    def on_bots_win_tokens_updated(self, tokens, *args, **kwargs):
        if len(tokens) != len(self.selected_tokens):
            self.selected_tokens = tokens
            self.log_message(f"✓ Выбрано ботов: {len(tokens)}")
        else:
            self.selected_tokens = tokens
    def on_bots_win_files_updated(self, files, *args, **kwargs):
        pass
    def log_message(self, message, *args, **kwargs):
        if "— получил /start" in message:
            bot_name = message.split(" — ")[0]
            updated = False
            for i in range(self.stats_list.count()):
                item = self.stats_list.item(i)
                if item.text().startswith(bot_name):
                    item.setText(message)
                    updated = True
                    break
            if not updated:
                self.stats_list.addItem(message)
        else:
            self.log_output.append(message)
    def load_text_file(self, *args, **kwargs):
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
    def get_delay_range(self, *args, **kwargs):
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
    def on_use_proxy_txt_toggled(self, checked, *args, **kwargs):
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
    def start_process(self, *args, **kwargs):
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
            self.auto_reply_worker.bot_stats_signal.connect(self.update_bot_stats)
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
    def handle_thread_error(self, error_message, *args, **kwargs):
        self.log_message(f"Ошибка: {error_message}")
        try:
            ErrorReportDialog.send_error_report(error_message)
            msg_label = QLabel(f"Произошла ошибка: {error_message}")
            msg_label.setWordWrap(True)
            QTimer.singleShot(100, lambda: self.log_message("Отчет об ошибке отправлен"))
        except Exception as e:
            self.log_message(f"Не удалось отправить отчет об ошибке: {e}")
    def stop_process(self, *args):
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
    def update_bot_stats(self, bot_username, start_count, reply_count, premium_count, *args):
        stat_message = f"{bot_username} — получил /start ({start_count}) / сообщение ({start_count}) / автоответов отправлено ({reply_count}) / Премиум: {premium_count}"
        updated = False
        for i in range(self.stats_list.count()):
            item = self.stats_list.item(i)
            if item.text().startswith(bot_username):
                item.setText(stat_message)
                updated = True
                break
        if not updated:
            self.stats_list.addItem(stat_message)
    def update_stats(self, total_starts, total_replies, *args):
        for i in range(self.stats_list.count()):
            if self.stats_list.item(i).text().startswith("Общая статистика:"):
                self.stats_list.takeItem(i)
                break
        self.stats_list.addItem(f"Общая статистика: /start: {total_starts}, ответов: {total_replies}")
