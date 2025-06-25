import os
import sys
import hashlib
import time
import random
import ctypes
from typing import Dict, List
import threading
from ui.decorators import critical_function, heavy_obfuscation
class OptimizedFileProtection:
    def __init__(self):
        self._file_hashes = {}
        self._memory_hashes = {}
        self._running = True
        self._check_interval = random.uniform(30.0, 60.0)
        self._protection_thread = None
        self._is_frozen = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')
        self._is_pyd = self._check_pyd_environment()
        self._is_admin = self._check_admin_rights()
        self._is_virtual = self._check_virtual_environment()
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
    def _check_virtual_environment(self, *args, **kwargs) -> bool:
        try:
            return (
                'VIRTUAL_ENV' in os.environ or
                'VBOX' in os.environ.get('SYSTEMROOT', '').upper() or
                'docker' in os.environ.get('PATH', '').lower() or
                'lxc' in os.environ.get('PATH', '').lower() or
                'vmware' in os.environ.get('PATH', '').lower() or
                'qemu' in os.environ.get('PATH', '').lower() or
                os.path.exists('/.dockerenv') or
                os.path.exists('/proc/vz') or
                os.path.exists('/proc/sys/kernel/osrelease')
            )
        except:
            return False
    def _check_admin_rights(self, *args, **kwargs) -> bool:
        try:
            if self._is_virtual or self._user_safe_mode:
                return True
            if os.name == 'nt':
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            return os.geteuid() == 0
        except Exception:
            return True
    def _check_pyd_environment(self, *args, **kwargs) -> bool:
        try:
            if getattr(sys, 'frozen', False):
                return True
            if any(m.__file__.endswith('.pyd') for m in sys.modules.values() if hasattr(m, '__file__')):
                return True
            if hasattr(sys, '_MEIPASS'):
                return True
            return False
        except:
            return True
    @critical_function
    def calculate_file_hash(self, filepath: str, *args, **kwargs) -> str:
        try:
            if not os.path.exists(filepath):
                return ""
            file_stat = os.stat(filepath)
            hasher = hashlib.sha256()
            hasher.update(str(file_stat.st_size).encode())
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()[:32]
        except Exception:
            return ""
    @critical_function
    def calculate_memory_hash(self, base_address: int, size: int, *args, **kwargs) -> str:
        if not self._is_pyd or self._is_virtual or self._user_safe_mode:
            return ""
        try:
            buffer = (ctypes.c_byte * min(size, 512))()
            bytes_read = ctypes.c_size_t()
            success = ctypes.windll.kernel32.ReadProcessMemory(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.c_void_p(base_address),
                ctypes.byref(buffer),
                min(size, 512),
                ctypes.byref(bytes_read)
            )
            if success and bytes_read.value > 0:
                data = bytes(buffer[:bytes_read.value])
                return hashlib.sha256(data).hexdigest()[:32]
        except Exception:
            pass
        return ""
    @critical_function
    def store_file_integrity(self, filepath: str, *args, **kwargs):
        try:
            if not os.path.exists(filepath) or self._user_safe_mode:
                return
            file_hash = self.calculate_file_hash(filepath)
            if file_hash:
                self._file_hashes[filepath] = {
                    'hash': file_hash,
                    'size': os.path.getsize(filepath),
                    'mtime': os.path.getmtime(filepath),
                    'timestamp': time.time()
                }
        except Exception:
            pass
    @critical_function
    def check_file_integrity(self, filepath: str, *args, **kwargs) -> bool:
        try:
            if filepath not in self._file_hashes:
                return True
            if self._is_virtual or self._is_pyd or self._user_safe_mode:
                return True
            stored_info = self._file_hashes[filepath]
            current_hash = self.calculate_file_hash(filepath)
            if not current_hash or current_hash == stored_info['hash']:
                return True
            return False
        except:
            return True
    @critical_function
    def detect_patching(self, *args, **kwargs) -> bool:
        if not self._is_pyd or self._is_virtual or not self._is_admin or self._user_safe_mode:
            return False
        try:
            critical_modules = [
                'ui.filya',
                'ui.session'
            ]
            for module_name, module in sys.modules.items():
                if not any(module_name.startswith(crit) for crit in critical_modules):
                    continue
                if hasattr(module, '__file__') and module.__file__ and module.__file__.endswith('.pyd'):
                    try:
                        with open(module.__file__, 'rb') as f:
                            content = f.read(min(1024, os.path.getsize(module.__file__)))
                            if b'\xCC' * 2 in content or b'\x90' * 4 in content:
                                return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False
    @heavy_obfuscation
    def start_protection(self, *args, **kwargs):
        if self._user_safe_mode:
            return
        def protection_loop():
            while self._running:
                try:
                    if self._is_virtual or self._is_pyd or self._user_safe_mode:
                        time.sleep(random.uniform(30.0, 60.0))
                        continue
                    for filepath in list(self._file_hashes.keys())[:3]:
                        if not self.check_file_integrity(filepath):
                            self._trigger_violation("File integrity violation")
                            return
                    time.sleep(random.uniform(30.0, 60.0))
                except:
                    time.sleep(10.0)
            self._protection_thread = threading.Thread(target=protection_loop, daemon=True)
            self._protection_thread.start()
    def _trigger_violation(self, reason: str, *args, **kwargs):
        try:
            if self._is_virtual or self._is_pyd or self._user_safe_mode:
                return
            error_code = {
                "File integrity violation": "0xE0000001",
                "Patching detected": "0xE0000002",
                "Memory violation": "0xE0000003"
            }.get(reason, "0xE0000000")
            error_msg = random.choice([
                f"Критическая ошибка системы. Код: {error_code}",
                f"Ошибка целостности. Код: {error_code}",
                f"Системная ошибка. Код: {error_code}"
            ])
            if hasattr(ctypes, 'windll'):
                ctypes.windll.user32.MessageBoxW(0, error_msg, "Критическая ошибка", 0x10)
            os._exit(1)
        except:
            os._exit(1)
    def stop_protection(self, *args, **kwargs):
        self._running = False
        if self._protection_thread:
            self._protection_thread.join(timeout=1.0)
_file_protection = OptimizedFileProtection()
def is_frozen():
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')
def initialize_file_protection(*args, **kwargs):
    try:
        if _file_protection._is_virtual or _file_protection._is_pyd or _file_protection._user_safe_mode:
            return
        for module in list(sys.modules.values())[:10]:
            if hasattr(module, '__file__') and module.__file__:
                try:
                    module_file = os.path.abspath(module.__file__)
                    if module_file.endswith(('.py', '.pyd', '.dll')):
                        _file_protection.store_file_integrity(module_file)
                except:
                    continue
        _file_protection.start_protection()
    except:
        pass
def stop_file_protection(*args, **kwargs):
    _file_protection.stop_protection() 
