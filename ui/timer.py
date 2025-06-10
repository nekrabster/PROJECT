import random
import asyncio
from PyQt6.QtCore import QObject, pyqtSignal
class Timer(QObject):
    delay_changed = pyqtSignal(int)
    def __init__(self, min_delay=None, max_delay=None, *args):
        super().__init__()
        self.min_delay = min_delay
        self.max_delay = max_delay
    def set_delay_range(self, min_delay, max_delay, *args):
        if min_delay is not None and max_delay is not None:
            if min_delay > max_delay:
                raise ValueError("Минимальная задержка должна быть меньше или равна максимальной")
        self.min_delay = min_delay
        self.max_delay = max_delay
    def get_delay_range(self, *args):
        return self.min_delay, self.max_delay
    async def apply_delay(self, *args):
        delay = 0
        if self.min_delay is not None and self.max_delay is not None and self.min_delay > 0 and self.max_delay > 0:
            delay = random.randint(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)
        self.delay_changed.emit(delay)
        return delay
    @staticmethod
    def parse_delay_input(min_text, max_text, *args):
        try:
            min_delay = int(min_text) if min_text and min_text.isdigit() else None
            max_delay = int(max_text) if max_text and max_text.isdigit() else None
            if min_delay is not None and max_delay is not None:
                if min_delay > max_delay:
                    raise ValueError("Минимальная задержка должна быть меньше или равна максимальной")
            return min_delay, max_delay
        except ValueError as e:
            raise ValueError(f"Ошибка в интервалах задержки: {e}")
