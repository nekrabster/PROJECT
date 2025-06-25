import ctypes
import hashlib
import os
import sys
import time
import threading
import random
from typing import Dict, List, Optional, Tuple
try:
    from ctypes import wintypes, windll
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    wintypes = None
    windll = None
import sys
IS_FROZEN = getattr(sys, 'frozen', False)
class LightweightIntegrityChecker:
    def __init__(self):
        self._module_hashes = {}
        self._api_hooks = {}
        self._original_addresses = {}
        self._integrity_thread = None
        self._running = True
        self._check_interval = random.uniform(15.0, 30.0)
        self._user_safe_mode = self._detect_user_environment()
    def _detect_user_environment(self, *args,**kwargs) -> bool:
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
    def calculate_file_hash(self, filepath: str, *args,**kwargs) -> str:
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:32]
        except Exception:
            return ""
    def get_module_info(self, module_name: str, *args,**kwargs) -> Optional[Tuple[int, int]]:
        if not WINDOWS_AVAILABLE or IS_FROZEN or self._user_safe_mode:
            return None
        try:
            module_handle = windll.kernel32.GetModuleHandleW(module_name)
            if not module_handle:
                return None
            module_info = ctypes.create_string_buffer(24)
            psapi = windll.psapi
            if psapi.GetModuleInformation(
                windll.kernel32.GetCurrentProcess(),
                module_handle,
                module_info,
                24
            ):
                base_address = ctypes.c_void_p.from_buffer(module_info, 0).value
                size = ctypes.c_ulong.from_buffer(module_info, 8).value
                return (base_address, size)
        except Exception:
            pass
        return None
    def calculate_memory_hash(self, base_address: int, size: int, *args,**kwargs) -> str:
        if self._user_safe_mode:
            return ""
        try:
            buffer = (ctypes.c_byte * min(size, 1024))()
            bytes_read = ctypes.c_size_t()
            success = windll.kernel32.ReadProcessMemory(
                windll.kernel32.GetCurrentProcess(),
                ctypes.c_void_p(base_address),
                ctypes.byref(buffer),
                min(size, 1024),
                ctypes.byref(bytes_read)
            )
            if success and bytes_read.value > 0:
                data = bytes(buffer[:bytes_read.value])
                return hashlib.sha256(data).hexdigest()[:32]
        except Exception:
            pass
        return ""
    def store_module_integrity(self, module_name: str, *args,**kwargs):
        if self._user_safe_mode:
            return
        module_info = self.get_module_info(module_name)
        if module_info:
            base_address, size = module_info
            memory_hash = self.calculate_memory_hash(base_address, size)
            if memory_hash:
                self._module_hashes[module_name] = {
                    'hash': memory_hash,
                    'base_address': base_address,
                    'size': size,
                    'timestamp': time.time()
                }
    def check_module_integrity(self, module_name: str, *args,**kwargs) -> bool:
        if module_name not in self._module_hashes or self._user_safe_mode:
            return True
        stored_info = self._module_hashes[module_name]
        current_hash = self.calculate_memory_hash(
            stored_info['base_address'],
            stored_info['size']
        )
        return current_hash == stored_info['hash']
    def get_api_address(self, module_name: str, function_name: str, *args,**kwargs) -> Optional[int]:
        if self._user_safe_mode:
            return None
        try:
            module_handle = windll.kernel32.GetModuleHandleW(module_name)
            if module_handle:
                address = windll.kernel32.GetProcAddress(
                    module_handle,
                    function_name.encode('ascii')
                )
                return address
        except Exception:
            pass
        return None
    def store_api_addresses(self, *args,**kwargs):
        if self._user_safe_mode:
            return
        critical_apis = [
            ('kernel32.dll', 'IsDebuggerPresent'),
            ('kernel32.dll', 'GetTickCount'),
        ]
        for module, function in critical_apis:
            address = self.get_api_address(module, function)
            if address:
                try:
                    buffer = (ctypes.c_byte * 8)()
                    bytes_read = ctypes.c_size_t()
                    success = windll.kernel32.ReadProcessMemory(
                        windll.kernel32.GetCurrentProcess(),
                        ctypes.c_void_p(address),
                        ctypes.byref(buffer),
                        8,
                        ctypes.byref(bytes_read)
                    )
                    if success:
                        original_bytes = bytes(buffer[:bytes_read.value])
                        key = f"{module}:{function}"
                        self._api_hooks[key] = {
                            'address': address,
                            'original_bytes': original_bytes,
                            'hash': hashlib.md5(original_bytes).hexdigest()
                        }
                except Exception:
                    continue
    def check_api_hooks(self, *args,**kwargs) -> List[str]:
        if self._user_safe_mode:
            return []
        hooked_apis = []
        for key, info in self._api_hooks.items():
            try:
                buffer = (ctypes.c_byte * 8)()
                bytes_read = ctypes.c_size_t()
                success = windll.kernel32.ReadProcessMemory(
                    windll.kernel32.GetCurrentProcess(),
                    ctypes.c_void_p(info['address']),
                    ctypes.byref(buffer),
                    8,
                    ctypes.byref(bytes_read)
                )
                if success:
                    current_bytes = bytes(buffer[:bytes_read.value])
                    current_hash = hashlib.md5(current_bytes).hexdigest()
                    if current_hash != info['hash']:
                        hooked_apis.append(key)
            except Exception:
                continue
        return hooked_apis
    def check_self_modification(self, *args,**kwargs) -> bool:
        if self._user_safe_mode:
            return False
        try:
            main_module = sys.executable
            if os.path.exists(main_module):
                current_hash = self.calculate_file_hash(main_module)
                if hasattr(self, '_main_module_hash'):
                    return current_hash != self._main_module_hash
                else:
                    self._main_module_hash = current_hash
        except Exception:
            pass
        return False
    def initialize_integrity_checking(self, *args,**kwargs):
        if self._user_safe_mode:
            return
        critical_modules = ['kernel32.dll', 'ntdll.dll']
        for module in critical_modules:
            self.store_module_integrity(module)
        self.store_api_addresses()
        try:
            main_module = sys.executable
            if os.path.exists(main_module):
                self._main_module_hash = self.calculate_file_hash(main_module)
        except Exception:
            pass
    def start_integrity_monitoring(self, *args,**kwargs):
        if self._user_safe_mode:
            return
        def monitoring_loop():
            while self._running:
                try:
                    for module_name in list(self._module_hashes.keys())[:2]:
                        if not self.check_module_integrity(module_name):
                            self._trigger_integrity_violation(f"Module {module_name} modified")
                            return
                    if random.random() < 0.3:
                        hooked_apis = self.check_api_hooks()
                        if hooked_apis:
                            self._trigger_integrity_violation(f"API hooks detected: {hooked_apis}")
                            return
                    if random.random() < 0.1:
                        if self.check_self_modification():
                            self._trigger_integrity_violation("Self-modification detected")
                            return
                    time.sleep(self._check_interval)
                    self._check_interval = random.uniform(15.0, 30.0)
                except Exception:
                    time.sleep(5.0)
        self._integrity_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._integrity_thread.start()
    def _trigger_integrity_violation(self, reason: str, *args,**kwargs):
        if self._user_safe_mode:
            return
        try:
            error_messages = [
                "Критическая ошибка системы. Перезапустите приложение.",
                "Ошибка целостности данных. Переустановите программу.",
                "Системная ошибка. Обратитесь к администратору."
            ]
            error_msg = random.choice(error_messages)
            try:
                ctypes.windll.user32.MessageBoxW(0, error_msg, "Критическая ошибка", 0x10)
            except:
                print(f"[ERROR] {error_msg}")
            time.sleep(random.uniform(0.1, 0.3))
        except Exception:
            pass
        os._exit(1)
    def stop_monitoring(self, *args,**kwargs):
        self._running = False
        if self._integrity_thread:
            self._integrity_thread.join(timeout=1.0)
