"""
Модуль для интеграции системы защиты в существующие файлы приложения.

Этот файл содержит примеры и инструкции по добавлению защиты в ваши модули.
"""

from .kms import critical_function, initialize_master_protection, is_protection_active
from .adv import heavy_obfuscation




@critical_function
def example_critical_function():
    """Пример защищенной критической функции"""

    pass


@heavy_obfuscation
def example_obfuscated_function():
    """Пример сильно обфускированной функции"""

    pass


@critical_function
@heavy_obfuscation
def example_maximum_protection():
    """Пример функции с максимальной защитой"""

    pass



def integrate_protection_in_activation_window():
    """
    Пример интеграции в activation_window.py:

    1. Добавить в начало файла:
    from .master_protection import critical_function, heavy_obfuscation

    2. Защитить класс ActivationWindow:

    @heavy_obfuscation
    class ActivationWindow(QWidget):
        @critical_function
        def __init__(self):


        @critical_function
        def validate_license(self):


        @heavy_obfuscation
        def handle_activation(self):

    """
    pass

def integrate_protection_in_main_window():
    """
    Пример интеграции в main_window.py:

    1. Добавить импорты:
    from .master_protection import critical_function, heavy_obfuscation

    2. Защитить основные методы:

    class MainWindow(QMainWindow):
        @critical_function
        def __init__(self):


        @heavy_obfuscation
        def load_sessions(self):


        @critical_function
        def send_messages(self):


        @heavy_obfuscation
        def manage_bots(self):

    """
    pass

def integrate_protection_in_telegram_client():
    """
    Пример интеграции в telegramclient.py:

    1. Добавить импорты:
    from .master_protection import critical_function, heavy_obfuscation

    2. Защитить работу с API:

    @critical_function
    async def connect_client(phone_number, api_id, api_hash):


    @heavy_obfuscation
    async def send_message(client, chat_id, message):


    @critical_function
    def validate_session(session_string):

    """
    pass



PROTECTION_TEMPLATE_IMPORTS = '''

from .master_protection import critical_function, heavy_obfuscation, is_protection_active
from .advanced_obfuscation import obfuscate_function
'''

PROTECTION_TEMPLATE_CLASS = '''

@heavy_obfuscation
class YourClass:
    @critical_function
    def __init__(self):

        if not is_protection_active():
            raise RuntimeError("Security system not initialized")


    @heavy_obfuscation
    def important_method(self):


    @critical_function
    def sensitive_operation(self):

'''

PROTECTION_TEMPLATE_FUNCTIONS = '''


@critical_function
def validate_user_input(data):


@heavy_obfuscation
def process_sensitive_data(data):


@critical_function
@heavy_obfuscation
def maximum_protection_function():

'''


def auto_integrate_protection(file_path: str, protection_level: str = "medium"):
    """
    Автоматически добавляет защиту в существующий Python файл.

    Args:
        file_path: путь к файлу для защиты
        protection_level: уровень защиты ("light", "medium", "heavy")
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()


        if 'from .master_protection import' not in content:
            import_line = "from .master_protection import critical_function, heavy_obfuscation\n"


            lines = content.split('\n')
            insert_index = 0


            for i, line in enumerate(lines):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    insert_index = i + 1

            lines.insert(insert_index, import_line)
            content = '\n'.join(lines)


        if protection_level == "light":
            class_decorator = ""
            method_decorator = "@critical_function\n    "
        elif protection_level == "medium":
            class_decorator = "@heavy_obfuscation\n"
            method_decorator = "@critical_function\n    "
        else:
            class_decorator = "@heavy_obfuscation\n"
            method_decorator = "@critical_function\n    @heavy_obfuscation\n    "


        lines = content.split('\n')
        new_lines = []

        for i, line in enumerate(lines):

            if line.strip().startswith('class ') and class_decorator:
                new_lines.append(class_decorator.rstrip())
                new_lines.append(line)

            elif (line.strip().startswith('def ') and
                  i > 0 and any(lines[j].strip().startswith('class ') for j in range(max(0, i-20), i))):
                indent = len(line) - len(line.lstrip())
                decorator_with_indent = ' ' * indent + method_decorator.lstrip().replace('\n    ', '\n' + ' ' * indent)
                new_lines.append(decorator_with_indent.rstrip())
                new_lines.append(line)
            else:
                new_lines.append(line)

        content = '\n'.join(new_lines)


        backup_path = file_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:

            with open(file_path, 'r', encoding='utf-8') as original:
                f.write(original.read())

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Protection integrated into {file_path}")
        print(f"Backup saved as {backup_path}")

    except Exception as e:
        print(f"Error integrating protection: {e}")


def quick_protect_activation_window():
    """Быстрая защита activation_window.py"""
    auto_integrate_protection("ui/activation_window.py", "heavy")

def quick_protect_main_window():
    """Быстрая защита main_window.py"""
    auto_integrate_protection("ui/main_window.py", "heavy")

def quick_protect_telegram_client():
    """Быстрая защита telegramclient.py"""
    auto_integrate_protection("ui/telegramclient.py", "heavy")

def quick_protect_all_modules():
    """Быстрая защита всех модулей в папке ui"""
    import glob

    py_files = glob.glob("ui/*.py")
    protected_files = [
        "ui/anti_debug.py",
        "ui/code_obfuscator.py",
        "ui/integrity_checker.py",
        "ui/master_protection.py",
        "ui/advanced_obfuscation.py",
        "ui/protection_integration.py"
    ]

    for file_path in py_files:
        if file_path not in protected_files and not file_path.endswith("__init__.py"):
            auto_integrate_protection(file_path, "medium")

    print("All modules protected successfully!")

if __name__ == "__main__":
    print("Доступные функции для интеграции защиты:")
    print("1. quick_protect_activation_window() - защита окна активации")
    print("2. quick_protect_main_window() - защита главного окна")
    print("3. quick_protect_telegram_client() - защита клиента Telegram")
    print("4. quick_protect_all_modules() - защита всех модулей")
    print("\nПримеры кода для ручной интеграции:")
    print(PROTECTION_TEMPLATE_IMPORTS)
    print(PROTECTION_TEMPLATE_CLASS)
    print(PROTECTION_TEMPLATE_FUNCTIONS)
