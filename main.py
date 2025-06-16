import os
os.environ["QASYNC_QT_API"] = "pyqt6"

import sys
if sys.platform == "win32":
    try:
        import certifi_win32
        os.environ["REQUESTS_CA_BUNDLE"] = certifi_win32.wincerts.where()
        certifi_win32.generate_pem()
    except ImportError:
        print("certifi-win32 не установлен — HTTPS может не работать.")

import asyncio
from qasync import QEventLoop, QApplication
from ui.rudich import ActivationWindow

try:
    from ui.kms import initialize_master_protection, critical_function
    initialize_master_protection(stealth_mode=True)
except ImportError:
    def critical_function(func):
        return func

@critical_function
def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    try:
        activation_window = ActivationWindow()
        activation_window.show()
        loop.run_forever()
    except Exception as e:
        print(f"Ошибка при запуске приложения: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
