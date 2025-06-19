import os
os.environ["QASYNC_QT_API"] = "pyqt6"
import sys
import asyncio
from qasync import QEventLoop, QApplication
import certifi
import requests
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
