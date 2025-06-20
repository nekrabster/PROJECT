import base64
import zlib
import marshal
import random
import string
import hashlib
import time
import sys
from typing import Any, Callable, Dict, List
WINDOWS_AVAILABLE = False
try:
    import winreg
    from ctypes import wintypes, windll
    WINDOWS_AVAILABLE = True
except ImportError:
    pass
IS_FROZEN = getattr(sys, 'frozen', False)
class CodeObfuscator:
    def __init__(self):
        self._xor_key = self._generate_key()
        self._string_cache = {}
        self._function_cache = {}
    def _generate_key(self, *args,**kwargs) -> bytes:
        timestamp = str(int(time.time()))[:-2]
        return hashlib.md5(timestamp.encode()).digest()
    def obfuscate_string(self, text: str, *args,**kwargs) -> str:
        if text in self._string_cache:
            return self._string_cache[text]
        encrypted_bytes = bytearray()
        key_bytes = self._xor_key
        for i, byte in enumerate(text.encode('utf-8')):
            encrypted_bytes.append(byte ^ key_bytes[i % len(key_bytes)])
        encoded = base64.b64encode(encrypted_bytes).decode()
        garbage = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(5, 15)))
        result = f"{garbage[:5]}{encoded}{garbage[5:]}"
        self._string_cache[text] = result
        return result
    def deobfuscate_string(self, obfuscated: str, *args,**kwargs) -> str:
        try:
            clean = obfuscated[5:-10] if len(obfuscated) > 15 else obfuscated[5:]
            encrypted_bytes = base64.b64decode(clean.encode())
            decrypted_bytes = bytearray()
            key_bytes = self._xor_key
            for i, byte in enumerate(encrypted_bytes):
                decrypted_bytes.append(byte ^ key_bytes[i % len(key_bytes)])
            return decrypted_bytes.decode('utf-8')
        except Exception:
            return obfuscated
    def pack_function(self, func: Callable, *args,**kwargs) -> str:
        try:
            code_object = func.__code__
            marshaled = marshal.dumps(code_object)
            compressed = zlib.compress(marshaled, level=9)
            encrypted = bytearray()
            key_bytes = self._xor_key
            for i, byte in enumerate(compressed):
                encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
            encoded = base64.b64encode(encrypted).decode()
            fake_metadata = {
                'version': random.randint(100, 999),
                'checksum': hashlib.md5(b'fake').hexdigest(),
                'timestamp': int(time.time()) + random.randint(-1000, 1000)
            }
            return f"META:{fake_metadata}:::{encoded}"
        except Exception as e:
            raise Exception(f"Failed to pack function: {e}")
    def unpack_function(self, packed_data: str, func_name: str = "dynamic_func", *args,**kwargs) -> Callable:
        try:
            if ":::" in packed_data:
                encoded = packed_data.split(":::")[1]
            else:
                encoded = packed_data
            encrypted = base64.b64decode(encoded.encode())
            decrypted = bytearray()
            key_bytes = self._xor_key
            for i, byte in enumerate(encrypted):
                decrypted.append(byte ^ key_bytes[i % len(key_bytes)])
            marshaled = zlib.decompress(bytes(decrypted))
            code_object = marshal.loads(marshaled)
            func = type(lambda: None)(code_object, globals(), func_name)
            return func
        except Exception as e:
            raise Exception(f"Failed to unpack function: {e}")
    def create_polymorphic_check(self, check_name: str, *args,**kwargs) -> str:
        if check_name == 'vm_check':
            return "def check(): return False"
        checks_variants = {
            'debugger_check': []
        }
        if WINDOWS_AVAILABLE and not IS_FROZEN:
            checks_variants['debugger_check'].extend([
                '''
def check():
    import ctypes
    return ctypes.windll.kernel32.IsDebuggerPresent() != 0
                ''',
                '''
def check():
    import ctypes
    from ctypes import wintypes
    debug_flag = wintypes.BOOL()
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.kernel32.CheckRemoteDebuggerPresent(handle, ctypes.byref(debug_flag))
    return debug_flag.value != 0
                '''
            ])

        checks_variants['debugger_check'].append(
            '''
def check():
    import time
    start = time.perf_counter()
    sum([i for i in range(1000)])
    end = time.perf_counter()
    return (end - start) > 0.005
            '''
        )

        checks_variants['debugger_check'].append(
            '''
def check():
    try:
        import psutil
        debug_processes = ['lldb', 'gdb', 'pdb', 'debugpy', 'ollydbg', 'x64dbg', 'windbg', 'ida']
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() in debug_processes:
                return True
    except ImportError:
        pass
    except Exception:
        pass
    return False
            '''
        )


        if WINDOWS_AVAILABLE and not IS_FROZEN:
            checks_variants['vm_check'].extend([
                '''
def check():
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\VMware, Inc.\\VMware Tools")
        return True
    except FileNotFoundError:
        pass
    try:
        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Oracle\\VirtualBox Guest Additions")
        return True
    except FileNotFoundError:
        pass
    return False
                '''
            ])

        checks_variants['vm_check'].extend([
            '''
def check():
    try:
        import psutil
        vm_procs = ['vmware.exe', 'vboxservice.exe', 'qemu-ga.exe', 'vmtoolsd.exe']
        running = [p.name().lower() for p in psutil.process_iter(['name'])]
        return any(vm in running for vm in vm_procs)
    except ImportError:
        pass
    except Exception:
        pass
    return False
            ''',
            '''
def check():
    import uuid
    mac = uuid.getnode()

    vm_mac_prefixes_decimal = [
        218600089,
        802097,
        524327,
        1385,

    ]

    mac_prefix = mac >> 24


    if mac.bit_length() >= 48:
        current_mac_prefix_3_bytes = (mac >> 24) & 0xFFFFFF



        if current_mac_prefix_3_bytes in [0x000569, 0x000C29, 0x001C14, 0x005056, 0x080027]:
             return True
    return False
            '''
        ])

        if check_name in checks_variants and checks_variants[check_name]:
            selected_code = random.choice(checks_variants[check_name])
            junk_vars = []
            for _ in range(random.randint(3, 7)):
                var_name = ''.join(random.choices(string.ascii_lowercase, k=8))
                var_value = random.randint(1000, 9999)
                junk_vars.append(f"    {var_name} = {var_value}")
            junk_operations = []
            for _ in range(random.randint(2, 5)):
                op = random.choice(['+', '-', '*', '%'])
                val1 = random.randint(1, 100)
                val2 = random.randint(1, 100)
                result_var = ''.join(random.choices(string.ascii_lowercase, k=6))
                junk_operations.append(f"    {result_var} = {val1} {op} {val2}")
            polymorphic_code = selected_code + "\n" + "\n".join(junk_vars) + "\n" + "\n".join(junk_operations)
            return polymorphic_code
        return "def check(): return False"
