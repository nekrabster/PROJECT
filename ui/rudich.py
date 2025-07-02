from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
    QMessageBox, QApplication
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QProcess, 
    QPropertyAnimation, QUrl
)
from PyQt6.QtGui import QPixmap, QColor, QDesktopServices, QPainterPath, QPainter
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QGuiApplication
import sys
import os
import requests
import json
import platform
import asyncio
import hashlib
from ui.bombardirocrocodilo import MainWindow, KeyValidationThread
from packaging.version import parse
from qasync import QEventLoop
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path):
            return path
    if getattr(sys, 'frozen', False):
        path = os.path.join(os.path.dirname(sys.executable), relative_path)
        if os.path.exists(path):
            return path
    path = os.path.join(os.path.dirname(__file__), relative_path)
    return path
class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str)
    def __init__(self, current_version, *args, **kwargs):
        super().__init__()
        self.current_version = current_version        
    def run(self, *args, **kwargs):
        try:
            response = requests.get(
                "https://update.smm-aviator.com/version/update.php",
                timeout=5
            )
            if response.status_code == 200:
                update_info = response.json()
                if "version" in update_info and "update_url" in update_info:
                    latest_version = update_info["version"]
                    update_url = update_info["update_url"]                    
                    if parse(latest_version) > parse(self.current_version):
                        self.update_available.emit(latest_version, update_url)
        except Exception as e:
            print(f"Ошибка при проверке обновлений: {e}")
