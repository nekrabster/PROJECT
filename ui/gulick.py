import ctypes
import os
import sys
import time
import threading
import random
import hashlib
import psutil
try:
    from ctypes import wintypes, windll
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False
    winreg = None
    wintypes = None
    windll = None
import sys
IS_FROZEN = getattr(sys, 'frozen', False)
from functools import wraps
class AntiDebugProtection:
    def __init__(self):
        self._protection_active = True
        self._check_interval = random.uniform(2.0, 5.0)
        self._dummy_functions = []
        self._create_dummy_functions()
    def _create_dummy_functions(self, *args,**kwargs):
        def fake_decrypt_license():
            fake_key = b'x' * 32
            return hashlib.sha256(fake_key).hexdigest()
        def fake_validate_hwid():
            import uuid
            return str(uuid.uuid4())
        def fake_connect_server():
            return '127.0.0.1:8080'
        self._dummy_functions = [fake_decrypt_license, fake_validate_hwid, fake_connect_server]
    def check_debugger_present(self, *args,**kwargs):
        if not WINDOWS_AVAILABLE or IS_FROZEN:
            try:
                running_processes = [p.name().lower() for p in psutil.process_iter(['name'])]
                debug_processes = ['lldb', 'gdb', 'pdb', 'debugpy']
                for debug_proc in debug_processes:
                    if any((debug_proc in proc for proc in running_processes)):
                        print(f'[DEBUG] Найден отладочный процесс: {debug_proc}')
                        return True
            except Exception:
                pass
            return False
        try:
            if windll.kernel32.IsDebuggerPresent():
                self._trigger_protection()
                return True
            debug_flag = wintypes.BOOL()
            process_handle = windll.kernel32.GetCurrentProcess()
            windll.kernel32.CheckRemoteDebuggerPresent(process_handle, ctypes.byref(debug_flag))
            if debug_flag.value:
                self._trigger_protection()
                return True
            ntdll = windll.ntdll
            process_debug_port = 7
            debug_port = ctypes.c_void_p()
            status = ntdll.NtQueryInformationProcess(process_handle, process_debug_port, ctypes.byref(debug_port), ctypes.sizeof(debug_port), None)
            if status == 0 and debug_port.value != 0:
                self._trigger_protection()
                return True
        except Exception:
            pass
        return False
    def check_timing_attack(self, *args,**kwargs):
        try:
            start_time = time.perf_counter()
            result = 0
            for i in range(1000):
                result += i * 2
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            if execution_time > 0.1:
                self._trigger_protection()
                return True
        except Exception:
            pass
        return False
    def check_virtual_machine(self, *args,**kwargs):
        return False
    def check_analysis_tools(self, *args,**kwargs):
        try:
            analysis_processes = ['ollydbg.exe', 'x64dbg.exe', 'x32dbg.exe', 'windbg.exe', 'ida.exe', 'ida64.exe', 'idaq.exe', 'idaq64.exe', 'idaw.exe', 'ghidra.exe', 'radare2.exe', 'r2.exe', 'hiew.exe', 'procmon.exe', 'procmon64.exe', 'apimonitor.exe', 'wireshark.exe', 'fiddler.exe', 'charles.exe', 'pe-bear.exe', 'lordpe.exe', 'pestudio.exe', 'hollowshunter.exe', 'hasherezade.exe']
            running_processes = [p.name().lower() for p in psutil.process_iter(['name'])]
            for analysis_proc in analysis_processes:
                if analysis_proc.lower() in running_processes:
                    self._trigger_protection()
                    return True
        except Exception:
            pass
        return False
    def check_sandbox_environment(self, *args,**kwargs):
        try:
            process_count = len(list(psutil.process_iter()))
            if process_count < 15:
                self._trigger_protection()
                return True
            memory = psutil.virtual_memory()
            if memory.total < 1 * 1024 * 1024 * 1024:
                self._trigger_protection()
                return True
            boot_time = psutil.boot_time()
            current_time = time.time()
            uptime = current_time - boot_time
            if uptime < 60:
                self._trigger_protection()
                return True
            username = os.getenv('USERNAME', '').lower()
            sandbox_users = ['sandbox', 'malware', 'virus', 'sample', 'test']
            if username in sandbox_users:
                self._trigger_protection()
                return True
        except Exception:
            pass
        return False
    def _trigger_protection(self, *args,**kwargs):
        if not self._protection_active:
            return
        for func in self._dummy_functions:
            try:
                func()
            except:
                pass
        self._show_fake_error()
        os._exit(1)
    def _show_fake_error(self, *args,**kwargs):
        try:
            fake_errors = ['Ошибка подключения к серверу активации. Код: 0x80070005', 'Не удалось загрузить лицензионный ключ. Проверьте интернет соединение.', 'Истек срок действия лицензии. Обратитесь к администратору.', 'Обнаружена проблема с базой данных. Переустановите приложение.']
            error_msg = random.choice(fake_errors)
            if WINDOWS_AVAILABLE:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, error_msg, 'Ошибка', 16)
            else:
                print(f'[ERROR] {error_msg}')
        except:
            pass
    def start_protection_thread(self, *args,**kwargs):
        def protection_loop():
            while self._protection_active:
                try:
                    checks = [self.check_debugger_present, self.check_timing_attack, self.check_virtual_machine, self.check_analysis_tools, self.check_sandbox_environment]
                    random.shuffle(checks)
                    for check in checks[:2]:
                        if check():
                            return
                        time.sleep(random.uniform(0.2, 1.0))
                    time.sleep(self._check_interval)
                    self._check_interval = random.uniform(2.0, 5.0)
                except Exception:
                    time.sleep(2.0)
        thread = threading.Thread(target=protection_loop, daemon=True)
        thread.start()
    def disable_protection(self, *args,**kwargs):
        self._protection_active = False
_protection = AntiDebugProtection()
def protected(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if random.random() < 0.02:
            if _protection.check_debugger_present():
                return None
        return func(*args, **kwargs)
    return wrapper
def initialize_protection():
    _protection.start_protection_thread()
def disable_protection():
    _protection.disable_protection()
