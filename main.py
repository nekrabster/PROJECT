# main.py

import certifi  # явный импорт, чтобы Nuitka включил пакет certifi
_CERT_FILE = certifi.where()  # путь к cacert.pem внутри собранного exe

import os
os.environ["QASYNC_QT_API"] = "pyqt6"

import sys
import asyncio
from qasync import QEventLoop, QApplication

# Импорт окна активации
from ui.rudich import ActivationWindow

# Попытка подключить мастер-защиту из kms; если нет — фэйковая обёртка
try:
    from ui.kms import initialize_master_protection, critical_function
    initialize_master_protection(stealth_mode=True)
except ImportError:
    def critical_function(func):
        return func

@critical_function
def main():
    """
    Запускает Qt-приложение внутри asyncio-loop.
    Любые исключения выводятся в консоль и завершают процесс.
    """
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    try:
        activation_window = ActivationWindow()
        activation_window.show()
        loop.run_forever()
    except Exception as e:
        # Выводим ошибку и выходим с кодом 1
        print(f"Ошибка при запуске приложения: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()