class ActivationWindow(QWidget):
    _RESOURCES = {}
    _CACHED_STYLES = {
        'container': """
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1E293B, stop:1 #111827);
                border-radius: 20px;
                border: 2px solid rgba(209, 213, 219, 0.1);
            }
        """,
        'title': """
            QLabel {
                color: #FFFFFF;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """,
        'input': """
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
                border: 2px solid rgba(147, 197, 253, 0.5);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """,
        'button': """
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #6B7280;
            }
        """,
        'notification': """
            QLabel {
                color: #FFFFFF;
                background-color: rgba(59, 130, 246, 0.1);
                border: 1px solid #3B82F6;
                border-radius: 8px;
                padding: 8px;
            }
        """,
        'telegram_link': """
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 14px;
                padding: 10px;
            }
            QLabel a {
                color: #6366F1;
                text-decoration: none;
            }
            QLabel a:hover {
                text-decoration: underline;
            }
        """,
        'version': """
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 13px;
                padding: 10px;
            }
        """
    }

    @classmethod
    def load_resource(cls, path):
        if path not in cls._RESOURCES:
            cls._RESOURCES[path] = QPixmap(path)
        return cls._RESOURCES[path]
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Активация")
        self.setFixedSize(400, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)        
        self.CURRENT_VERSION = "2.3.9"
        self.drag_position = None
        self.validation_worker = None
        self.update_url = None
        self.update_checker = None        
        self.setup_critical_ui()
        QTimer.singleShot(100, self.setup_deferred_ui)
        QApplication.instance().paletteChanged.connect(self.update_stylesheet)
    def set_rounded_corners(self, *args, **kwargs):
        class RoundedWidget(QWidget):
            def __init__(self, parent=None, radius=20):
                super().__init__(parent)
                self.radius = radius
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)                
                path = QPainterPath()
                rect = self.rect()                
                path.addRoundedRect(rect, self.radius, self.radius)
                self.setMask(path.toFillPolygon().toPolygon())
                painter.fillPath(path, self.palette().window())
        self.container = RoundedWidget(self, radius=20)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QWidget#container {
                background-color: white;
                border: 1px solid #cccccc;
            }
        """)
        self.container.setGeometry(1, 1, 400, 500)
    def setup_critical_ui(self, *args, **kwargs):
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(self._CACHED_STYLES['container'])
        self.container.setGeometry(1, 1, 400, 500)        
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)        
        self.load_config()
        self.setup_dispatcher_icon()
        self.setup_key_input()
        self.setup_activate_button()
        self.setup_telegram_button()
    def setup_deferred_ui(self, *args, **kwargs):
        self.setup_version_info()
        self.setup_additional_info()
        self.setup_window_effects()
        QTimer.singleShot(1000, self.check_for_update)
    def setup_dispatcher_icon(self, *args, **kwargs):
        icon_container = QWidget()
        icon_container.setFixedHeight(300)        
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)        
        self.icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), os.pardir, "icons", "dispatcher.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            available_width = self.container.width() - 20 
            available_height = 260
            scaled_size = min(available_width, available_height)            
            pixmap = pixmap.scaled(
                scaled_size, scaled_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_label.setPixmap(pixmap)        
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self.icon_label)        
        self.main_layout.addWidget(icon_container)
    def setup_key_input(self, *args, **kwargs):
        layout = QVBoxLayout()
        layout.setSpacing(15)        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Введите ключ активации")
        self.key_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.08);  /* Увеличили непрозрачность */
                color: #FFFFFF;
                border: 2px solid rgba(147, 197, 253, 0.5);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: rgba(255, 255, 255, 0.12);  /* При фокусе еще больше непрозрачности */
                border-color: #3B82F6;
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.5);
            }
        """)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)        
        if hasattr(self, 'saved_key') and self.saved_key:
            self.key_input.setText(self.saved_key)            
        layout.addWidget(self.key_input)
        self.main_layout.addLayout(layout)        
    def setup_activate_button(self, *args, **kwargs):
        layout = QVBoxLayout()
        layout.setSpacing(25)
        self.activate_button = QPushButton("Активировать")
        self.activate_button.setStyleSheet(self._CACHED_STYLES['button'])
        self.activate_button.clicked.connect(self.activate)
        layout.addWidget(self.activate_button)        
        self.main_layout.addLayout(layout)
    def setup_telegram_button(self, *args, **kwargs):
        layout = QVBoxLayout()
        layout.setContentsMargins(50, 0, 50, 0)          
        self.telegram_button = QPushButton("Получить ключ в Telegram")
        self.telegram_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0088cc, stop:1 #0099cc);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                min-height: 40px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0099cc, stop:1 #00aadd);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0077bb, stop:1 #0088cc);
            }
        """)
        self.telegram_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.telegram_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/garolder")))        
        layout.addWidget(self.telegram_button)
        self.main_layout.addLayout(layout)
    def setup_version_info(self, *args, **kwargs):
        layout = QVBoxLayout()
        layout.setSpacing(15)        
        self.version_label = QLabel("Версия 2.3.9")
        self.version_label.setStyleSheet(self._CACHED_STYLES['version'])
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)        
        self.main_layout.addLayout(layout)
    def setup_additional_info(self, *args, **kwargs):
        self.update_notification_label = QLabel("", self)
        self.update_notification_label.setFixedHeight(35)
        self.update_notification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_notification_label.setStyleSheet(self._CACHED_STYLES['notification'])
        self.update_notification_label.hide()
        self.update_notification_label.mousePressEvent = self.download_update
        self.main_layout.addWidget(self.update_notification_label)        
    def setup_window_effects(self, *args, **kwargs):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 0)
        self.container.setGraphicsEffect(shadow)        
    def create_loading_overlay(self, *args, **kwargs):
        overlay = QWidget(self)
        overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.5);
                border-radius: 20px;
            }
        """)
        layout = QVBoxLayout(overlay)
        loading_label = QLabel("Загрузка...")
        loading_label.setStyleSheet("color: white; font-size: 16px; background: transparent;")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(loading_label)
        fade_animation = QPropertyAnimation(overlay, b"windowOpacity")
        fade_animation.setDuration(200)        
        return overlay, fade_animation
    def show_loading_overlay(self, show=True, *args, **kwargs):
        if not hasattr(self, '_loading_overlay'):
            self._loading_overlay, self._fade_animation = self.create_loading_overlay()            
        if show:
            self._loading_overlay.setGeometry(self.container.geometry())
            self._fade_animation.setStartValue(0)
            self._fade_animation.setEndValue(1)
            self._loading_overlay.show()
            self._fade_animation.start()
        else:
            self._fade_animation.setStartValue(1)
            self._fade_animation.setEndValue(0)
            self._fade_animation.finished.connect(self._loading_overlay.hide)
            self._fade_animation.start()
    def validate_license_key(self, user_key, *args, **kwargs):
        self.show_loading_overlay(True)
        self.activate_button.setEnabled(False)
        self.activate_button.setText("Проверка...")        
        self.validation_worker = KeyValidationWorker(user_key, self.get_device_id())
        def on_validation_complete(is_valid, error_message):
            self.show_loading_overlay(False)
            self.activate_button.setEnabled(True)
            self.activate_button.setText("Активировать")            
            if not is_valid:
                QMessageBox.warning(self, "Ошибка", error_message)            
            if is_valid:
                self.save_key_and_proceed(user_key)                
        self.validation_worker.validation_complete.connect(on_validation_complete)
        self.validation_worker.start()
        return False
    def showEvent(self, event, *args, **kwargs):
        super().showEvent(event)
        self.check_for_update()
    def check_for_update(self, *args, **kwargs):
        if self.update_checker is None:
            self.update_checker = UpdateCheckerThread(self.CURRENT_VERSION)
            self.update_checker.update_available.connect(self.on_update_available)        
        if not self.update_checker.isRunning():
            self.update_checker.start()
    def on_update_available(self, latest_version, update_url, *args, **kwargs):
        self.update_url = update_url        
        self.version_label.setText(f"Доступно обновление {latest_version}")
        self.version_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 11px;
                background-color: rgba(59, 130, 246, 0.15);
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 8px;
                padding: 5px 10px;
            }
            QLabel:hover {
                background-color: rgba(59, 130, 246, 0.25);
                border-color: rgba(59, 130, 246, 0.5);
            }
        """)
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.mousePressEvent = self.download_update
    def download_update(self, event=None, *args, **kwargs):
        import os
        CURRENT_FILE = os.path.abspath("Soft-K.exe")
        TEMP_FILE = os.path.abspath("Soft-K_temp.exe")
        UPDATER_FILE = os.path.abspath("updater.bat")
        try:
            self.version_label.setText("Скачивание новой версии...")
            response = requests.get(self.update_url, stream=True)
            if response.status_code == 200:
                with open(TEMP_FILE, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
            else:
                raise Exception(f"Ошибка загрузки: статус {response.status_code}")
            self.version_label.setText("Подготовка установщика...")
            updater_code = f"""@echo off
