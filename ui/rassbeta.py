import os, asyncio, json, hashlib, platform, random, string
import aiohttp
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog,
    QCheckBox, QListWidget, QHBoxLayout,
    QSlider, QSizePolicy, QTimeEdit, QGroupBox
)
from aiogram import Bot
from ui.progress import ProgressWidget
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.bots_win import BotTokenWindow
from ui.appchuy import AiogramBotConnection, AiogramErrorHandler, AiogramErrorType
class BotWorker(BaseThread):
    def __init__(self, token, user_ids, message, bot_name, delay_range: tuple = (0.1, 0.3), *args, **kwargs):
        super().__init__(session_file=token, parent=kwargs.get('parent', None))
        self.token = token
        self.user_ids = user_ids
        self.message = message
        self.bot_name = bot_name
        self.delay_range = tuple(delay_range)
        self.bot_manager = AiogramBotConnection(token)
        self.bot_manager.log_signal.connect(self.log_signal.emit)
        self.bot_manager.error_signal.connect(self.handle_error)
    def handle_error(self, token, error):
        self.log_signal.emit(f"{token}: {error.message}")
    async def process(self, *args, **kwargs):
        try:
            bot = await self.bot_manager.connect()
            if not await self.bot_manager.check_connection():
                await self.bot_manager.disconnect()
                return
            sent_counter = {'sent': 0}
            total = len(self.user_ids)
            rate_limit = 10
            min_interval = 0.2
            queue = asyncio.Queue()
            for user_id in self.user_ids:
                await queue.put(user_id)
            async def worker():
                while not queue.empty() and self.running:
                    user_id = await queue.get()
                    if not await self.bot_manager.check_connection():
                        break
                    random_text = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    try:
                        await bot.send_message(user_id, self.message or random_text)
                        sent_counter['sent'] += 1
                        progress = int((sent_counter['sent'] / total) * 100)
                        self.emit_progress(progress, f"Отправка сообщений ботом {self.bot_name}: {sent_counter['sent']}/{total}")
                        self.emit_log(f"PROGRESS::{self.bot_name}::{sent_counter['sent']}::{total}")
                    except Exception as e:
                        err = AiogramErrorHandler.classify_error(e, user_id=user_id, username=self.bot_name)
                        msg = AiogramErrorHandler.format_error_message(self.token, err)
                        self.emit_log(f"{msg}")
                        if err.type in [AiogramErrorType.CONNECTION, AiogramErrorType.SSL_ERROR, AiogramErrorType.BAD_GATEWAY]:
                            await self.bot_manager.check_connection()
                        progress = int((sent_counter['sent'] / total) * 100)
                        self.emit_progress(progress, f"Отправка сообщений ботом {self.bot_name}: {sent_counter['sent']}/{total}")
                        self.emit_log(f"PROGRESS::{self.bot_name}::{sent_counter['sent']}::{total}")
                    await asyncio.sleep(min_interval)
                    queue.task_done()
            workers = [asyncio.create_task(worker()) for _ in range(rate_limit)]
            await queue.join()
            for w in workers:
                w.cancel()
            await self.bot_manager.disconnect()
            sent = sent_counter['sent']
            failed = total - sent
            self.emit_log(f"{self.bot_name}: завершено, всего: {sent}, ошибок: {failed}")
        except Exception as e:
            self.emit_log(f"❌ Бот {self.bot_name}: критическая ошибка: {e}")
            try:
                await self.bot_manager.disconnect()
            except Exception:
                pass
            self.emit_log(f"{self.bot_name}: завершено с ошибкой")
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
            return "http://127.0.0.1:8000"
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
    async def start_rass(self, tokens, users, text, percent, auto, auto_time):
        data = {
            "auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key},
            "tokens": tokens,
            "users": users,
            "text": text,
            "percent": percent,
            "auto": auto,
            "auto_time": auto_time
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/start_rass", json=data) as response:
                return await response.json()
    async def stop_rass(self):
        data = {"auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key}}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/stop_rass", json=data) as response:
                return await response.json()
    async def get_status(self):
        async with aiohttp.ClientSession() as session:
            url = f"{self.server_url}/status/{self.ssh_key}/{self.activation_key}"
            async with session.get(url) as response:
                return await response.json()
    async def get_users(self):
        async with aiohttp.ClientSession() as session:
            url = f"{self.server_url}/users/{self.ssh_key}/{self.activation_key}"
            async with session.get(url) as response:
                return await response.json()
    async def set_auto(self, auto_time):
        data = {"auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key}, "auto_time": auto_time}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/set_auto", json=data) as response:
                return await response.json()
    async def unset_auto(self):
        data = {"auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key}}
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.server_url}/unset_auto", json=data) as response:
                return await response.json()
class RassWindow(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.setWindowTitle("Рассылка")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QHBoxLayout(self)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_layout.setContentsMargins(10, 10, 10, 10)
        load_layout = QHBoxLayout()
        self.users_button = QPushButton("📁 Загрузить папку c юзерами")
        self.users_button.clicked.connect(self.load_users_folder)
        load_layout.addWidget(self.users_button)
        left_layout.addLayout(load_layout)
        auto_layout = QHBoxLayout()
        self.auto_send_checkbox = QCheckBox("⏰ Авторассылка")
        auto_layout.addWidget(self.auto_send_checkbox)
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Время:"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setFixedWidth(80)
        self.time_edit.setAlignment(Qt.AlignmentFlag.AlignLeft)
        time_layout.addWidget(self.time_edit)
        time_layout.addStretch()
        auto_layout.addLayout(time_layout)
        left_layout.addLayout(auto_layout)
        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText("✍️ Введите текст рассылки...")
        left_layout.addWidget(self.message_edit)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("▶ Начать рассылку")
        self.start_button.clicked.connect(self.start_broadcast)
        button_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.clicked.connect(self.stop_all)
        button_layout.addWidget(self.stop_button)
        left_layout.addLayout(button_layout)
        slider_container = QHBoxLayout()
        slider_label = QLabel("📊 Процент рассылки:")
        slider_container.addWidget(slider_label)
        self.percent_slider = QSlider(Qt.Orientation.Horizontal)
        self.percent_slider.setMinimum(0)
        self.percent_slider.setMaximum(100)
        self.percent_slider.setValue(100)
        self.percent_slider.setTickInterval(10)
        self.percent_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.percent_slider.setPageStep(10)
        self.percent_slider.setFixedWidth(200)
        slider_container.addWidget(self.percent_slider)
        self.percent_label = QLabel("100%")
        self.percent_label.setMinimumWidth(40)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        slider_container.addWidget(self.percent_label)
        slider_container.addStretch()
        self.percent_slider.valueChanged.connect(lambda value: self.percent_label.setText(f"{value}%"))
        left_layout.addLayout(slider_container)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output, stretch=2)
        left_layout.addWidget(QLabel("📊 Статистика ботов:"))
        self.stats_list = QListWidget()
        left_layout.addWidget(self.stats_list)
        self.progress_widget = ProgressWidget(self)
        left_layout.addWidget(self.progress_widget)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("✓ Выберите ботов:"))
        self.bot_token_window = BotTokenWindow(token_folder_path=self.parent().bot_token_folder if self.parent() else self.bot_token_folder)
        self.bot_token_window.tokens_updated.connect(self.on_bots_win_tokens_updated)
        self.bot_token_window.files_updated.connect(self.on_bots_win_files_updated)
        right_layout.addWidget(self.bot_token_window)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addLayout(right_layout, 1)
        self.tokens = {}
        self.users = {}
        self.total_users = 0
        self.total_processed = 0
        self.selected_tokens = []
        self.token_usernames = {}
        self.api_client = ServerApiClient()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_server_status)
        self.status_timer.start(1000)
        self.is_broadcasting = False
        self.last_auto_send_date = None
    def on_bots_win_tokens_updated(self, tokens, *args):
        self.selected_tokens = tokens
        self.tokens = {t: self.bot_token_window.token_usernames.get(t, t) for t in tokens}
    def on_bots_win_files_updated(self, files):
        pass
    def update_log_output(self, message, *args):
        if message.startswith("PROGRESS::"):
            _, bot_name, processed, total = message.split("::")
            processed = int(processed)
            total = int(total)
            for i in range(self.stats_list.count()):
                item = self.stats_list.item(i)
                if item.text().startswith(f"{bot_name}:"):
                    item.setText(f"{bot_name}: обработано {processed}/{total}")
                    break
            self.total_processed += 1
            if self.total_users > 0:
                progress = int((self.total_processed / self.total_users) * 100)
                self.progress_widget.update_progress(progress, f"Общий прогресс: {self.total_processed}/{self.total_users}")
        else:
            self.log_output.append(message)
    async def fetch_usernames_for_tokens(self, tokens, *args):
        for token in tokens:
            if token in self.token_usernames:
                continue
            try:
                conn = AiogramBotConnection(token)
                bot = await conn.connect()
                info = await bot.get_me()
                username = info.username or token[:10]
                self.token_usernames[token] = username
                await conn.disconnect()
            except Exception as e:
                self.token_usernames[token] = token[:10]
    def load_users_from_folder(self, folder, *args):
        if not folder:
            return False
        self.users.clear()
        selected_tokens = set(self.selected_tokens)
        if not selected_tokens:
            self.log_output.append("⛔ Не выбрано ни одного бота.")
            return False
        found_any = False
        tokens_to_fetch = []
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "r") as f:
                    lines = f.read().splitlines()
                    if not lines:
                        continue
                    token = lines[0].strip()
                    if token not in selected_tokens:
                        continue
                    user_ids = [int(line) for line in lines[1:] if line.isdigit()]
                    if user_ids:
                        self.users[token] = user_ids
                        tokens_to_fetch.append(token)
                        found_any = True
                    else:
                        self.log_output.append(f"⚠️ {token[:10]}: нет пользователей для рассылки.")
            except Exception as e:
                self.log_output.append(f"❌ Ошибка при чтении файла {file_path}: {e}")
                continue
        if tokens_to_fetch:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.fetch_usernames_for_tokens(tokens_to_fetch))
                self.log_output.append("Загрузка.")
            else:
                loop.run_until_complete(self.fetch_usernames_for_tokens(tokens_to_fetch))
        if found_any:
            self.log_output.append("✅ Папка с пользователями загружена успешно.")
            return True
        else:
            self.log_output.append("⚠️ Не удалось загрузить пользователей ни для одного бота.")
            return False
    def load_users_folder(self, *args):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с пользователями")
        if not folder:
            return
        self.load_users_from_folder(folder)
        self.session_folder = folder
    def start_broadcast(self, *args, auto=False):
        if not self.selected_tokens:
            self.log_output.append("⛔ Выберите хотя бы одного бота для рассылки")
            return
        if not self.users:
            self.log_output.append("⛔ Загрузите список пользователей")
            return
        message_text = self.message_edit.toPlainText().strip()
        percent = self.percent_slider.value()
        auto_flag = self.auto_send_checkbox.isChecked()
        auto_time = self.time_edit.time().toString("HH:mm") if auto_flag else None
        asyncio.create_task(self._start_broadcast_on_server(message_text, percent, auto_flag, auto_time))
    async def _start_broadcast_on_server(self, message_text, percent, auto_flag, auto_time):
        self.log_output.clear()
        self.log_output.append("✅ Запрос на запуск рассылки отправлен на сервер...")
        resp = await self.api_client.start_rass(self.selected_tokens, self.users, message_text, percent, auto_flag, auto_time)
        self.log_output.append(str(resp))
        self.is_broadcasting = True
    def stop_all(self, *args):
        asyncio.create_task(self._stop_broadcast_on_server())
    async def _stop_broadcast_on_server(self):
        self.log_output.append("⏹️ Остановка рассылки...")
        resp = await self.api_client.stop_rass()
        self.log_output.append(str(resp))
        self.is_broadcasting = False
    def check_server_status(self, *args):
        asyncio.create_task(self._update_server_status())
    async def _update_server_status(self, *args):
        try:
            status_response = await self.api_client.get_status()
            stats = status_response.get('stats', {})
            self.stats_list.clear()
            total_sent = 0
            total_total = 0
            for token, stat in stats.items():
                sent = stat.get('sent', 0)
                total = stat.get('total', 0)
                running = stat.get('running', False)
                auto = stat.get('auto', False)
                self.stats_list.addItem(f"{token[:10]}: отправлено {sent}/{total} | {'Авто' if auto else 'Обычная'} | {'В процессе' if running else 'Остановлен'}")
                total_sent += sent
                total_total += total
            if total_total > 0:
                progress = int((total_sent / total_total) * 100)
                self.progress_widget.update_progress(progress, f"Общий прогресс: {total_sent}/{total_total}")
            else:
                self.progress_widget.update_progress(0, "Нет активных рассылок")
        except Exception as e:
            self.log_output.append(f"Ошибка получения статуса: {e}")