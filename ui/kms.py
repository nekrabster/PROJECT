import os
import sys
import time
import threading
import random
import ctypes
import hashlib
import base64
from typing import List
from .gulick import initialize_protection as init_anti_debug, protected
from .codik import execute_decoy_operations, create_dynamic_protection
from .integraly import initialize_integrity_protection, stop_integrity_protection
from .adv import initialize_advanced_obfuscation, create_fake_activity
from .decorators import heavy_obfuscation
from .filya import initialize_file_protection, stop_file_protection

IS_FROZEN = getattr(sys, 'frozen', False)

class MasterProtection:
    def __init__(self):
        self._protection_active = False
        self._initialization_complete = False
        self._protection_threads = []
        self._stealth_mode = True
    def _create_decoy_modules(self):
        decoy_names = [
            'license_validator', 'server_connector', 'crypto_engine',
            'database_manager', 'session_handler', 'auth_provider'
        ]
        for name in decoy_names:
            try:
                decoy_code = f'''
import hashlib
import base64
import time
import random

class {name.title().replace("_", "")}:
    def __init__(self):
        self.initialized = False
        self.last_check = time.time()
        self.validation_key = "{random.randint(100000, 999999)}"

    def validate(self):
        if not self.initialized:
            return False
        current_time = time.time()
        if current_time - self.last_check > 3600:
            return False
        return True

    def refresh_token(self):
        self.last_check = time.time()
        new_key = hashlib.md5(str(random.randint(1000, 9999)).encode()).hexdigest()
        self.validation_key = new_key[:16]
        return self.validation_key

    def connect(self, endpoint="127.0.0.1"):

        time.sleep(random.uniform(0.1, 0.5))
        return random.choice([True, False])

    def encrypt_data(self, data):

        encoded = base64.b64encode(str(data).encode()).decode()
        return encoded[::-1]

instance = {name.title().replace("_", "")}()
'''
                exec(decoy_code, globals())
            except Exception:
                continue
    @heavy_obfuscation
    def _setup_environment_checks(self, *args,**kwargs):
        def environment_monitor():
            while self._protection_active:
                try:
                    if self._check_cpu_timing():
                        self._trigger_emergency_shutdown("CPU timing anomaly")
                        return
                    if random.random() < 0.2:
                        if self._check_network_monitoring():
                            self._trigger_emergency_shutdown("Network monitoring detected")
                            return
                    if random.random() < 0.15:
                        if self._check_file_monitoring():
                            self._trigger_emergency_shutdown("File monitoring detected")
                            return
                    execute_decoy_operations()
                    time.sleep(random.uniform(2.0, 5.0))
                except Exception:
                    time.sleep(3.0)
        thread = threading.Thread(target=environment_monitor, daemon=True)
        thread.start()
        self._protection_threads.append(thread)
    @heavy_obfuscation
    def _check_cpu_timing(self, *args,**kwargs) -> bool:
        if IS_FROZEN:
            return False
        try:
            iterations = 10000
            start_time = time.perf_counter()
            result = sum(i * i for i in range(iterations))
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            if execution_time > 0.1 or execution_time < 0.001:
                return True
            timings = []
            for _ in range(5):
                start = time.perf_counter()
                sum(i for i in range(1000))
                end = time.perf_counter()
                timings.append(end - start)
            avg = sum(timings) / len(timings)
            variance = sum((t - avg) ** 2 for t in timings) / len(timings)
            std_dev = variance ** 0.5
            if std_dev > avg * 0.5:
                return True
        except Exception:
            pass
        return False
    def _check_network_monitoring(self, *args,**kwargs) -> bool:
        if IS_FROZEN:
            return False
        try:
            import socket
            import subprocess
            try:
                result = subprocess.run(['netstat', '-an'],
                                      capture_output=True,
                                      text=True,
                                      timeout=5)
                if result.returncode == 0:
                    output = result.stdout.lower()
                    suspicious_ports = ['8080', '8888', '9999', '4444', '1337']
                    for port in suspicious_ports:
                        if f':{port}' in output:
                            return True
            except Exception:
                pass
            test_ports = [8080, 8888, 3128, 8118]
            for port in test_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.1)
                    result = sock.connect_ex(('127.0.0.1', port))
                    sock.close()
                    if result == 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False
    def _check_file_monitoring(self, *args,**kwargs) -> bool:
        if IS_FROZEN:
            return False
        try:
            import tempfile
            import hashlib
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                test_data = os.urandom(1024)
                temp_file.write(test_data)
            time.sleep(0.1)
            try:
                with open(temp_path, 'rb') as f:
                    read_data = f.read()
                if read_data != test_data:
                    os.unlink(temp_path)
                    return True
                import stat
                file_stat = os.stat(temp_path)
                current_time = time.time()
                if abs(file_stat.st_mtime - current_time) > 1.0:
                    os.unlink(temp_path)
                    return True
                os.unlink(temp_path)
            except Exception:
                pass
        except Exception:
            pass
        return False
    def _setup_honeypots(self):
        """Настройка ложных данных (honeypots)"""
        fake_globals = {
            'LICENSE_KEY': 'FAKE-' + ''.join(random.choices('ABCDEF0123456789', k=32)),
            'SERVER_URL': 'https://fake-server.example.com/api/v1/',
            'API_SECRET': hashlib.md5(b'fake_secret').hexdigest(),
            'ENCRYPTION_KEY': base64.b64encode(os.urandom(32)).decode(),
            'DATABASE_PASSWORD': 'fake_password_123',
            'ADMIN_TOKEN': 'admin_' + str(random.randint(100000, 999999))
        }
        for key, value in fake_globals.items():
            globals()[key] = value
        def fake_authenticate_user(username, password):
            time.sleep(random.uniform(0.1, 0.3))
            return random.choice([True, False])
        def fake_decrypt_license(encrypted_data):
            time.sleep(random.uniform(0.2, 0.5))
            return "VALID_LICENSE_" + str(random.randint(1000, 9999))
        def fake_connect_database():
            time.sleep(random.uniform(0.3, 0.7))
            return {"status": "connected", "id": random.randint(1, 1000)}
        globals()['authenticate_user'] = fake_authenticate_user
        globals()['decrypt_license'] = fake_decrypt_license
        globals()['connect_database'] = fake_connect_database
    @heavy_obfuscation
    def _trigger_emergency_shutdown(self, reason: str):
        try:
            if self._stealth_mode:
                normal_errors = [
                    "Произошла непредвиденная ошибка. Приложение будет закрыто.",
                    "Ошибка инициализации. Перезапустите приложение.",
                    "Не удалось загрузить необходимые компоненты.",
                    "Ошибка доступа к системным ресурсам."
                ]
                error_msg = random.choice(normal_errors)
                try:
                    ctypes.windll.user32.MessageBoxW(0, error_msg, "Ошибка", 0x30)
                except:
                    print(error_msg)
            else:
                print(f"Protection triggered: {reason}")
            for _ in range(random.randint(3, 8)):
                fake_data = os.urandom(512)
                fake_hash = hashlib.sha256(fake_data).hexdigest()
                time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass
        os._exit(0)
    @heavy_obfuscation
    def initialize(self, stealth_mode: bool = True, *args,**kwargs):
        if self._protection_active:
            return
        self._stealth_mode = stealth_mode
        try:
            initialize_advanced_obfuscation()
            create_fake_activity()
            self._create_decoy_modules()
            self._setup_honeypots()
            init_anti_debug()
            initialize_integrity_protection()
            initialize_file_protection()
            self._setup_environment_checks()
            dynamic_check = create_dynamic_protection()
            def dynamic_monitor():
                while self._protection_active:
                    try:
                        if dynamic_check():
                            self._trigger_emergency_shutdown("Dynamic check failed")
                            return
                        time.sleep(random.uniform(3.0, 8.0))
                    except Exception:
                        time.sleep(5.0)
            dynamic_thread = threading.Thread(target=dynamic_monitor, daemon=True)
            dynamic_thread.start()
            self._protection_threads.append(dynamic_thread)
            self._protection_active = True
            self._initialization_complete = True
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            if not stealth_mode:
                print(f"Protection initialization failed: {e}")
            self._protection_active = True
    def is_active(self, *args,**kwargs) -> bool:
        return self._protection_active and self._initialization_complete
    def shutdown(self, *args,**kwargs):
        self._protection_active = False
        try:
            stop_integrity_protection()
            stop_file_protection()
        except Exception:
            pass
        for thread in self._protection_threads:
            try:
                if thread.is_alive():
                    thread.join(timeout=1.0)
            except Exception:
                pass
_master_protection = MasterProtection()
@heavy_obfuscation
def initialize_master_protection(stealth_mode: bool = True):
    _master_protection.initialize(stealth_mode=True)
def is_protection_active() -> bool:
    return _master_protection.is_active()
def shutdown_protection():
    _master_protection.shutdown()
def critical_function(func):
    @protected
    @heavy_obfuscation
    def wrapper(*args, **kwargs):
        if not is_protection_active():
            initialize_master_protection()
            time.sleep(0.1)
        if random.random() < 0.05:
            dynamic_check = create_dynamic_protection()
            if dynamic_check():
                _master_protection._trigger_emergency_shutdown("Critical function check failed")
        return func(*args, **kwargs)
    return wrapper
