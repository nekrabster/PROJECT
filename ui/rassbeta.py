import os, asyncio, random, string
import aiohttp
import asyncio
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog,
    QCheckBox, QListWidget, QHBoxLayout,
    QSlider, QSizePolicy, QTimeEdit, QGroupBox
)
from aiogram import Bot
from ui.progress import ProgressWidget
import platform
from ui.thread_base import ThreadStopMixin
from ui.bots_win import BotTokenWindow

class RassylkaApiClient:
    def __init__(self, server_url="http://127.0.0.1:8001"):
        self.server_url = server_url
        self.ssh_key = self.get_ssh_key()
        self.activation_key = self.get_activation_key()

    def get_ssh_key(self):
        try:
            ssh_key_file = os.path.expanduser("~/.ssh/id_rsa.pub")
            if os.path.exists(ssh_key_file):
                with open(ssh_key_file, 'r') as f:
                    return f.read().strip()
        except Exception:
            pass
        return platform.node()

    def get_activation_key(self):
        try:
            with open("config.txt", 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('key='):
                        return line.strip().split('=', 1)[1]
        except Exception:
            return "default_key"

    async def start_rassylka(self, users_data, message, percent, auto, auto_time):
        payload = {
            "auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key},
            "users_data": users_data,
            "message": message,
            "percent": percent,
            "auto": auto,
            "auto_time": auto_time
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.server_url}/start_rassylka", json=payload, timeout=10) as response:
                    return await response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def stop_rassylka(self):
        payload = {"auth": {"ssh_key": self.ssh_key, "activation_key": self.activation_key}}
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.server_url}/stop_rassylka", json=payload, timeout=10) as response:
                    return await response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def get_status(self):
        url = f"{self.server_url}/status/{self.ssh_key}/{self.activation_key}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        return await response.json()
                    return {"status": "error", "message": f"Server error: {response.status}"}
            except Exception as e:
                return {"status": "offline", "message": str(e)}
class RassWindowBeta(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.api_client = RassylkaApiClient()
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
        self.is_broadcasting = False
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_server_status)
        self.status_timer.start(3000)
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
        asyncio.ensure_future(self.bot_token_window.fetch_usernames_for_tokens(tokens_to_fetch))
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

    def start_broadcast(self):
        if self.is_broadcasting:
            self.log_output.append("⛔ Рассылка уже идёт!")
            return
        if not self.selected_tokens:
            self.log_output.append("⛔ Выберите хотя бы одного бота для рассылки")
            return
        if not self.users:
            self.log_output.append("⛔ Загрузите список пользователей")
            return
        message_text = self.message_edit.toPlainText().strip()
        is_auto = self.auto_send_checkbox.isChecked()
        if not message_text and not is_auto:
            self.log_output.append("⛔ Введите текст сообщения или включите авторассылку для случайного текста")
            return
        self.log_output.clear()
        self.log_output.append("✅ Отправка запроса на сервер...")
        self.is_broadcasting = True
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)
        users_data_to_send = {token: self.users.get(token, []) for token in self.selected_tokens}
        auto_time_str = self.time_edit.time().toString("HH:mm")
        percent = self.percent_slider.value()
        asyncio.ensure_future(self.api_client.start_rassylka(
            users_data=users_data_to_send,
            message=message_text,
            percent=percent,
            auto=is_auto,
            auto_time=auto_time_str
        ))
    def stop_all(self):
        self.log_output.append("✅ Отправка команды остановки на сервер...")
        asyncio.ensure_future(self.api_client.stop_rassylka())
        self.is_broadcasting = False
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)

    def update_progress(self, value: int, status_text: str, *args, **kwargs):
        self.progress_widget.progress_bar.setValue(value)
        self.progress_widget.status_label.setText(status_text)

    def check_server_status(self):
        asyncio.ensure_future(self._check_server_status())

    async def _check_server_status(self):
        status = await self.api_client.get_status()
        if status.get("status") == "offline":
            self.stats_list.clear()
            self.stats_list.addItem(f"Сервер недоступен: {status.get('message')}")
            self.is_broadcasting = False
            return

        tasks = status.get("tasks", {})
        self.stats_list.clear()
        total_sent = 0
        total_failed = 0
        total_overall = 0
        is_running = status.get("status") == "running"

        if not tasks and not is_running:
            self.stats_list.addItem("Нет активных задач на сервере.")

        for bot_name, stats in tasks.items():
            self.stats_list.addItem(f"{bot_name}: {stats['sent']}/{stats['total']} (Ошибок: {stats['failed']})")
            total_sent += stats['sent']
            total_failed += stats['failed']
            total_overall += stats['total']

        if total_overall > 0:
            progress = int(((total_sent + total_failed) / total_overall) * 100)
            self.progress_widget.update_progress(progress, f"Общий прогресс: {total_sent + total_failed} / {total_overall}")
        else:
            self.progress_widget.update_progress(0, "Ожидание задач...")

        self.is_broadcasting = is_running
        self.start_button.setDisabled(self.is_broadcasting)
        self.stop_button.setDisabled(not self.is_broadcasting)

        autoschedule = status.get("autoschedule", {})
        if autoschedule.get("auto"):
            self.auto_send_checkbox.setChecked(True)
            self.time_edit.setTime(QTime.fromString(autoschedule.get("auto_time", "00:00"), "HH:mm"))
        else:
            self.auto_send_checkbox.setChecked(False)

