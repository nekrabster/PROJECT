import os
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
class MasterProtection:
    def __init__(self):
        self._protection_active = False
        self._initialization_complete = False
        self._protection_threads = []
        self._stealth_mode = True
        self._user_safe_mode = True
        self._performance_mode = True
    def _is_user_system(self, *args,**kwargs):
        try:
            import psutil
            process_count = len(list(psutil.process_iter()))
            memory = psutil.virtual_memory()
            boot_time = psutil.boot_time()
            current_time = time.time()
            uptime = current_time - boot_time
            username = os.getenv('USERNAME', '').lower()
            if process_count > 50 and memory.total > 4 * 1024 * 1024 * 1024 and uptime > 3600:
                return True
            if username not in ['sandbox', 'malware', 'virus', 'sample', 'test']:
                return True
            return False
        except Exception:
            return True
    def _create_minimal_decoys(self, *args,**kwargs):
        if not self._user_safe_mode:
            return
        decoy_names = ['license_validator', 'server_connector']
        for name in decoy_names:
            try:
                decoy_code = f'''
class {name.title().replace("_", "")}:
    def __init__(self):
        self.initialized = False

    def validate(self):
        return self.initialized

instance = {name.title().replace("_", "")}()
'''
                exec(decoy_code, globals())
            except Exception:
                continue
    @heavy_obfuscation
    def _setup_lightweight_checks(self, *args, **kwargs):
        if not self._performance_mode:
            return
        def environment_monitor():
            while self._protection_active:
                try:
                    if random.random() < 0.1:
                        if self._check_critical_timing():
                            self._trigger_emergency_shutdown("Critical timing anomaly")
                            return
                    if random.random() < 0.05:
                        execute_decoy_operations()
                        time.sleep(random.uniform(5.0, 15.0))
                except Exception:
                    time.sleep(10.0)
            thread = threading.Thread(target=environment_monitor, daemon=True)
            thread.start()
            self._protection_threads.append(thread)
    @heavy_obfuscation
    def _check_critical_timing(self, *args, **kwargs) -> bool:
        try:
            iterations = 1000
            start_time = time.perf_counter()
            result = sum(i * i for i in range(iterations))
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            if execution_time > 0.05:
                return True
        except Exception:
            pass
        return False
    def _setup_minimal_honeypots(self, *args,**kwargs):
        if not self._user_safe_mode:
            return
        fake_globals = {
            'LICENSE_KEY': 'EVAL-' + ''.join(random.choices('ABCDEF0123456789', k=16)),
            'SERVER_URL': 'https://example.com/api/',
            'API_SECRET': hashlib.md5(b'demo_secret').hexdigest()[:16]
        }
        for key, value in fake_globals.items():
            globals()[key] = value
    @heavy_obfuscation
    def _trigger_emergency_shutdown(self, reason: str, *args,**kwargs):
        try:
            if self._stealth_mode:
                normal_errors = [
                    "Произошла ошибка. Приложение будет закрыто.",
                    "Ошибка инициализации. Перезапустите приложение.",
                    "Не удалось загрузить компоненты."
                ]
                error_msg = random.choice(normal_errors)
                try:
                    ctypes.windll.user32.MessageBoxW(0, error_msg, "Ошибка", 0x30)
                except:
                    print(error_msg)
            time.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass
        os._exit(0)
    @heavy_obfuscation
    def initialize(self, stealth_mode: bool = True, *args, **kwargs):
        if self._protection_active:
            return
        self._stealth_mode = stealth_mode
        self._user_safe_mode = self._is_user_system()
        try:
            if self._user_safe_mode:
                self._create_minimal_decoys()
                self._setup_minimal_honeypots()
                self._setup_lightweight_checks()
            else:
                initialize_advanced_obfuscation()
                create_fake_activity()
                init_anti_debug()
                initialize_integrity_protection()
                initialize_file_protection()
                dynamic_check = create_dynamic_protection()
                def lightweight_monitor():
                    while self._protection_active:
                        try:
                            if not self._user_safe_mode:
                                if dynamic_check():
                                    self._trigger_emergency_shutdown("Dynamic check failed")
                                    return
                            time.sleep(random.uniform(10.0, 30.0))
                        except Exception:
                            time.sleep(15.0)
                dynamic_thread = threading.Thread(target=lightweight_monitor, daemon=True)
                dynamic_thread.start()
                self._protection_threads.append(dynamic_thread)
                self._protection_active = True
                self._initialization_complete = True
        except Exception:
            pass
    def is_active(self, *args, **kwargs) -> bool:
        return self._protection_active
    def shutdown(self, *args, **kwargs):
        self._protection_active = False
        try:
            if not self._user_safe_mode:
                stop_integrity_protection()
                stop_file_protection()
            for thread in self._protection_threads:
                if thread.is_alive():
                    thread.join(timeout=0.5)
        except Exception:
            pass
        self._protection_threads.clear()
        self._initialization_complete = False
_master_protection = MasterProtection()
@heavy_obfuscation
def initialize_master_protection(stealth_mode: bool = True):
    _master_protection.initialize(stealth_mode)
def is_protection_active() -> bool:
    return _master_protection.is_active()
def shutdown_protection():
    _master_protection.shutdown()
def critical_function(func):
    @protected
    @heavy_obfuscation
    def wrapper(*args, **kwargs):
        if _master_protection._user_safe_mode:
            return func(*args, **kwargs)
        if random.random() < 0.01:
            if not _master_protection.is_active():
                return None
        return func(*args, **kwargs)
    return wrapper
