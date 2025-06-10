import os, re, json, asyncio, random, logging, threading, datetime, traceback
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLineEdit, QLabel,
    QCheckBox, QSizePolicy, QGroupBox
)
from PyQt6.QtGui import QFont, QIcon
from telethon import TelegramClient, errors
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError,
)
from ui.okak import ErrorReportDialog
class TSMFilter(logging.Filter):
    def filter(self, record):
        return "TSMSendMessageToUIServer" not in record.getMessage()
logger = logging.getLogger()
logger.setLevel(logging.ERROR)
logger.addFilter(TSMFilter())
class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    def __init__(self, api_id, api_hash, session_folder, phone_numbers, task):
        super().__init__()
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_folder = session_folder
        self.phone_numbers = phone_numbers
        self.task = task
    def run(self, *args, **kwargs):
        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.process_multiple_numbers(self.phone_numbers, self.task))
            except RuntimeError:
                asyncio.run(self.process_multiple_numbers(self.phone_numbers, self.task))
        except Exception as e:
            tb = traceback.format_exc()
            self.error_signal.emit(tb)
    async def process_multiple_numbers(self, phone_numbers, task):
        for phone_number in phone_numbers:
            try:
                await task(phone_number)
            except Exception as e:
                tb = traceback.format_exc()
                self.error_signal.emit(tb)
def load_config():
    try:
        with open('config.txt', 'r') as file:
            return {k: v for line in file if '=' in line and line.strip() for k, v in [line.strip().split('=', 1)]}
    except Exception:
        return {}
def load_proxy(config):
    try:
        proxy_type = config["PROXY_TYPE"]
        addr = config["PROXY_IP"]
        port = int(config["PROXY_PORT"])
    except (KeyError, ValueError, TypeError):
        return None
    return {
        "proxy_type": proxy_type,
        "addr": addr,
        "port": port,
        "username": config.get("PROXY_LOGIN"),
        "password": config.get("PROXY_PASSWORD"),
    }
def ensure_session_folder(config):
    session_folder = config.get("SESSION_FOLDER")
    if not session_folder:
        session_folder = os.path.join(os.getcwd(), "sessions")
    session_folder = os.path.abspath(session_folder)
    os.makedirs(session_folder, exist_ok=True)
    config["SESSION_FOLDER"] = session_folder
    config_path = 'config.txt'
    session_line = f'SESSION_FOLDER={session_folder}'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if re.match(r'^SESSION_FOLDER=', line):
                lines[i] = session_line + '\n'
                found = True
                break
        if not found:
            lines.append(session_line + '\n')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    else:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(session_line + '\n')
    return session_folder
