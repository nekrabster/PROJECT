import os
import json
import logging
import sys
import platform
import traceback
import asyncio
import requests
from random import randint
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation
)
from PyQt6.QtGui import QPalette, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel,
    QPushButton, QLineEdit, QFrame, QSizePolicy, QFileDialog, QMessageBox,
    QDialog, QTextEdit, QScrollArea, QFormLayout, QDialogButtonBox
)
from ui.complas import ComplaintsWindow
from ui.kachok import PhysicalSimWindow
from ui.subscribe import SubscribeWindow
from ui.malining import MailingWindow
from ui.components import ComponentsWindow
from ui.session import BotWindow
from ui.sessionbeta import BotWindowBeta
from ui.rass import RassWindow
from ui.rassbeta import RassWindow
from ui.check import CheckWindow
from ui.newtoken import NewTokenWindow
from ui.informatika import InfoWindow
from ui.okak import ErrorReportDialog
from ui.bot_manager import BotManagerWindow
from ui.session_manager import SessionManagerWindow
from ui.search import SearchWindow
from ui.samit import SamitWindow
from ui.proxy_utils import parse_proxy_string
from ui.mail import MailWindow
from ui.subs import SubsWindow
from ui.kraken import KrakenWindow
from ui.instructions import INSTRUCTIONS
from ui.damkrat import ColorGenerator
from ui.theme import ThemeManager
from ui.styles import StyleManager
from ui.top import TopBar
from ui.side import SideBar
from ui.bottom import BottomBar
def get_app_directory():
    """Возвращает правильную рабочую директорию приложения"""
    if getattr(sys, 'frozen', False):
        # Для executable используем текущую рабочую директорию
        return os.getcwd()
    else:
        # Для обычного Python-скрипта используем корневую директорию проекта
        return os.path.abspath('.')
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), os.pardir, relative_path)
def load_config():
    base_path = get_app_directory()
    DEFAULT_CONFIG = {
        "api_id": 0,
        "api_hash": "",
        "session_folder": os.path.join(base_path, "sessions"),
        "bot_token_folder": os.path.join(base_path, "bots"),
        "proxy_config": {
            "type": "",
            "ip": "",
            "port": "",
            "login": "",
            "password": ""
        }
    }
    config = DEFAULT_CONFIG.copy()
    proxy_config = config["proxy_config"].copy()
    try:
        config_path = os.path.join(base_path, "config.txt")
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                if '=' not in line:
                    continue
                key, val = line.strip().split('=', 1)
                key = key.lower()
                val = val.strip()
                if key == "api_id":
                    config["api_id"] = int(val) if val.isdigit() else 0
                elif key == "api_hash":
                    config["api_hash"] = val
                elif key == "session_folder":
                    config["session_folder"] = os.path.join(base_path, val) if not os.path.isabs(val) else val
                elif key == "bot_token_folder":
                    config["bot_token_folder"] = os.path.join(base_path, val) if not os.path.isabs(val) else val
                elif key == "proxy_type":
                    proxy_config["type"] = val
                elif key == "proxy_ip":
                    proxy_config["ip"] = val
                elif key == "proxy_port":
                    proxy_config["port"] = val
                elif key == "proxy_login":
                    proxy_config["login"] = val
                elif key == "proxy_password":
                    proxy_config["password"] = val
        config["proxy_config"] = proxy_config
        return config
    except FileNotFoundError:
        print("Warning: config.txt file not found. Using default config.")
        return DEFAULT_CONFIG
    except Exception as e:
        print(f"Warning: failed to load configuration, using default config. {e}")
        return DEFAULT_CONFIG