class SimpleSelfModifyingCode:
    def __init__(self):
        self._obfuscated_functions = {}
    def create_encrypted_function(self, func_code: str, func_name: str, *args,**kwargs) -> str:
        try:
            import base64
            encoded = base64.b64encode(func_code.encode('utf-8')).decode('ascii')
            key = random.randint(1, 255)
            encrypted = ''
            for char in encoded:
                encrypted += chr(ord(char) ^ key)
            wrapper_code = f'''
def {func_name}():
import base64
encrypted="{encrypted}"
key={key}
decoded=""
for char in encrypted:
decoded+=chr(ord(char)^key)
original=base64.b64decode(decoded.encode()).decode('utf-8')
exec(original)
'''
            return wrapper_code
        except Exception:
            return f"def {func_name}(): pass"
_integrity_checker = LightweightIntegrityChecker()
_self_modifying = SimpleSelfModifyingCode()
def initialize_integrity_protection(*args,**kwargs):
    try:
        _integrity_checker.initialize_integrity_checking()
        _integrity_checker.start_integrity_monitoring()
    except Exception:
        pass
def stop_integrity_protection():
    _integrity_checker.stop_monitoring()
def create_self_modifying_function(code: str, name: str) -> str:
    return _self_modifying.create_encrypted_function(code, name)