class PhysicalSimWindow(QWidget):
    def __init__(self, api_id, api_hash, session_folder, main_window, *args):
        super().__init__(*args)
        self.main_window = main_window
        if hasattr(self.main_window, 'config_changed'):
            self.main_window.config_changed.connect(self.on_config_changed)
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_folder = session_folder
        config = load_config()
        self.session_folder = ensure_session_folder(config)
        if not config or not config.get('API_ID') or not config.get('API_HASH'):
            self.append_log("config.txt отсутствует или параметры пустые. Вы новый пользователь. Пожалуйста, заполните параметры (API_ID, API_HASH, session_folder, proxy) через кнопки на верхней панели.")
        if not self._check_api_credentials():
            self.append_log("Пожалуйста, заполните параметры API_ID и API_HASH через кнопки на верхней панели.")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QHBoxLayout(self)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_groupbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        proxy_widget = QWidget()
        proxy_layout = QVBoxLayout(proxy_widget)
        self.use_proxy_checkbox = QCheckBox("Использовать прокси", self)
        proxy_layout.addWidget(self.use_proxy_checkbox)
        left_layout.addWidget(proxy_widget)
        phone_widget = QWidget()
        phone_layout = QVBoxLayout(phone_widget)
        self.phone_input = QLineEdit(self)
        self.phone_input.setPlaceholderText("Введите номер телефона 7, +7 формат")
        phone_layout.addWidget(self.phone_input)
        self.phone_button = QPushButton("Подтвердить номер", self)
        self.phone_button.setIcon(QIcon.fromTheme("phone"))
        self.phone_button.clicked.connect(self.handle_send_code)
        phone_layout.addWidget(self.phone_button)
        self.code_input = QLineEdit(self)
        self.code_input.setPlaceholderText("Введите код из SMS телеграм")
        self.code_input.setEnabled(False)
        phone_layout.addWidget(self.code_input)
        self.code_button = QPushButton("Отправить код", self)
        self.code_button.setIcon(QIcon.fromTheme("message"))
        self.code_button.clicked.connect(self.handle_authentication)
        self.code_button.setEnabled(False)
        phone_layout.addWidget(self.code_button)
        self.password_input = QLineEdit(self)
        self.password_input.setPlaceholderText("Введите облачный пароль (если запросят)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setEnabled(False)
        phone_layout.addWidget(self.password_input)
        self.password_button = QPushButton("Отправить пароль", self)
        self.password_button.setIcon(QIcon.fromTheme("key"))
        self.password_button.clicked.connect(self.handle_password)
        self.password_button.setEnabled(False)
        phone_layout.addWidget(self.password_button)
        left_layout.addWidget(proxy_widget)
        left_layout.addWidget(phone_widget)
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        self.stop_button = QPushButton("Остановить процесс", self)
        self.stop_button.setIcon(QIcon.fromTheme("stop"))
        self.stop_button.clicked.connect(self.stop_process)
        control_layout.addWidget(self.stop_button)
        self.status_label = QLabel(self)
        control_layout.addWidget(self.status_label)
        left_layout.addWidget(control_widget)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area)
        left_layout.addWidget(log_widget)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        explanation_text = QTextEdit()
        explanation_text.setReadOnly(True)
        explanation_text.setStyleSheet("")
        explanation_font = QFont()
        explanation_font.setPointSize(10)
        explanation_text.setFont(explanation_font)
        explanation_content = """
<h3>Инструкция по созданию сессий:</h3>
<ul>
<li>Параметры API нужно ввести до создания сессии - подробнее можно уточнить в окне "информация" в нижнем углу</li>
<li>Параметры девайса, версии и системы генерируются автоматически и все сохраняется в JSON</li>
<li>Все SMS приходят на аккаунт телеграма</li>
</ul>
"""
        explanation_text.setHtml(explanation_content)
        right_layout.addWidget(explanation_text)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(right_panel, 1)
        self.phone_code_hash = None
        self.random_device = None
        self.setLayout(main_layout)
    def _check_api_credentials(self, *args, **kwargs):
        if not self.api_id or not self.api_hash or str(self.api_id) == '0' or not str(self.api_hash).strip():
            error_msg = "Ошибка: Не заданы параметры API_ID или API_HASH. Укажите их в панеле сверху перед началом работы."
            self.append_log(error_msg)
            return False
        return True
    def _get_proxy_config(self, *args, **kwargs):
        use_proxy = self.use_proxy_checkbox.isChecked()
        proxy = load_proxy(load_config()) if use_proxy else None
        if use_proxy:
            if proxy and proxy.get('addr') and proxy.get('port'):
                proxy_str = (
                    f"{proxy.get('proxy_type','')}:{proxy.get('addr','')}:{proxy.get('port','')}"
                    + (f":{proxy.get('username','')}" if proxy.get('username') else '')
                    + (f":{proxy.get('password','')}" if proxy.get('password') else '')
                )
                self.worker_thread.log_signal.emit(f"🌐 Используется прокси: {proxy.get('addr', 'не указан')}:{proxy.get('port', 'не указан')}")
            else:
                proxy_str = False
                self.worker_thread.log_signal.emit("⚠️ Прокси включен, но не настроен в конфигурации")
        else:
            proxy_str = False
            self.worker_thread.log_signal.emit("ℹ️ Прокси не используется")
        return proxy, proxy_str
    def _create_telegram_client(self, session_path, proxy=None, *args, **kwargs):
        if not hasattr(self, 'random_device') or not self.random_device:
            device_models = [
                "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max",
                "iPhone 14", "iPhone 14 Pro", "iPhone 14 Pro Max",
                "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max",
                "iPhone 16", "iPhone 16 Pro", "iPhone 16 Pro Max"
            ]
            self.random_device = random.choice(device_models)
        return TelegramClient(
            session_path,
            self.api_id,
            self.api_hash,
            device_model=self.random_device,
            system_version="18.5",
            app_version="8.4",
            proxy=proxy
        )
    def append_log(self, message, *args, **kwargs):
        def do_log():
            if hasattr(self, 'log_area'):
                if "✅" in message:
                    color = "#2ecc71"
                elif "⛔" in message or "Ошибка" in message:
                    color = "#e74c3c"
                elif "⚠️" in message:
                    color = "#f1c40f"
                else:
                    color = None
                if color:
                    self.log_area.append(f'<span style="color: {color};">{message}</span>')
                else:
                    self.log_area.append(f'<span style="color: palette(window-text);">{message}</span>')
                self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
            logging.info(message)
        if threading.current_thread() is threading.main_thread():
            do_log()
        else:
            QTimer.singleShot(0, do_log)
    def handle_thread_error(self, error_message, *args, **kwargs):
        try:
            with open(self._error_log_path, 'a', encoding='utf-8') as f:
                f.write((error_message or '(traceback пустой)') + '\n')
        except Exception:
            pass
        QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(self._error_log_path))
    def handle_send_code(self, *args, **kwargs):
        phone_number = self.phone_input.text().strip()
        if not phone_number:
            self.append_log("⛔ Введите номер телефона")
            return
        self.log_area.clear()
        self.append_log("✅ Начинаем отправку кода...")
        if not self._check_api_credentials():
            return
        phone_numbers = [num.strip().replace(" ", "") for num in self.phone_input.text().split(",") if num.strip()]
        if not phone_numbers:
            self.append_log("Ошибка: Номер телефона не введен")
            return
        self.worker_thread = WorkerThread(self.api_id, self.api_hash, self.session_folder, phone_numbers, self.send_code)
        self.worker_thread.error_signal.connect(self.handle_thread_error)
        self.worker_thread.log_signal.connect(self.append_log)
        self.worker_thread.start()
    async def send_code(self, phone_number, *args, **kwargs):
        if not self._check_api_credentials():
            self.worker_thread.log_signal.emit("Ошибка: Не заданы параметры API_ID или API_HASH. Укажите их в настройках перед началом работы.")
            return
        proxy, proxy_str = self._get_proxy_config()
        self.last_used_proxy_str = proxy_str
        clean_number = phone_number.replace("+", "")
        session_path = os.path.join(self.session_folder, f"{clean_number}.session")
        self.client = self._create_telegram_client(session_path, proxy)
        try:
            self.worker_thread.log_signal.emit(f"Попытка подключения для {phone_number}...")
            await self.client.connect()
            self.worker_thread.log_signal.emit(f"Отправка запроса на код для номера: {phone_number}")
            sent_code = await self.client.send_code_request(phone_number)
            self.worker_thread.log_signal.emit(f"✅Код отправлен на номер {phone_number}. Введите код и нажмите 'Отправить код'.")
            self.code_input.setEnabled(True)
            self.code_button.setEnabled(True)
            self.phone_code_hash = sent_code.phone_code_hash
        except FloodWaitError as e:
            self.worker_thread.log_signal.emit(f"Ошибка: слишком много попыток, попробуйте позже через {e.seconds} секунд.")
        except Exception as e:
            self.worker_thread.log_signal.emit(f"Error while sending code or retrieving user data: {e}")
            logging.error(f"Error: {e}")
        finally:
            await self.client.disconnect()
    def _generate_device_info(self, *args, **kwargs):

        return {
            "sdk": self._generate_sdk(),
            "system_version": self._generate_system_version(),
            "app_version": self._generate_app_version()
        }
    def _generate_sdk(self, *args, **kwargs):
        import uuid
        unique_part = uuid.uuid4().hex[:6].upper()
        date_part = datetime.datetime.now().strftime("%Y%m%d")
        return f"SDK-{date_part}-{unique_part}"
    def _generate_system_version(self, *args, **kwargs):
        major = random.randint(14, 18)
        minor = random.randint(0, 2)
        patch = random.randint(0, 9)
        return f"{major}.{minor}.{patch}"
    def _generate_app_version(self, *args, **kwargs):
        major = 8
        minor = random.randint(2, 6)
        build = random.randint(20000, 30000)
        return f"{major}.{minor} ({build}) AppStore"
    async def create_and_save_json(self, client, session_path, proxy_str, *args):
        try:
            user = await client.get_me()
        except Exception as e:
            self.worker_thread.log_signal.emit(f"Ошибка получения данных о пользователе: {e}")
            user = None
        device_info = self._generate_device_info()
        json_data = {
            "app_id": self.api_id,
            "app_hash": self.api_hash,
            "sdk": device_info["sdk"],
            "device": self.random_device if hasattr(self, "random_device") else None,
            "app_version": device_info["app_version"],
            "system_version": device_info["system_version"],
            "lang_pack": user.lang_code if (user and hasattr(user, "lang_code")) else "ios",
            "system_lang_pack": "en",
            "twoFA": self.password_input.text() if self.password_input.text() else None,
            "id": user.id if user else None,
            "phone": user.phone if (user and hasattr(user, "phone")) else None,
            "username": user.username if user else None,
            "is_premium": user.premium if (user and hasattr(user, "premium")) else False,
            "premium_expiry": None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "has_profile_pic": bool(user.photo) if (user and hasattr(user, "photo")) else False,
            "spamblock": False,
            "spamblock_end_date": None,
            "session_file": os.path.basename(session_path).replace(".session", ""),
            "last_connect_date": None,
            "register_time": None,
            "proxy": proxy_str,
            "last_check_time": datetime.datetime.now().isoformat(),
            "ipv6": False
        }
        json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        json_filename = os.path.splitext(session_path)[0] + ".json"
        with open(json_filename, "w", encoding="utf-8") as f:
            f.write(json_str)
        self.worker_thread.log_signal.emit(f"✅JSON файл создан: {json_filename}")
        self.worker_thread.log_signal.emit("Вы можете автоматически заполнить Имя-Фамилию-Username-Bio в модуле Менеджер аккаунтов.")
    def handle_authentication(self, *args):
        phone_numbers = [num.strip().replace(" ", "") for num in self.phone_input.text().split(",") if num.strip()]
        code = self.code_input.text().strip()
        if not code:
            self.worker_thread.log_signal.emit("Ошибка: Код не введен")
            return
        self.worker_thread = WorkerThread(self.api_id, self.api_hash, self.session_folder,
                                          phone_numbers, lambda num: self.authenticate(num, code))
        self.worker_thread.log_signal.connect(self.append_log)
        self.worker_thread.start()
    async def authenticate(self, phone_number, code, *args):
        if not self._check_api_credentials():
            self.worker_thread.log_signal.emit("Ошибка: Не заданы параметры API_ID или API_HASH. Укажите их в настройках перед началом работы.")
            return
        clean_number = phone_number.replace("+", "")
        session_path = os.path.join(self.session_folder, f"{clean_number}.session")
        proxy, proxy_str = self._get_proxy_config()
        client = self._create_telegram_client(session_path, proxy)
        try:
            await client.connect()
            self.worker_thread.log_signal.emit(f"Авторизация для {phone_number}")
            if not self.phone_code_hash:
                self.worker_thread.log_signal.emit("Ошибка: phone_code_hash отсутствует. Попробуйте запросить код заново.")
                return
            if not client.is_connected():
                self.worker_thread.log_signal.emit("Ошибка: Клиент Telegram не подключен. Попробуйте снова.")
                return
            await client.sign_in(phone_number, code, phone_code_hash=self.phone_code_hash)
            self.worker_thread.log_signal.emit(f"✅Аккаунт {phone_number} успешно авторизован!")
            await self.create_and_save_json(client, session_path, proxy_str)
            self.worker_thread.log_signal.emit("Вы можете автоматически заполнить Имя-Фамилию-Username-Bio в модуле Менеджер аккаунтов.")
        except SessionPasswordNeededError:
            self.worker_thread.log_signal.emit("Введите облачный пароль (Если запросят)")
            self.password_input.setEnabled(True)
            self.password_button.setEnabled(True)
        except FloodWaitError as e:
            self.worker_thread.log_signal.emit(f"Error: Flood limit, try again in {e.seconds} seconds.")
        except errors.PasswordHashInvalidError:
            self.worker_thread.log_signal.emit("Ошибка: Неверный облачный пароль. Проверьте введенные данные.")
        except Exception as e:
            self.worker_thread.log_signal.emit(f"Authentication error: {e}")
        finally:
            await client.disconnect()
    def handle_password(self, *args):
        phone_number = self.phone_input.text().strip().replace(" ", "")
        password = self.password_input.text().strip()
        if not password:
            self.worker_thread.log_signal.emit("Ошибка: Пароль не введен")
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.send_password(phone_number, password))
        except RuntimeError:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_password(phone_number, password))
            except RuntimeError:
                asyncio.run(self.send_password(phone_number, password))
    async def send_password(self, phone_number, password, *args):
        if not self._check_api_credentials():
            self.worker_thread.log_signal.emit("Ошибка: Не заданы параметры API_ID или API_HASH. Укажите их в настройках перед началом работы.")
            return
        clean_number = phone_number.replace("+", "")
        session_path = os.path.join(self.session_folder, f"{clean_number}.session")
        proxy, proxy_str = self._get_proxy_config()
        client = self._create_telegram_client(session_path, proxy)
        try:
            await client.connect()
            if not self.phone_code_hash:
                self.worker_thread.log_signal.emit("Ошибка: phone_code_hash отсутствует. Попробуйте запросить код заново.")
                return
            if not client.is_connected():
                self.worker_thread.log_signal.emit("Ошибка: Клиент Telegram не подключен. Попробуйте снова.")
                return
            await client.sign_in(password=password, phone_code_hash=self.phone_code_hash, *args)
            self.worker_thread.log_signal.emit(f"Пароль принят, аккаунт {phone_number} успешно авторизован!")
            await self.create_and_save_json(client, session_path, proxy_str)
            self.password_input.setEnabled(False)
            self.password_button.setEnabled(False)
        except errors.PasswordHashInvalidError:
            self.worker_thread.log_signal.emit("Ошибка: Неверный облачный пароль. Проверьте введенные данные.")
        except Exception as e:
            self.worker_thread.log_signal.emit(f"Ошибка при вводе пароля для {phone_number}: {e}")
        finally:
            await client.disconnect()
    def stop_process(self, *args):
        if hasattr(self, 'worker_thread'):
            self.worker_thread.log_signal.emit("Процесс остановлен.")
        else:
            self.append_log("Процесс остановлен.")
        if hasattr(self, 'client') and self.client.is_connected():
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.client.disconnect())
            except RuntimeError:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.client.disconnect())
                except RuntimeError:
                    asyncio.run(self.client.disconnect())
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.quit()
            self.worker.wait()
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            if hasattr(self, 'worker_thread'):
                self.worker_thread.log_signal.emit("Процесс авторизации остановлен.")
    def on_config_changed(self, config, *args):
        self.api_id = config.get('api_id', self.api_id)
        self.api_hash = config.get('api_hash', self.api_hash)
        self.session_folder = ensure_session_folder(config)
        if hasattr(self, 'use_proxy_checkbox') and self.use_proxy_checkbox:
            self.use_proxy_checkbox.setChecked(bool(config.get('PROXY_TYPE')))
