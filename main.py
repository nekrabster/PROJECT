import os
os.environ["QASYNC_QT_API"] = "pyqt6"
import sys
import asyncio
from qasync import QEventLoop, QApplication
from ui.rudich import ActivationWindow
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
