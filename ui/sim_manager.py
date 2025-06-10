import os, io, re, json, asyncio, random, string, inspect
from typing import Optional, Dict, List, Any
from PIL import Image
from faker import Faker
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QFileDialog, QLabel, QCheckBox, QMessageBox,
    QSizePolicy, QGroupBox, QLineEdit, QInputDialog
)
from telethon.errors import (
    FloodWaitError, PasswordHashInvalidError
)
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from ui.loader import load_config, load_proxy
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection, TelegramErrorType,
    TelegramError
)
from datetime import datetime
from ui.thread_base import ThreadStopMixin, BaseThread
def update_session_json(session_path, **kwargs):
    json_path = session_path.replace('.session', '.json')
    log_func = None
    frame = inspect.currentframe()
    while frame:
        if 'self' in frame.f_locals and hasattr(frame.f_locals['self'], 'log_signal'):
            log_func = lambda msg: frame.f_locals['self'].log_signal.emit(msg)
            break
        frame = frame.f_back
    if log_func is None:
        log_func = print
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'twoFA' in kwargs:
            data['twoFA'] = kwargs['twoFA']
        for k, v in kwargs.items():
            if k != 'twoFA':
                data[k] = v
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        pass
class SimManagerWindow(QDialog, ThreadStopMixin):
    def __init__(self, session_folder, selected_sessions=None, parent=None):
        super().__init__(parent)
        ThreadStopMixin.__init__(self)
        self.session_folder = session_folder
        self.selected_sessions = selected_sessions or []
        self.completed_sessions = set()
        self.total_sessions = len(self.selected_sessions)
        self.active_param = None
        self.running = False
        self._is_closing = False
        self.report_shown = False
        self.verify_session_paths()
        self.setup_ui()
        config = load_config()
        self.proxy = load_proxy(config) if config else None
        if self.selected_sessions:
            if len(self.selected_sessions) == 1:
                self.log_area.append(f"✏️ Редактирование сессии: {os.path.basename(self.selected_sessions[0])}")
            else:
                self.log_area.append(f"📝 Выбрано сессий для редактирования: {len(self.selected_sessions)}")
    def verify_session_paths(self, *args, **kwargs):
        verified_sessions = []
        for session_path in self.selected_sessions:
            if not os.path.isabs(session_path):
                session_path = os.path.join(self.session_folder, session_path)
            if os.path.exists(session_path):
                verified_sessions.append(session_path)
        else:
            print(f"Файл сессии не найден: {session_path}")
        self.selected_sessions = verified_sessions
        self.total_sessions = len(self.selected_sessions)
    def setup_ui(self, *args, **kwargs):
        main_layout = QVBoxLayout(self)
        self.setWindowTitle("Редактор профилей")
        if len(self.selected_sessions) == 1:
            self.setWindowTitle(f"Редактор профиля: {os.path.basename(self.selected_sessions[0])}")
        self.setMinimumWidth(900)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        global_controls_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси")
        global_controls_layout.addWidget(self.use_proxy_checkbox)
        global_controls_layout.addStretch(1)
        main_layout.addLayout(global_controls_layout)
        profile_editing_group = QGroupBox("Редактирование параметров профиля")
        profile_editing_layout = QVBoxLayout()
        buttons_row1 = QHBoxLayout()
        self.change_name_btn = QPushButton("Изменить имя")
        self.change_lastname_btn = QPushButton("Изменить фамилию")
        self.change_bio_btn = QPushButton("Изменить описание")
        buttons_row1.addWidget(self.change_name_btn)
        buttons_row1.addWidget(self.change_lastname_btn)
        buttons_row1.addWidget(self.change_bio_btn)
        profile_editing_layout.addLayout(buttons_row1)
        buttons_row2 = QHBoxLayout()
        self.change_avatar_btn = QPushButton("Изменить аватар")
        self.change_2fa_btn = QPushButton("Изменить 2FA")
        buttons_row2.addWidget(self.change_avatar_btn)
        buttons_row2.addWidget(self.change_2fa_btn)
        profile_editing_layout.addLayout(buttons_row2)
        self.param_input = QLineEdit(self)
        self.param_input.setPlaceholderText("Введите новое значение...")
        profile_editing_layout.addWidget(self.param_input)
        image_folder_layout = QHBoxLayout()
        self.select_image_folder_btn = QPushButton("Выбрать папку для аватаров")
        self.select_image_folder_btn.clicked.connect(self.select_image_folder)
        image_folder_layout.addWidget(self.select_image_folder_btn)
        self.image_folder_label = QLabel("Папка не выбрана")
        image_folder_layout.addWidget(self.image_folder_label)
        image_folder_layout.addStretch(1)
        profile_editing_layout.addLayout(image_folder_layout)
        profile_editing_group.setLayout(profile_editing_layout)
        main_layout.addWidget(profile_editing_group)
        bulk_actions_group = QGroupBox("Массовые действия")
        bulk_actions_layout = QVBoxLayout()
        self.fill_profile_btn = QPushButton("Генерация Профиля")
        self.fill_profile_btn.setObjectName("FillProfileButton")
        self.fill_profile_btn.setIcon(QIcon("icons/icon65.png"))
        gradient_style = """
QPushButton#FillProfileButton {
    background: qradialgradient(
        cx:0.5, cy:0.5, radius: 1,
        stop:0 #FF0000,
        stop:0.2 #FF1493,
        stop:0.4 #FF69B4,
        stop:0.6 #FFB6C1,
        stop:0.8 #FFC0CB,
        stop:1 #FFFFFF
    );
    border-radius: 10px;
    color: black;
    padding: 10px;
    font-weight: bold;
}
"""
        self.fill_profile_btn.setStyleSheet(gradient_style)
        bulk_actions_layout.addWidget(self.fill_profile_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        bulk_actions_group.setLayout(bulk_actions_layout)
        main_layout.addWidget(bulk_actions_group)
        control_panel = QHBoxLayout()
        self.start_btn = QPushButton("▶ Начать")
        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.setEnabled(False)
        control_panel.addWidget(self.start_btn)
        control_panel.addWidget(self.stop_btn)
        main_layout.addLayout(control_panel)
        self.progress_widget = ProgressWidget(self)
        main_layout.addWidget(self.progress_widget)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)
        self.change_name_btn.clicked.connect(lambda: self.set_active_param('first_name', self.change_name_btn))
        self.change_lastname_btn.clicked.connect(lambda: self.set_active_param('last_name', self.change_lastname_btn))
        self.change_bio_btn.clicked.connect(lambda: self.set_active_param('about', self.change_bio_btn))
        self.change_avatar_btn.clicked.connect(lambda: self.set_active_param('avatar', self.change_avatar_btn))
        self.change_2fa_btn.clicked.connect(lambda: self.set_active_param('twoFA', self.change_2fa_btn))
        self.fill_profile_btn.clicked.connect(self.on_fill_profile_clicked)
        self.start_btn.clicked.connect(self.handle_start)
        self.stop_btn.clicked.connect(self.handle_stop)
        self.active_param = None
        self.param_buttons = [
            self.change_name_btn, self.change_lastname_btn,
            self.change_bio_btn, self.change_avatar_btn,
            self.change_2fa_btn
        ]
    def set_active_param(self, param: str, btn: QPushButton, *args, **kwargs) -> None:
        self.active_param = param
        for b in self.param_buttons:
            if b == btn:
                b.setStyleSheet("background-color: #aee571;")
            else:
                b.setStyleSheet("")
        if param == 'avatar':
            self.param_input.setEnabled(False)
            self.param_input.setPlaceholderText("Для аватара выберите папку с изображениями")
        else:
            self.param_input.setEnabled(True)
            self.param_input.setPlaceholderText("Введите новое значение...")
    def select_image_folder(self, *args, **kwargs):
        folder = QFileDialog.getExistingDirectory(self, "Выбрать папку с изображениями")
        if folder:
            self.image_folder = folder
            if self.active_param == 'avatar':
                self.image_folder_label.setText(f"Папка: {folder}")
                self.log_area.append(f"Выбрана папка изображений: {folder}")
            else:
                QMessageBox.warning(self, "Ошибка", "Сначала выберите 'Изменить аватар'!")
        else:
            self.log_area.append("Папка изображений не выбрана.")
    def get_text_dialog(self, title, label, *args, **kwargs):
        text, ok = QInputDialog.getText(self, title, label)
        if ok and text.strip():
            return text.strip()
        return None
    def update_session_progress(self, percent: int, message: str, *args, **kwargs):
        if not self._is_closing:
            self.progress_widget.update_progress(percent, message)
    def closeEvent(self, event, *args, **kwargs) -> None:
        self._is_closing = True
        self.log_area.append("Ожидание завершения процессов перед закрытием...")
        self.stop_all_operations()
        event.accept()
    def handle_stop(self, *args, **kwargs) -> None:
        self.running = False
        self.log_area.append("⏹️ Останавливаем процесс...")
        self.stop_all_operations()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_widget.update_progress(100, "Остановлено")
        self.log_area.append("✅ Все процессы остановлены")
        for btn in self.param_buttons:
            btn.setEnabled(True)
        self.param_input.setEnabled(True)
    def handle_session_finished(self, session_path: str, success: bool) -> None:
        if self._is_closing:
            return
        self.completed_sessions.add(session_path)
        progress = len(self.completed_sessions) * 100 // self.total_sessions
        self.progress_widget.update_progress(
            progress,
            f"Завершено {len(self.completed_sessions)}/{self.total_sessions}"
        )
        if len(self.completed_sessions) >= self.total_sessions:
            self.running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            for btn in self.param_buttons:
                btn.setEnabled(True)
            self.param_input.setEnabled(True)
            self.progress_widget.update_progress(100, "Все задачи завершены")
            self.log_area.append(f"✅ Все {self.total_sessions} сессий обработаны")
    @pyqtSlot()
    def on_fill_profile_clicked(self, *args, **kwargs):
        self.report_shown = False
        if self.running:
            self.log_area.append("⚠️ Процесс уже запущен")
            return
        if not self.selected_sessions:
            self.log_area.append("⚠️ Не выбрано ни одной сессии")
            return
        use_proxy = self.use_proxy_checkbox.isChecked()
        proxy = None
        if use_proxy:
            config = load_config()
            proxy = load_proxy(config)
            if proxy:
                self.log_area.append(f"🌐 Используем прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.log_area.append("⚠️ Прокси включен, но не настроен в конфигурации")
        else:
            self.log_area.append("ℹ️ Прокси не используется")
        if hasattr(self, 'image_folder') and os.path.exists(self.image_folder):
            self.log_area.append(f"🖼️ Будут использованы аватарки из папки: {self.image_folder}")
        else:
            result = QMessageBox.question(
                self,
                "Аватарки не выбраны",
                "Вы не выбрали папку с изображениями для аватаров. Продолжить без смены аватара?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if result == QMessageBox.StandardButton.No:
                self.log_area.append("⚠️ Выберите папку с изображениями для аватаров")
                return
        self.running = True
        self.completed_sessions = set()
        self.active_param = 'fill_profile'
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        for btn in self.param_buttons:
            btn.setEnabled(False)
        self.param_input.setEnabled(False)
        self.total_sessions = len(self.selected_sessions)
        self.progress_widget.update_progress(0, "Запуск процесса...")
        for session_path in self.selected_sessions:
            thread = SessionThread(self, session_path, 'fill_profile',
                                   {'avatar_folder': getattr(self, 'image_folder', None)}, proxy)
            thread.log_signal.connect(lambda msg: self.log_area.append(msg))
            thread.error_signal.connect(self.handle_session_error)
            thread.progress_signal.connect(self.update_session_progress)
            thread.done_signal.connect(lambda: self._on_thread_finished(thread))
            self.thread_manager.start_thread(thread)
            launch_progress = self.thread_manager.get_total_count() * 100 // self.total_sessions
            self.progress_widget.update_progress(
                launch_progress,
                f"Запущено {self.thread_manager.get_total_count()}/{self.total_sessions}"
            )
    def run_async(self, coro, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return asyncio.create_task(coro) if loop.is_running() else loop.run_until_complete(coro)
    @pyqtSlot()
    def handle_start(self) -> None:
        self.report_shown = False
        if self.running:
            self.log_area.append("⚠️ Процесс уже запущен")
            return
        if not self.selected_sessions:
            self.log_area.append("⚠️ Не выбрано ни одной сессии")
            return
        if not self.active_param:
            self.log_area.append("⚠️ Выберите действие (имя, фамилия, описание и т.д.)")
            return
        use_proxy = self.use_proxy_checkbox.isChecked()
        proxy = None
        if use_proxy:
            config = load_config()
            proxy = load_proxy(config)
            if proxy:
                self.log_area.append(f"🌐 Используем прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.log_area.append("⚠️ Прокси включен, но не настроен в конфигурации")
        else:
            self.log_area.append("ℹ️ Прокси не используется")
        value = None
        if self.active_param == 'avatar':
            if not hasattr(self, 'image_folder') or not os.path.exists(self.image_folder):
                self.log_area.append("⚠️ Выберите папку с изображениями")
                return
            value = self.image_folder
        elif self.active_param == 'twoFA':
            new_password = self.param_input.text().strip()
            if not new_password:
                self.log_area.append("⚠️ Введите новый пароль 2FA")
                return
            value = {'new': new_password}
        elif self.active_param in ['first_name', 'last_name', 'about', 'username']:
            value = self.param_input.text().strip()
            if not value:
                self.log_area.append(f"⚠️ Введите новое значение для {self.active_param}")
                return
        self.running = True
        self.completed_sessions = set()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        for btn in self.param_buttons:
            btn.setEnabled(False)
        self.param_input.setEnabled(False)
        self.total_sessions = len(self.selected_sessions)
        self.progress_widget.update_progress(0, "Запуск процесса...")
        for session_path in self.selected_sessions:
            thread_value = value
            if self.active_param == 'twoFA':
                json_path = session_path.replace('.session', '.json')
                old_password = ''
                if os.path.exists(json_path):
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        old_password = data.get('twoFA', '')
                    except Exception:
                        pass
                thread_value = {'old': old_password, 'new': value['new']}
            thread = SessionThread(self, session_path, self.active_param, thread_value, proxy)
            thread.log_signal.connect(lambda msg: self.log_area.append(msg))
            thread.error_signal.connect(self.handle_session_error)
            thread.progress_signal.connect(self.update_session_progress)
            thread.done_signal.connect(lambda: self._on_thread_finished(thread))
            self.thread_manager.start_thread(thread)
            launch_progress = self.thread_manager.get_total_count() * 100 // self.total_sessions
            self.progress_widget.update_progress(
                launch_progress,
                f"Запущено {self.thread_manager.get_total_count()}/{self.total_sessions}"
            )
    def handle_session_error(self, error_type: str, message: str) -> None:
        error_prefix = {
            'FloodWait': '⏳',
            'AuthError': '🔒',
            'NetworkError': '🌐',
            'FileError': '📁',
            '2FAError': '🔑',
            'ThreadError': '⚠️',
            'ProcessError': '❌',
            'InitError': '⚠️'
        }.get(error_type, '❌')
        self.log_area.append(f"{error_prefix} {message}")
    def _on_thread_finished(self, thread: BaseThread):
        self.completed_sessions.add(thread.session_path)
        progress = len(self.completed_sessions) * 100 // self.total_sessions
        self.progress_widget.update_progress(
            progress,
            f"Завершено {len(self.completed_sessions)}/{self.total_sessions}"
        )
        if len(self.completed_sessions) >= self.total_sessions and not self.report_shown:
            self.report_shown = True
            self.running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            for btn in self.param_buttons:
                btn.setEnabled(True)
            self.param_input.setEnabled(True)
            self.progress_widget.update_progress(100, "Все задачи завершены")
            self.log_area.append(f"✅ Все {self.total_sessions} сессий обработаны")
class SessionThread(BaseThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, str)
    done_signal = pyqtSignal(str, bool)
    def __init__(self, parent, session_path: str, param: str, value: Any, proxy: Optional[Dict] = None):
        super().__init__(session_file=os.path.basename(session_path), parent=parent)
        self.parent = parent
        self.session_path = session_path
        self.session_file = os.path.basename(session_path)
        self.param = param
        self.value = value
        self.proxy = proxy
        self.running = True
        self.session_folder = os.path.dirname(session_path)
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.handle_log)
        self.connection.error_signal.connect(self.handle_error)
        self.connection.progress_signal.connect(self.progress_signal.emit)
    def handle_log(self, message, *args, **kwargs):
        self.log_signal.emit(message)
    def handle_error(self, session_file: str, error: TelegramError, *args, **kwargs):
        if not self.running:
            return
        error_type_str = error.type.name if hasattr(error.type, 'name') else str(error.type)
        if error.type == TelegramErrorType.FLOOD_WAIT:
            if not self.running:
                return
            self.log_signal.emit(f"⏳ {os.path.basename(session_file)} | Ожидание {error.wait_time} сек")
        else:
            if not self.running:
                return
            self.error_signal.emit(error_type_str, f"{os.path.basename(session_file)} | Ошибка: {error.message}")
    def stop(self, *args, **kwargs):
        super().stop()
    def run(self, *args, **kwargs):
        super().run()
    async def process(self, *args, **kwargs):
        try:
            if not self.running:
                return
            success, user = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy))
            if not success or not user:
                self.emit_log(f"❌ Не удалось подключиться к сессии: {os.path.basename(self.session_file)}")
                return
            try:
                if self.param == 'fill_profile':
                    await self.generate_and_update_profile(self.connection.client)
                elif self.param == 'first_name':
                    await self.connection.client(UpdateProfileRequest(first_name=self.value))
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Имя изменено")
                    await self.connection.update_session_info(self.session_file, await self.connection.client.get_me())
                elif self.param == 'last_name':
                    await self.connection.client(UpdateProfileRequest(last_name=self.value))
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Фамилия изменена")
                    await self.connection.update_session_info(self.session_file, await self.connection.client.get_me())
                elif self.param == 'about':
                    await self.connection.client(UpdateProfileRequest(about=self.value))
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Описание изменено")
                    await self.connection.update_session_info(self.session_file, await self.connection.client.get_me())
                elif self.param == 'username':
                    await self.connection.client(UpdateUsernameRequest(username=self.value))
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Username изменён")
                    await self.connection.update_session_info(self.session_file, await self.connection.client.get_me())
                elif self.param == 'avatar':
                    await self.update_avatar(self.connection.client)
                elif self.param == 'twoFA':
                    await self.update_2fa(self.connection.client)
            except FloodWaitError as e:
                wait_time = e.seconds
                self.emit_log(f"⏳ {os.path.basename(self.session_file)} | Ожидание {wait_time} секунд")
                if wait_time < 120 and self.running:
                    await asyncio.sleep(wait_time)
                    self.emit_log(f"⏳ {os.path.basename(self.session_file)} | Повторная попытка после ожидания")
                    await self.process()
                else:
                    self.emit_log(f"⚠️ {os.path.basename(self.session_file)} | Слишком долгое ожидание: {wait_time} секунд")
            except Exception as e:
                self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка: {str(e)}")
        except Exception as e:
            self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка подключения: {str(e)}")
        finally:
            if self.connection:
                await self.connection.disconnect()
    async def generate_and_update_profile(self, client, *args, **kwargs):
        faker = Faker('ru_RU')
        gender = faker.random_element(elements=("male", "female"))
        if gender == "male":
            first_name = faker.first_name_male()
            last_name = faker.last_name_male()
        else:
            first_name = faker.first_name_female()
            last_name = faker.last_name_female()
        start_phrases = [
            "Люблю", "Не люблю", "Ищу", "Занимаюсь", "Хочу", "Обожаю", "Пытаюсь", "Не пропускаю",
            "Хожу", "Живу", "Иногда", "Больше всего ценю", "Мечтаю", "Увлекаюсь"
        ]
        middle_phrases = [
            "видео игры", "спокойные вечера", "новые знакомства", "путешествия", "психологию", "спорт",
            "музыку", "книги", "разные хобби", "книги по саморазвитию", "мудрость", "качественные фильмы",
            "контент про игры", "мудрые цитаты", "программирование", "разговоры о жизни", "активный отдых"
        ]
        end_phrases = [
            "и наслаждаюсь каждым моментом.", "и не жалею об этом.", "и это то, что мне нужно.",
            "и жду новых открытий.", "и меня это всегда вдохновляет.", "и обожаю этим делиться.",
            "и это приносит мне счастье.", "и это всегда помогает мне быть собой.",
            "и не могу представить себя без этого.", "и всегда нахожу что-то новое.",
            "и всегда рад поделиться этим с другими.", "и не упускаю шанс повеселиться.",
            "и это для меня главное.", "и буду рад, если ты тоже увлечен этим."
        ]
        about = f"{random.choice(start_phrases)} {random.choice(middle_phrases)} {random.choice(end_phrases)}"
        about = about[:70]
        await client(UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name,
            about=about
        ))
        self.emit_log(f"✅ {os.path.basename(self.session_file)} | Профиль обновлен:")
        self.emit_log(f"   👤 Имя: {first_name} {last_name}")
        self.emit_log(f"   📝 Описание: {about}")
        base_username = self.latinize(first_name.lower() + last_name.lower())
        base_username = re.sub(r'[^a-zA-Z0-9]', '', base_username)
        if not base_username or not base_username[0].isalpha():
            base_username = 'user' + base_username
        base_username = base_username[:32]
        if len(base_username) < 5:
            base_username += ''.join(random.choices('0123456789', k=5-len(base_username)))
        if not base_username[-1].isalnum():
            base_username = base_username[:-1] + 'a'
        username_set = False
        try:
            me = await client.get_me()
            current_username = (me.username or '').lower()
        except Exception:
            current_username = ''
        if base_username != current_username:
            tried = set()
            max_attempts = 5
            attempt = 0
            while not username_set and attempt < max_attempts:
                try:
                    if attempt == 0:
                        username = base_username
                    else:
                        letter = random.choice(string.ascii_lowercase)
                        digit = random.choice('0123456789')
                        username = f"{base_username[:30]}{letter}{digit}"
                    if username in tried:
                        continue
                    tried.add(username)
                    await client(UpdateUsernameRequest(username=username))
                    username_set = True
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Username установлен: @{username}")
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        self.emit_log(f"⚠️ {os.path.basename(self.session_file)} | Не удалось установить username: {str(e)}")
                        username = ""
        me = await client.get_me()
        json_path = os.path.join(self.session_folder, self.session_file.replace('.session', '.json'))
        try:
            current_data = {}
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    current_data = json.load(f)
            current_data.update({
                'first_name': first_name,
                'last_name': last_name,
                'about': about,
                'username': username if username_set else "",
                'last_update': datetime.now().isoformat()
            })
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
            self.emit_log(f"✅ {os.path.basename(self.session_file)} | Данные сохранены в JSON")
        except Exception as e:
            self.error_signal.emit("JsonError", f"{os.path.basename(self.session_file)} | Ошибка обновления JSON: {e}")
    def latinize(self, text: str) -> str:
        trans_table = str.maketrans({
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '',
            'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        })
        return text.lower().translate(trans_table)
    async def update_avatar(self, client, *args):
        try:
            if not os.path.exists(self.value):
                self.error_signal.emit("FileError", f"{os.path.basename(self.session_file)} | Папка не найдена: {self.value}")
                return
            images = [f for f in os.listdir(self.value) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if not images:
                self.error_signal.emit("FileError", f"{os.path.basename(self.session_file)} | В папке нет изображений")
                return
            image_path = os.path.join(self.value, random.choice(images))
            with Image.open(image_path) as img:
                img = img.convert("RGB")
                img = img.resize((512, 512), Image.LANCZOS)
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=95)
                output.seek(0)
                file = await client.upload_file(output)
                await client(UploadProfilePhotoRequest(file=file))
            self.emit_log(f"✅ {os.path.basename(self.session_file)} | Аватар обновлен")
            json_path = os.path.join(self.session_folder, self.session_file.replace('.session', '.json'))
            try:
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data['has_profile_pic'] = True
                    data['last_update'] = datetime.now().isoformat()
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                self.error_signal.emit("JsonError", f"{os.path.basename(self.session_file)} | Ошибка обновления JSON: {e}")
        except Exception as e:
            self.error_signal.emit("AvatarError", f"{os.path.basename(self.session_file)} | {str(e)}")
    async def update_2fa(self, client, *args, **kwargs):
        try:
            if isinstance(self.value, dict):
                old_password = self.value.get('old', '')
                new_password = self.value.get('new', '')
            else:
                old_password = ''
                new_password = self.value
            try:
                if old_password:
                    await client.edit_2fa(current_password=old_password, new_password=new_password)
                else:
                    await client.edit_2fa(new_password=new_password)
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | 2FA пароль обновлен")
                json_path = os.path.join(self.session_folder, self.session_file.replace('.session', '.json'))
                try:
                    if os.path.exists(json_path):
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        data['twoFA'] = new_password
                        data['last_update'] = datetime.now().isoformat()
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    self.error_signal.emit("JsonError", f"{os.path.basename(self.session_file)} | Ошибка обновления JSON: {e}")
            except PasswordHashInvalidError:
                self.error_signal.emit("2FAError", f"{os.path.basename(self.session_file)} | Неверный текущий пароль 2FA")
            except Exception as e:
                self.error_signal.emit("2FAError", f"{os.path.basename(self.session_file)} | {str(e)}")
        except Exception as e:
            self.error_signal.emit("2FAError", f"{os.path.basename(self.session_file)} | {str(e)}")
