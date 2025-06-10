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
class IntegrityChecker:
    def __init__(self):
        self._module_hashes = {}
        self._api_hooks = {}
        self._original_addresses = {}
        self._integrity_thread = None
        self._running = True
        self._check_interval = random.uniform(1.0, 3.0)
    def calculate_file_hash(self, filepath: str, *args,**kwargs) -> str:
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""
    def get_module_info(self, module_name: str, *args,**kwargs) -> Optional[Tuple[int, int]]:
        if not WINDOWS_AVAILABLE or IS_FROZEN:
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
        try:
            buffer = (ctypes.c_byte * size)()
            bytes_read = ctypes.c_size_t()
            success = windll.kernel32.ReadProcessMemory(
                windll.kernel32.GetCurrentProcess(),
                ctypes.c_void_p(base_address),
                ctypes.byref(buffer),
                size,
                ctypes.byref(bytes_read)
            )
            if success and bytes_read.value > 0:
                data = bytes(buffer[:bytes_read.value])
                return hashlib.sha256(data).hexdigest()
        except Exception:
            pass
        return ""
    def store_module_integrity(self, module_name: str, *args,**kwargs):
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
        if module_name not in self._module_hashes:
            return True
        stored_info = self._module_hashes[module_name]
        current_hash = self.calculate_memory_hash(
            stored_info['base_address'],
            stored_info['size']
        )
        return current_hash == stored_info['hash']
    def get_api_address(self, module_name: str, function_name: str, *args,**kwargs) -> Optional[int]:
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
        critical_apis = [
            ('kernel32.dll', 'IsDebuggerPresent'),
            ('kernel32.dll', 'CheckRemoteDebuggerPresent'),
            ('kernel32.dll', 'GetTickCount'),
            ('kernel32.dll', 'QueryPerformanceCounter'),
            ('ntdll.dll', 'NtQueryInformationProcess'),
            ('ntdll.dll', 'NtSetInformationThread'),
            ('kernel32.dll', 'CreateFileW'),
            ('kernel32.dll', 'ReadFile'),
            ('kernel32.dll', 'WriteFile'),
        ]
        for module, function in critical_apis:
            address = self.get_api_address(module, function)
            if address:
                buffer = (ctypes.c_byte * 16)()
                bytes_read = ctypes.c_size_t()
                success = windll.kernel32.ReadProcessMemory(
                    windll.kernel32.GetCurrentProcess(),
                    ctypes.c_void_p(address),
                    ctypes.byref(buffer),
                    16,
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
    def check_api_hooks(self, *args,**kwargs) -> List[str]:
        hooked_apis = []
        for key, info in self._api_hooks.items():
            try:
                buffer = (ctypes.c_byte * 16)()
                bytes_read = ctypes.c_size_t()
                success = windll.kernel32.ReadProcessMemory(
                    windll.kernel32.GetCurrentProcess(),
                    ctypes.c_void_p(info['address']),
                    ctypes.byref(buffer),
                    16,
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
    def detect_code_caves(self, *args,**kwargs) -> bool:
        try:
            process_handle = windll.kernel32.GetCurrentProcess()
            address = 0x10000
            while address < 0x7FFFFFFF:
                mem_info = wintypes.MEMORY_BASIC_INFORMATION()
                size = windll.kernel32.VirtualQuery(
                    ctypes.c_void_p(address),
                    ctypes.byref(mem_info),
                    ctypes.sizeof(mem_info)
                )
                if size == 0:
                    break
                if (mem_info.State == 0x1000 and
                    mem_info.Type == 0x1000000 and
                    mem_info.Protect & 0x20):
                    buffer_size = min(1024, mem_info.RegionSize)
                    buffer = (ctypes.c_byte * buffer_size)()
                    bytes_read = ctypes.c_size_t()
                    success = windll.kernel32.ReadProcessMemory(
                        process_handle,
                        ctypes.c_void_p(mem_info.BaseAddress),
                        ctypes.byref(buffer),
                        buffer_size,
                        ctypes.byref(bytes_read)
                    )
                    if success and bytes_read.value > 100:
                        data = bytes(buffer[:bytes_read.value])
                        zero_count = data.count(0)
                        if zero_count > len(data) * 0.9:
                            return True
                        hook_patterns = [
                            b'\xE9',
                            b'\xEB',
                            b'\xFF\x25',
                            b'\x68',
                            b'\xC3',
                        ]
                        for pattern in hook_patterns:
                            if data.count(pattern) > len(data) // 50:
                                return True
                address = mem_info.BaseAddress + mem_info.RegionSize
        except Exception:
            pass
        return False
    def check_self_modification(self, *args,**kwargs) -> bool:
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
        critical_modules = ['kernel32.dll', 'ntdll.dll', 'user32.dll']
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
        def monitoring_loop():
            while self._running:
                try:
                    for module_name in self._module_hashes.keys():
                        if not self.check_module_integrity(module_name):
                            self._trigger_integrity_violation(f"Module {module_name} modified")
                            return
                    hooked_apis = self.check_api_hooks()
                    if hooked_apis:
                        self._trigger_integrity_violation(f"API hooks detected: {hooked_apis}")
                        return
                    if random.random() < 0.3:
                        if self.detect_code_caves():
                            self._trigger_integrity_violation("Code caves detected")
                            return
                    if random.random() < 0.2:
                        if self.check_self_modification():
                            self._trigger_integrity_violation("Self-modification detected")
                            return
                    time.sleep(self._check_interval)
                    self._check_interval = random.uniform(1.0, 3.0)
                except Exception:
                    time.sleep(2.0)
        self._integrity_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self._integrity_thread.start()
    def _trigger_integrity_violation(self, reason: str, *args,**kwargs):
        try:
            for _ in range(random.randint(5, 10)):
                fake_data = os.urandom(1024)
                fake_hash = hashlib.sha256(fake_data).hexdigest()
            fake_errors = [
                "Критическая ошибка системы безопасности. Код: 0xC0000005",
                "Обнаружено нарушение целостности данных. Приложение будет закрыто.",
                "Ошибка аутентификации лицензии. Код: 0x80070002",
                "Системная ошибка. Обратитесь к администратору."
            ]
            error_msg = random.choice(fake_errors)
            if WINDOWS_AVAILABLE:
                ctypes.windll.user32.MessageBoxW(0, error_msg, "Критическая ошибка", 0x10)
            else:
                print(f"[CRITICAL ERROR] Integrity violation: {reason} - {error_msg}")
        except Exception:
            pass
        os._exit(1)
    def stop_monitoring(self, *args,**kwargs):
        self._running = False
class SelfModifyingCode:
    def __init__(self):
        self._code_blocks = {}
        self._modification_key = os.urandom(16)
    def create_encrypted_function(self, func_code: str, func_name: str, *args,**kwargs) -> str:
        try:
            compiled = compile(func_code, '<string>', 'exec')
            import marshal
            marshaled = marshal.dumps(compiled)
            encrypted = bytearray()
            key = self._modification_key
            for i, byte in enumerate(marshaled):
                encrypted.append(byte ^ key[i % len(key)])
            import base64
            encoded = base64.b64encode(encrypted).decode()
            loader_code = f'''
import base64
import marshal
import os

def {func_name}_loader():
    key = {list(self._modification_key)}
    encoded = "{encoded}"

    encrypted = base64.b64decode(encoded.encode())
    decrypted = bytearray()

    for i, byte in enumerate(encrypted):
        decrypted.append(byte ^ key[i % len(key)])

    marshaled = bytes(decrypted)
    compiled = marshal.loads(marshaled)

    exec(compiled, globals())
    return locals().get('{func_name}')

{func_name} = {func_name}_loader()
'''
            return loader_code
        except Exception as e:
            return f"def {func_name}(): pass  # Error: {e}"
_integrity_checker = IntegrityChecker()
_self_modifying = SelfModifyingCode()
def initialize_integrity_protection(*args,**kwargs):
    _integrity_checker.initialize_integrity_checking()
    _integrity_checker.start_integrity_monitoring()
def stop_integrity_protection():
    _integrity_checker.stop_monitoring()
def create_self_modifying_function(code: str, name: str) -> str:
    return _self_modifying.create_encrypted_function(code, name)