title Обновление программы

:: Ждем завершения процесса
:waitloop
tasklist | find /i \"Soft-K.exe\" >nul 2>&1
if not errorlevel 1 (
    timeout /t 1 >nul
    goto waitloop
)

:: Заменяем exe
move /Y \"{TEMP_FILE}\" \"{CURRENT_FILE}\" >nul 2>&1

:: Запускаем новую версию
start \"\" \"{CURRENT_FILE}\"

:: Удаляем себя
del \"%~f0\"
"""
            with open(UPDATER_FILE, "w", encoding="utf-8") as f:
                f.write(updater_code)
            QProcess.startDetached(UPDATER_FILE)
            QTimer.singleShot(500, QApplication.quit)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при обновлении:\n{e}")
    def check_update_status(self, *args, **kwargs):
        if asyncio.get_event_loop().is_running():
            QTimer.singleShot(100, lambda: self.check_update_status())
    def load_config(self, *args, **kwargs):
        self.saved_key = ''
        config_path = os.path.join(os.getcwd(), 'config.txt')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('key='):
                            self.saved_key = line.strip().split('=', 1)[1]
                            break
            except Exception as e:
                print(f"Не удалось прочитать config.txt: {e}")
    def activate(self, checked=False, *args, **kwargs):
        try:
            key = self.key_input.text()
            if not key:
                QMessageBox.warning(self, "Ошибка", "Введите ключ активации")
                return
            self.validate_license_key(key)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {str(e)}")
            print(f"Ошибка в методе activate: {e}")
    def open_main_window(self, *args, **kwargs):
        LOADING_LABEL_WIDTH = 200
        LOADING_LABEL_HEIGHT = 60
        LOADING_STYLE = """
            QLabel {
                color: #FFFFFF;
                font-size: 16px;
                background-color: rgba(0, 0, 0, 80%);
                border-radius: 10px;
                padding: 20px;
            }
        """
        loading_label = QLabel("Загрузка...", self)
        loading_label.setStyleSheet(LOADING_STYLE)
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_label.resize(LOADING_LABEL_WIDTH, LOADING_LABEL_HEIGHT)
        loading_label.move(
            (self.width() - LOADING_LABEL_WIDTH) // 2,
            (self.height() - LOADING_LABEL_HEIGHT) // 2
        )
        loading_label.show()
        QApplication.processEvents()
        def init_main_window():
            x, y, w, h = self.calculate_window_geometry()
            key = self.key_input.text()
            self.main_window = MainWindow(key=key)
            self.main_window.resize(w, h)
            self.main_window.move(x, y)
            self.main_window.show()
            loading_label.deleteLater()
            self.close()
        QTimer.singleShot(100, init_main_window)
    def calculate_window_geometry(self):
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        MARGIN_PERCENT = 0.99
        window_width = int(screen_width * MARGIN_PERCENT)
        window_height = int(screen_height * MARGIN_PERCENT)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        return x, y, window_width, window_height
    def save_key_and_proceed(self, key, *args, **kwargs):
        config_path = os.path.join(os.getcwd(), 'config.txt')
        lines = []
        found = False
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('key='):
                            lines.append(f'key={key}\n')
                            found = True
                        else:
                            lines.append(line)
            except Exception as e:
                print(f"Не удалось прочитать config.txt для обновления ключа: {e}")    
        if not found:
            lines.append(f'key={key}\n')
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            print(f"Не удалось сохранить ключ в config.txt: {e}")            
        self.open_main_window()
    def get_device_id(self, *args, **kwargs):
        return platform.node()
    def mousePressEvent(self, event, *args, **kwargs):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint()            
    def mouseMoveEvent(self, event, *args, **kwargs):
        if self.drag_position:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_position)
            self.drag_position = event.globalPosition().toPoint()
            event.accept()            
    def mouseReleaseEvent(self, event, *args, **kwargs):
        self.drag_position = None
    def update_stylesheet(self, *args):
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
class UpdateCheckTask(QThread):
    update_available = pyqtSignal(str, str)
    update_error = pyqtSignal(str)
    def __init__(self, window):
        super().__init__()
        self.window = window
    def run(self, *args, **kwargs):
        UPDATE_CHECK_URL = "https://update.smm-aviator.com/version/update.php"
        CURRENT_VERSION = "2.3.9"
        try:
            response = requests.get(UPDATE_CHECK_URL)
            response.raise_for_status()
            update_info = response.json()
            if "version" not in update_info or "update_url" not in update_info:
                self.update_error.emit("Ответ сервера не содержит информации о версии.")
                return
            latest_version = update_info["version"]
            update_url = update_info["update_url"]
            if parse(latest_version) > parse(CURRENT_VERSION):
                self.update_available.emit(latest_version, update_url)
            else:
                self.window.version_label.setText(f"Версия приложения: {latest_version}")
        except requests.exceptions.RequestException as e:
            self.update_error.emit(f"Ошибка проверки обновлений: {e}")
        except json.JSONDecodeError:
            self.update_error.emit("Ошибка обработки JSON ответа от сервера.")
    def calculate_sha256(self, file_path, *args, **kwargs):
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
class KeyValidationWorker(QThread):
    validation_complete = pyqtSignal(bool, str)
    def __init__(self, key, device_id):
        super().__init__()
        self.key = key
        self.device_id = device_id        
    def run(self, *args, **kwargs):
        url = 'https://update.smm-aviator.com/check_key.php'
        payload = {"key": self.key, "device_id": self.device_id}
        headers = {'Content-Type': 'application/json'}        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "valid":
                    self.validation_complete.emit(True, "")
                elif data["status"] == "invalid":
                    self.validation_complete.emit(False, "Неверный ключ активации.")
                elif data["status"] == "expired":
                    self.validation_complete.emit(False, "Срок действия ключа истек.")
                else:
                    self.validation_complete.emit(False, "Произошла ошибка на сервере.")
            else:
                self.validation_complete.emit(False, "Не удалось подключиться к серверу.")
        except requests.exceptions.RequestException:
            self.validation_complete.emit(False, "Ошибка подключения к серверу.")