class KeyValidationThread(QThread):
    key_invalid_signal = pyqtSignal()
    def __init__(self, key, device_id):
        super().__init__()
        self.key = key
        self.device_id = device_id
        self.running = True
    async def check_key_async(self, *args, **kwargs):
        consecutive_failures = 0
        while self.running:
            try:
                url = 'https://update.smm-aviator.com/check_key.php'
                payload = {"key": self.key, "device_id": self.device_id}
                headers = {'Content-Type': 'application/json'}
                response = await asyncio.to_thread(requests.post, url, data=json.dumps(payload), headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] != "valid":
                        self.key_invalid_signal.emit()
                        break
                    consecutive_failures = 0
                else:
                    print(f"Error checking key: {response.status_code} - {response.text}")
                    consecutive_failures += 1
            except requests.exceptions.RequestException as e:
                print(f"Network error while checking key: {e}")
                consecutive_failures += 1
            except Exception as e:
                print(f"Unknown error while checking key: {e}")
                consecutive_failures += 1
            if consecutive_failures >= 3:
                print("Нет соединения с сервером 3 раза подряд. Софт будет выключен.")
                app = QApplication.instance()
                if app:
                    app.quit()
                else:
                    os._exit(1)
                return
            await asyncio.sleep(600)
    def run(self, *args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.check_key_async())
    def stop(self, *args, **kwargs):
        self.running = False