class DynamicExecutor:
    """Класс для динамического выполнения кода"""
    def __init__(self):
        self.obfuscator = CodeObfuscator()
        self._execution_context = {}
    def create_polymorphic_check(self, check_name: str, *args,**kwargs) -> str:
        """Создание полиморфной проверки"""
        checks_variants = {
            'debugger_check': [
                '''
def check():
    import ctypes
    return ctypes.windll.kernel32.IsDebuggerPresent() != 0
                ''',
                '''
def check():
    import ctypes
    from ctypes import wintypes
    debug_flag = wintypes.BOOL()
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.kernel32.CheckRemoteDebuggerPresent(handle, ctypes.byref(debug_flag))
    return debug_flag.value != 0
                ''',
                '''
def check():
    import time
    start = time.perf_counter()
    sum([i for i in range(1000)])
    end = time.perf_counter()
    return (end - start) > 0.01
                '''
            ],
            'vm_check': [
                '''
def check():
    import psutil
    vm_procs = ['vmware.exe', 'vboxservice.exe', 'qemu-ga.exe']
    running = [p.name().lower() for p in psutil.process_iter(['name'])]
    return any(vm in running for vm in vm_procs)
                ''',
                '''
def check():
    import uuid
    mac = uuid.getnode()
    vm_prefixes = [0x000569, 0x000C29, 0x080027]
    mac_prefix = (mac >> 24) & 0xFFFFFF
    return mac_prefix in vm_prefixes
                ''',
                '''
def check():
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\VMware, Inc.\\VMware Tools")
        return True
    except FileNotFoundError:
        return False
                '''
            ]
        }
        if check_name in checks_variants:
            selected_code = random.choice(checks_variants[check_name])
            junk_vars = []
            for _ in range(random.randint(3, 7)):
                var_name = ''.join(random.choices(string.ascii_lowercase, k=8))
                var_value = random.randint(1000, 9999)
                junk_vars.append(f"    {var_name} = {var_value}")
            junk_operations = []
            for _ in range(random.randint(2, 5)):
                op = random.choice(['+', '-', '*', '%'])
                val1 = random.randint(1, 100)
                val2 = random.randint(1, 100)
                result_var = ''.join(random.choices(string.ascii_lowercase, k=6))
                junk_operations.append(f"    {result_var} = {val1} {op} {val2}")
            polymorphic_code = selected_code + "\n" + "\n".join(junk_vars) + "\n" + "\n".join(junk_operations)
            return polymorphic_code
        return "def check(): return False"
    def execute_dynamic_check(self, check_code: str) -> bool:
        """Динамическое выполнение проверки"""
        try:
            local_context = {}
            exec(check_code, globals(), local_context)
            if 'check' in local_context:
                result = local_context['check']()
                return bool(result)
        except Exception:
            pass
        return False
    def create_decoy_functions(self, count: int = 10, *args,**kwargs) -> List[str]:
        """Создание ложных функций для запутывания"""
        decoy_functions = []
        for i in range(count):
            func_name = ''.join(random.choices(string.ascii_lowercase, k=random.randint(8, 15)))
            func_type = random.choice(['math', 'string', 'crypto', 'network'])
            if func_type == 'math':
                code = f'''
def {func_name}():
    import math
    x = {random.randint(1, 100)}
    y = {random.randint(1, 100)}
    result = math.sqrt(x * y)
    return int(result) % 256
                '''
            elif func_type == 'string':
                code = f'''
def {func_name}():
    import hashlib
    data = "{random.randint(10000, 99999)}"
    return hashlib.md5(data.encode()).hexdigest()[:8]
                '''
            elif func_type == 'crypto':
                code = f'''
def {func_name}():
    import base64
    data = b"{random.randint(100000, 999999)}"
    encoded = base64.b64encode(data)
    return len(encoded)
                '''
            else:
                code = f'''
def {func_name}():
    import socket
    try:
        s = socket.socket()
        s.settimeout(0.1)
        result = s.connect_ex(("127.0.0.1", {random.randint(8000, 9000)}))
        s.close()
        return result != 0
    except:
        return True
                '''
            decoy_functions.append(code)
        return decoy_functions
_obfuscator = CodeObfuscator()
_executor = DynamicExecutor()
OBFUSCATED_STRINGS = {
    'debugger_detected': _obfuscator.obfuscate_string("Обнаружен отладчик"),
    'vm_detected': _obfuscator.obfuscate_string("Обнаружена виртуальная машина"),
    'analysis_detected': _obfuscator.obfuscate_string("Обнаружены средства анализа"),
    'protection_triggered': _obfuscator.obfuscate_string("Срабатывание защиты"),
}
def get_string(key: str) -> str:
    """Получение деобфускированной строки"""
    if key in OBFUSCATED_STRINGS:
        return _obfuscator.deobfuscate_string(OBFUSCATED_STRINGS[key])
    return key
def create_dynamic_protection() -> Callable:
    """Создание динамической защиты"""
    check_code = _executor.create_polymorphic_check('debugger_check')
    def dynamic_check():
        return _executor.execute_dynamic_check(check_code)
    return dynamic_check
def execute_decoy_operations():
    """Выполнение ложных операций"""
    decoy_funcs = _executor.create_decoy_functions(5)
    for func_code in decoy_funcs:
        try:
            exec(func_code)
        except Exception:
            pass
