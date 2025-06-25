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
class OptimizedCodeObfuscator:
    def __init__(self):
        self._xor_key = self._generate_key()
        self._string_cache = {}
        self._function_cache = {}
        self._user_safe_mode = self._detect_user_environment()
    def _detect_user_environment(self, *args,**kwargs) -> bool:
        try:
            import psutil
            process_count = len(list(psutil.process_iter()))
            memory = psutil.virtual_memory()
            return process_count > 40 and memory.total > 3 * 1024 * 1024 * 1024
        except Exception:
            return True
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
        if self._user_safe_mode:
            result = encoded
        else:
            garbage = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(3, 8)))
            result = f"{garbage[:3]}{encoded}{garbage[3:]}"
        self._string_cache[text] = result
        return result
    def deobfuscate_string(self, obfuscated: str, *args,**kwargs) -> str:
        try:
            if self._user_safe_mode:
                clean = obfuscated
            else:
                clean = obfuscated[3:-5] if len(obfuscated) > 8 else obfuscated[3:]
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
            compressed = zlib.compress(marshaled, level=6)
            encrypted = bytearray()
            key_bytes = self._xor_key
            for i, byte in enumerate(compressed):
                encrypted.append(byte ^ key_bytes[i % len(key_bytes)])
            encoded = base64.b64encode(encrypted).decode()
            if self._user_safe_mode:
                return encoded
            fake_metadata = {
                'version': random.randint(100, 999)
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
    def create_safe_check(self, check_name: str, *args,**kwargs) -> str:
        if self._user_safe_mode:
            return "def check(): return False"
        checks_variants = {
            'debugger_check': [
                '''
def check():
    import time
    start = time.perf_counter()
    sum([i for i in range(500)])
    end = time.perf_counter()
    return (end - start) > 0.01
                '''
            ]
        }
        if WINDOWS_AVAILABLE and not IS_FROZEN and not self._user_safe_mode:
            checks_variants['debugger_check'].append(
                '''
def check():
    import ctypes
    return ctypes.windll.kernel32.IsDebuggerPresent() != 0
                '''
            )
        if check_name in checks_variants and checks_variants[check_name]:
            selected_code = random.choice(checks_variants[check_name])
            if not self._user_safe_mode:
                junk_vars = []
                for _ in range(random.randint(1, 3)):
                    var_name = ''.join(random.choices(string.ascii_lowercase, k=6))
                    var_value = random.randint(100, 999)
                    junk_vars.append(f"    {var_name} = {var_value}")
                polymorphic_code = selected_code + "\n" + "\n".join(junk_vars)
                return polymorphic_code
            return selected_code
        return "def check(): return False"
class LightweightExecutor:
    """Класс для динамического выполнения кода"""
    def __init__(self):
        self.obfuscator = OptimizedCodeObfuscator()
        self._execution_context = {}
    def create_safe_check(self, check_name: str, *args,**kwargs) -> str:
        """Создание полиморфной проверки"""
        return self.obfuscator.create_safe_check(check_name)
    def execute_safe_check(self, check_code: str, *args,**kwargs) -> bool:
        """Динамическое выполнение проверки"""
        try:
            if self.obfuscator._user_safe_mode:
                return False
            exec(check_code, self._execution_context)
            check_func = self._execution_context.get('check')
            if check_func:
                return check_func()
        except Exception:
            pass
        return False
    def create_minimal_decoys(self, count: int = 3, *args,**kwargs) -> List[str]:
        """Создание ложных функций для запутывания"""
        if self.obfuscator._user_safe_mode:
            return []
        decoy_functions = []
        for i in range(count):
            func_name = f"decoy_function_{i}"
            decoy_code = f'''
def {func_name}():
    import time
    result = {random.randint(100, 999)}
    time.sleep(0.01)
    return result
            '''
            decoy_functions.append(decoy_code)
        return decoy_functions
_obfuscator = OptimizedCodeObfuscator()
_executor = LightweightExecutor()
def get_string(key: str) -> str:
    """Получение деобфускированной строки"""
    strings = {
        'error_msg': "Ошибка приложения"
    }
    if key in strings:
        return _obfuscator.obfuscate_string(strings[key])
    return _obfuscator.obfuscate_string(key)
def create_dynamic_protection() -> Callable:
    """Создание динамической защиты"""
    check_code = _executor.create_safe_check('debugger_check')
    def dynamic_check():
        return _executor.execute_safe_check(check_code)
    return dynamic_check
def execute_decoy_operations():
    """Выполнение ложных операций"""
    if _obfuscator._user_safe_mode:
        return
    decoys = _executor.create_minimal_decoys(2)
    for decoy in decoys:
        try:
            exec(decoy)
        except Exception:
            pass