class MainWindow(QWidget):
    config_changed = pyqtSignal(dict)
    instructions = INSTRUCTIONS
    def __init__(self, key=None, *args):
        from ui.kms import initialize_master_protection, is_protection_active
        if not is_protection_active():
            initialize_master_protection()
        super().__init__(*args)
        self.setup_window()
        self.setup_logging()
        self.load_and_check_config()
        self.setup_key_validation(key)
        self.top_bar_manager = TopBar(self)
        self.side_bar_manager = SideBar(self)
        self.bottom_bar_manager = BottomBar(self)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.sidebar = self.side_bar_manager.create_sidebar()
        self.stacked_widget = self.create_stacked_widget()
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.top_bar = self.top_bar_manager.create_top_bar()
        self.bottom_bar = self.bottom_bar_manager.create_bottom_bar()
        right_layout.addWidget(self.top_bar)
        self.instruction_panel = self.create_instruction_panel()
        right_layout.addWidget(self.instruction_panel)
        right_layout.addWidget(self.stacked_widget, 1)
        right_layout.addWidget(self.bottom_bar)        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_container, 1)        
        self.apply_sidebar_style()
        self.update_stylesheet()
        self.side_bar_manager.connect_stats_signal()
    def setup_window(self, *args):
        self.setObjectName("main_window")
        self.setWindowTitle("Soft-K")
        self.setMinimumSize(1000, 900)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.is_dark_theme = QApplication.instance().palette().color(QPalette.ColorRole.Window).value() < 128
        QApplication.instance().paletteChanged.connect(self.on_palette_changed)
        self.update_stylesheet()
        icon_path = resource_path("icons/dispatcher.png")
        self.setWindowIcon(QIcon(icon_path))
    def on_palette_changed(self, *args):
        self.is_dark_theme = QApplication.instance().palette().color(QPalette.ColorRole.Window).value() < 128
        self.update_stylesheet()
        if hasattr(self, 'top_bar_manager'):
            self.top_bar_manager.update_theme_icon()
        self.apply_sidebar_style()
    def setup_logging(self, *args):
        class TSMFilter(logging.Filter):
            def filter(self, record):
                return "TSMSendMessageToUIServer" not in record.getMessage()        
        logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s: %(message)s')
        logger = logging.getLogger()
        logger.addFilter(TSMFilter())        
        def log_error(msg):
            logging.error(msg)
            QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(None, error_text=msg))        
        self.log_error = log_error
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            tb_txt = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            self.log_error(tb_txt)
            app = QApplication.instance()
            if not app:
                print('CRITICAL ERROR')        
        sys.excepthook = handle_exception
    def load_and_check_config(self, *args):
        config = load_config()
        if config.get('api_id', 0) == 0 or not config.get('api_hash'):
            print("Внимание: Необходимо указать параметры API (api_id и api_hash) в настройках.")
        self.api_id = config['api_id']
        self.api_hash = config['api_hash']
        self.session_folder = os.path.abspath(config['session_folder'])
        self.bot_token_folder = os.path.abspath(config['bot_token_folder'])
        self.proxy_config = config.get('proxy_config')
        if not os.path.exists(self.bot_token_folder):
            try:
                os.makedirs(self.bot_token_folder, exist_ok=True)
            except Exception as e:
                print(f"Ошибка создания папки для токенов ботов: {e}")
    def setup_key_validation(self, key, *args):
        if key:
            self.key_validation_thread = KeyValidationThread(key, platform.node())
            self.key_validation_thread.key_invalid_signal.connect(self.handle_key_invalid)
            self.key_validation_thread.start()
        else:
            self.key_validation_thread = None
    def create_instruction_panel(self, *args):
        instruction_panel = QFrame()
        instruction_panel.setVisible(False)
        instruction_panel.setMaximumHeight(0)
        instruction_panel.setFrameShape(QFrame.Shape.StyledPanel)
        instruction_panel.setFrameShadow(QFrame.Shadow.Raised)
        instruction_panel.setStyleSheet("background: transparent; border-top: none; border-bottom: 1px solid #ccc;")
        self.instruction_label = QLabel()
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setTextFormat(Qt.TextFormat.RichText)
        self.instruction_label.setStyleSheet("font-size: 11px; background: transparent;")
        self.instruction_scroll = QScrollArea()
        self.instruction_scroll.setWidgetResizable(True)
        self.instruction_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.instruction_scroll.setWidget(self.instruction_label)
        panel_layout = QVBoxLayout(instruction_panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.addWidget(self.instruction_scroll)
        return instruction_panel
    def detect_theme(self, *args):
        return ThemeManager.detect_theme()
    def build_radial_gradient(self, stops, *args):
        return ColorGenerator.build_radial_gradient(stops)
    def generate_theme_palette(self, is_dark, *args):
        return ColorGenerator.generate_theme_palette(is_dark)
    def apply_theme_palette(self, palette, *args):
        self.update_stylesheet(
            custom_widget_bg=palette["custom_widget_bg"],
            btn_bg=palette["btn_bg"],
            btn_hover=palette["btn_hover"],
            btn_fg=palette["btn_fg"],
            lbl_fg=palette["lbl_fg"],
            inp_bg=palette["inp_bg"],
            inp_fg=palette["inp_fg"],
            inp_border=palette["inp_border"],
            textedit_bg=palette["textedit_bg"]
        )
        self.sidebar_styles = palette["sidebar_styles"]
        self.apply_sidebar_style()
    def update_interface_colors(self, *args):
        ThemeManager.update_interface_colors(self)
    def handle_key_invalid(self, *args):
        QMessageBox.warning(self, "Error", "The activation key has expired. The program will close.")
        QApplication.quit()
        import sys
        sys.exit(0)
    def closeEvent(self, event):
        os._exit(0)
    def update_stylesheet(self, *args, custom_widget_bg=None, btn_bg=None, btn_hover=None, btn_fg=None, lbl_fg=None, inp_bg=None, inp_fg=None, inp_border=None, textedit_bg=None):
        dark = getattr(self, 'is_dark_theme', False)
        theme_colors = StyleManager.get_theme_default_colors(dark)
        if custom_widget_bg is not None:
            theme_colors['bg'] = custom_widget_bg
        if btn_bg is not None:
            theme_colors['_btn_bg'] = btn_bg
        if btn_hover is not None:
            theme_colors['_btn_hover'] = btn_hover
        if btn_fg is not None:
            theme_colors['_btn_fg'] = btn_fg
        if lbl_fg is not None:
            theme_colors['_lbl_fg'] = lbl_fg
        if inp_bg is not None:
            theme_colors['_inp_bg'] = inp_bg
        if inp_fg is not None:
            theme_colors['_inp_fg'] = inp_fg
        if inp_border is not None:
            theme_colors['_inp_border'] = inp_border
        if textedit_bg is not None:
            theme_colors['_textedit_bg'] = textedit_bg
        style = StyleManager.build_stylesheet(theme_colors)
        self.setStyleSheet(style)
        if hasattr(self, 'top_bar_manager'):
            self.top_bar_manager.update_icons(dark)
    def toggle_theme(self, *arg):
        ThemeManager.toggle_theme(self.is_dark_theme)
        self.update_stylesheet()
        self.sidebar_styles = None
        self.apply_sidebar_style()
    def apply_sidebar_style(self, *arg):
        styles = getattr(self, 'sidebar_styles', None)
        if styles is None:
            styles = StyleManager.get_default_sidebar_styles(getattr(self, 'is_dark_theme', False))
        self.side_bar_manager.sidebar = self.sidebar
        self.side_bar_manager.apply_sidebar_style(styles)
        self.bullet_labels = self.side_bar_manager.bullet_labels
    def create_stacked_widget(self, *args):
        stacked_widget = QStackedWidget(self)
        self.windows = self.create_windows()
        for window in self.windows.values():
            stacked_widget.addWidget(window)
        stacked_widget.setCurrentWidget(self.windows["informatika"])
        return stacked_widget
    def create_windows(self, *args):
        return {
            "informatika": InfoWindow(self),
            "kachok": PhysicalSimWindow(self.api_id, self.api_hash, self.session_folder, self),
            "complas": ComplaintsWindow(self.session_folder, self),
            "subscribe": SubscribeWindow(self.session_folder, self),
            "malining": MailingWindow(self.session_folder, self),
            "components": ComponentsWindow(self.session_folder, self),
            "bot_manager": BotManagerWindow(self.bot_token_folder, self),
            "session": BotWindow(self),
            "sessionbeta": BotWindowBeta(self),
            "rass": RassWindow(self.session_folder, self),
            "rassbeta": RassWindow(self.session_folder, self),
            "check": CheckWindow(self),
            "newtoken": NewTokenWindow(self.session_folder, self),
            "session_manager": SessionManagerWindow(self.session_folder, parent=self),
            "search": SearchWindow(self, self.session_folder),
            "samit": SamitWindow(self, self.api_id, self.api_hash),
            "mail": MailWindow(self),
            "subs": SubsWindow(self.session_folder, self),
            "kraken": KrakenWindow(self),
        }
    def handle_window_switch(self, window_name, *args):
        if window_name in self.windows:
            self.stacked_widget.setCurrentWidget(self.windows[window_name])
            self.update_instruction_panel(window_name)
    def update_instruction_panel(self, window_name=None, *args):
        if window_name is None:
            idx = self.stacked_widget.currentIndex()
            window_name = list(self.windows.keys())[idx]
        instruction = self.instructions.get(window_name, "Инструкция недоступна для этого окна.")
        self.instruction_label.setText(f"<b>Инструкция:</b><br>{instruction}")
        if not self.instruction_panel.isVisible():
            self.instruction_label.clear()
    def toggle_instruction_panel(self, *args):
        visible = not self.instruction_panel.isVisible()
        duration = 220
        if visible:
            self.instruction_panel.setVisible(True)
            self.update_instruction_panel()
            self.instruction_panel.setMaximumHeight(0)
            self.anim = QPropertyAnimation(self.instruction_panel, b"maximumHeight")
            self.anim.setDuration(duration)
            self.anim.setStartValue(0)
            self.anim.setEndValue(120)
            self.anim.start()
        else:
            self.anim = QPropertyAnimation(self.instruction_panel, b"maximumHeight")
            self.anim.setDuration(duration)
            self.anim.setStartValue(self.instruction_panel.maximumHeight())
            self.anim.setEndValue(0)
            def on_finished():
                self.instruction_panel.setVisible(False)
                self.instruction_label.clear()
            self.anim.finished.connect(on_finished)
            self.anim.start()
    def handle_internet_status(self, status, *args):
        self.internet_available = status
        if self.internet_available:
            self.enable_functionality()
        else:
            self.disable_functionality()
    def enable_functionality(self, *args):
        if self.key_validation_thread:
            self.key_validation_thread.running = True
    def disable_functionality(self, *args):
        if self.key_validation_thread:
            self.key_validation_thread.running = False
    def write_config(self, api_id=None, api_hash=None, session_folder=None, proxy_config=None):
        api_id = api_id if api_id is not None else getattr(self, 'api_id', '')
        api_hash = api_hash if api_hash is not None else getattr(self, 'api_hash', '')
        session_folder = session_folder if session_folder is not None else getattr(self, 'session_folder', '')
        bot_token_folder = getattr(self, 'bot_token_folder', '')
        proxy = proxy_config if proxy_config is not None else getattr(self, 'proxy_config', {}) or {}
        config_path = "config.txt"
        old_lines = []
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not (
                        line.startswith("API_ID=")
                        or line.startswith("API_HASH=")
                        or line.startswith("SESSION_FOLDER=")
                        or line.startswith("BOT_TOKEN_FOLDER=")
                        or line.startswith("PROXY_TYPE=")
                        or line.startswith("PROXY_IP=")
                        or line.startswith("PROXY_PORT=")
                        or line.startswith("PROXY_LOGIN=")
                        or line.startswith("PROXY_PASSWORD=")
                    ):
                        old_lines.append(line)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"API_ID={api_id}\n")
            f.write(f"API_HASH={api_hash}\n")
            f.write(f"SESSION_FOLDER={session_folder}\n")
            f.write(f"BOT_TOKEN_FOLDER={bot_token_folder}\n")
            f.write(f"PROXY_TYPE={proxy.get('type', '')}\n")
            f.write(f"PROXY_IP={proxy.get('ip', '')}\n")
            f.write(f"PROXY_PORT={proxy.get('port', '')}\n")
            f.write(f"PROXY_LOGIN={proxy.get('login', '')}\n")
            f.write(f"PROXY_PASSWORD={proxy.get('password', '')}\n")
            for line in old_lines:
                f.write(line)
        try:
            new_config = load_config()
            config_upper = {k.upper(): v for k, v in new_config.items()}
            if 'PROXY_CONFIG' in config_upper and isinstance(config_upper['PROXY_CONFIG'], dict):
                config_upper['PROXY_CONFIG'] = {k.upper(): v for k, v in config_upper['PROXY_CONFIG'].items()}
            self.config_changed.emit(config_upper)
        except Exception:
            pass
    def open_api_params(self, *args):
        dialog = QDialog(self)
        dialog.setWindowTitle("Параметры Api")
        form = QFormLayout(dialog)
        api_id_edit = QLineEdit(dialog)
        api_id_edit.setText(str(getattr(self, 'api_id', '')))
        api_hash_edit = QLineEdit(dialog)
        api_hash_edit.setText(getattr(self, 'api_hash', ''))
        form.addRow("API ID:", api_id_edit)
        form.addRow("API Hash:", api_hash_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(lambda: (self._save_api_params(api_id_edit.text(), api_hash_edit.text()), dialog.accept()))
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
    def _save_api_params(self, api_id_str, api_hash, *args):
        try:
            api_id = int(api_id_str)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "API ID должен быть числом")
            return
        self.api_id = api_id
        self.api_hash = api_hash
        self.write_config()
        QMessageBox.information(self, "Сохранено", "Параметры Api сохранены")
    def open_proxy_params(self, *args):
        dialog = QDialog(self)
        dialog.setWindowTitle("Параметры прокси")
        form = QFormLayout(dialog)
        cfg = getattr(self, 'proxy_config', {}) or {}
        proxy_str_edit = QLineEdit(dialog)
        current_str = ''
        if cfg.get('type') and cfg.get('ip') and cfg.get('port'):
            if cfg.get('login') and cfg.get('password'):
                current_str = f"{cfg.get('type','http')}://{cfg.get('login')}:{cfg.get('password')}@{cfg.get('ip')}:{cfg.get('port')}"
            else:
                current_str = f"{cfg.get('type','http')}://{cfg.get('ip')}:{cfg.get('port')}"
        proxy_str_edit.setText(current_str)
        type_edit = QLineEdit(dialog)
        ip_edit = QLineEdit(dialog)
        port_edit = QLineEdit(dialog)
        login_edit = QLineEdit(dialog)
        pwd_edit = QLineEdit(dialog)
        pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        type_edit.setText(cfg.get('type', ''))
        ip_edit.setText(cfg.get('ip', ''))
        port_edit.setText(cfg.get('port', ''))
        login_edit.setText(cfg.get('login', ''))
        pwd_edit.setText(cfg.get('password', ''))
        form.addRow("Прокси строка:", proxy_str_edit)
        form.addRow("Тип:", type_edit)
        form.addRow("IP:", ip_edit)
        form.addRow("Порт:", port_edit)
        form.addRow("Логин:", login_edit)
        form.addRow("Пароль:", pwd_edit)
        def on_proxy_str_change():
            parsed = parse_proxy_string(proxy_str_edit.text())
            type_edit.setText(parsed['type'])
            ip_edit.setText(parsed['ip'])
            port_edit.setText(parsed['port'])
            login_edit.setText(parsed['login'])
            pwd_edit.setText(parsed['password'])
        proxy_str_edit.textChanged.connect(on_proxy_str_change)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        form.addWidget(buttons)
        def on_accept():
            parsed = parse_proxy_string(proxy_str_edit.text())
            proxy = {
                'type': type_edit.text() or parsed['type'],
                'ip': ip_edit.text() or parsed['ip'],
                'port': port_edit.text() or parsed['port'],
                'login': login_edit.text() or parsed['login'],
                'password': pwd_edit.text() or parsed['password']
            }
            self._save_proxy_params(proxy)
            dialog.accept()
        buttons.accepted.connect(on_accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()
    def _save_proxy_params(self, proxy, *args):
        self.proxy_config = proxy
        self.write_config()
        QMessageBox.information(self, "Сохранено", "Параметры прокси сохранены")
    def choose_session_folder(self, *args):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с сессиями")
        if folder:
            if folder == self.session_folder:
                QMessageBox.information(self, "Информация", "Выбрана та же папка, что и текущая.")
                return     
            old_folder = self.session_folder
            self.session_folder = folder
            self.write_config()
            self.config_changed.emit({'SESSION_FOLDER': folder})
            for window_name, window in self.windows.items():
                if hasattr(window, 'session_window') and hasattr(window.session_window, 'update_session_folder'):
                    window.session_window.update_session_folder(folder)
            QMessageBox.information(self, "Сохранено", f"Папка с сессиями: {folder}")
    def choose_bot_token_folder(self, *args):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с токенами ботов")
        if folder:
            if folder == self.bot_token_folder:
                QMessageBox.information(self, "Информация", "Выбрана та же папка, что и текущая.")
                return 
            old_folder = self.bot_token_folder
            self.bot_token_folder = folder
            if not hasattr(self, 'session_folder') or not self.session_folder:
                self.session_folder = os.path.dirname(folder)            
            self.write_config()
            config_updates = {
                'BOT_TOKEN_FOLDER': folder,
                'SESSION_FOLDER': self.session_folder
            }
            self.config_changed.emit(config_updates)
            for window_name, window in self.windows.items():
                if hasattr(window, 'bot_token_window') and hasattr(window.bot_token_window, 'update_token_folder'):
                    window.bot_token_window.update_token_folder(folder)
                if hasattr(window, 'session_window') and hasattr(window.session_window, 'update_session_folder'):
                    window.session_window.update_session_folder(self.session_folder)            
            QMessageBox.information(self, "Сохранено", f"Папка с токенами ботов: {folder}\nПапка с сессиями: {self.session_folder}")
    def open_create_text_dialog(self, *args):
        dlg = QDialog(self)
        dlg.setWindowTitle("Создать txt файл")
        dlg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(dlg)
        input = QLineEdit(dlg)
        input.setPlaceholderText("Введите имя файла без расширения (.txt)")
        layout.addWidget(input)
        btn = QPushButton("Создать txt", dlg)
        layout.addWidget(btn)
        def on_create():
            name = input.text().strip()
            if not name:
                QMessageBox.warning(dlg, "Ошибка", "Введите имя файла.")
                return
            if not name.lower().endswith('.txt'):
                name += '.txt'
            root = get_app_directory()
            path = os.path.join(root, name)
            try:
                with open(path, 'x', encoding='utf-8') as f:
                    pass
                QMessageBox.information(dlg, "Успех", f"Файл создан: {path}")
                dlg.accept()
            except FileExistsError:
                QMessageBox.warning(dlg, "Ошибка", f"Файл уже существует: {path}")
            except Exception as e:
                QMessageBox.warning(dlg, "Ошибка", f"Не удалось создать файл: {e}")
        btn.clicked.connect(on_create)
        dlg.exec()
    def open_edit_txt_dialog(self, *args):
        file_path, _ = QFileDialog.getOpenFileName(self, "Открыть txt файл", "", "Text Files (*.txt)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть файл: {e}")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Редактировать: {os.path.basename(file_path)}")
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit(dlg)
        text_edit.setPlainText(content)
        layout.addWidget(text_edit)
        save_btn = QPushButton("Сохранить", dlg)
        layout.addWidget(save_btn)
        def on_save():
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_edit.toPlainText())
                QMessageBox.information(dlg, "Успех", f"Файл сохранён: {file_path}")
                dlg.accept()
            except Exception as e:
                QMessageBox.warning(dlg, "Ошибка", f"Не удалось сохранить файл: {e}")
        save_btn.clicked.connect(on_save)
        dlg.exec()
