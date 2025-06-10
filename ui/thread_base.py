import asyncio
import logging
import os
from typing import Optional, Dict, Any, List, Set
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QObject
from ui.timer import Timer
import random
class BaseThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str)
    done_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    delay_signal = pyqtSignal(int)
    def __init__(self, session_file: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.session_file = session_file
        self.running = True
        self.is_stopped = False
        self.loop = None
        self.task = None
        self.timer = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_timer()
    def _init_timer(self, *args, **kwargs):
        try:
            self.timer = Timer()
            self.timer.delay_changed.connect(lambda delay: self.delay_signal.emit(delay))
        except Exception as e:
            self.logger.warning(f"Не удалось инициализировать таймер: {e}")
    def set_delay_range(self, min_delay: int, max_delay: int, *args, **kwargs):
        if self.timer:
            self.timer.set_delay_range(min_delay, max_delay)
    async def apply_delay(self, *args, **kwargs) -> None:
        if self.timer:
            await self.timer.apply_delay()
        else:
            await asyncio.sleep(1)
    def emit_log(self, message: str, *args, **kwargs):
        self.log_signal.emit(message)
    def emit_progress(self, value: int, status: str):
        self.progress_signal.emit(value, status)
    def emit_error(self, error_message: str):
        self.error_signal.emit(error_message)
    def stop(self, *args, **kwargs):
        self.running = False
        self.is_stopped = True
        if self.task and not self.task.done():
            self.task.cancel()
        if self.timer:
            self.timer.stop()
        if hasattr(self, 'client') and self.client and self.loop and self.loop.is_running():
            try:
                disconnect_result = self.client.disconnect()
                if asyncio.iscoroutine(disconnect_result):
                    asyncio.run_coroutine_threadsafe(disconnect_result, self.loop)
            except (TypeError, RuntimeError, AttributeError) as e:
                self.emit_log(f"Ошибка при отключении клиента: {str(e)}")
    def run(self, *args, **kwargs):
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.task = self.loop.create_task(self.process())
            self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            self.emit_log("Поток был отменен")
        except Exception as e:
            self.emit_error(f"Ошибка в потоке: {str(e)}")
            self.logger.error(f"Thread error: {str(e)}")
        finally:
            self._cleanup()
    def _cleanup(self, *args, **kwargs):
        try:
            if hasattr(self, 'client') and self.client and self.loop and self.loop.is_running():
                try:
                    self.loop.run_until_complete(self.client.disconnect())
                except:
                    pass
        except:
            pass
        finally:
            if self.loop:
                self.loop.close()
            self.loop = None
            self.task = None
            self.done_signal.emit()
    async def process(self, *args, **kwargs):
        raise NotImplementedError("process() должен быть реализован в наследнике")
class TelegramThread(BaseThread):
    def __init__(self, session_file: str, session_folder: str, use_proxy: bool = False, parent=None):
        super().__init__(session_file, parent)
        self.session_folder = session_folder
        self.use_proxy = use_proxy
        self.client = None
    def get_session_name(self, *args, **kwargs) -> str:
        return os.path.basename(self.session_file) if self.session_file else "Unknown"
    def emit_session_log(self, message: str, *args, **kwargs):
        session_name = self.get_session_name()
        self.emit_log(f"{session_name} | {message}")
class ThreadManager:
    def __init__(self, parent=None):
        self.parent = parent
        self.threads: List[BaseThread] = []
        self.active_threads: Set[BaseThread] = set()
        self.completed_threads: Set[BaseThread] = set()
        self.logger = logging.getLogger(self.__class__.__name__)
    def add_thread(self, thread: BaseThread, *args, **kwargs) -> None:
        if thread not in self.threads:
            self.threads.append(thread)
            self.active_threads.add(thread)
            thread.done_signal.connect(lambda: self._on_thread_finished(thread))
            thread.error_signal.connect(lambda msg: self._on_thread_error(thread, msg))
    def start_thread(self, thread: BaseThread, *args, **kwargs) -> bool:
        try:
            if thread not in self.threads:
                self.add_thread(thread)
            thread.start()
            return True
        except Exception as e:
            self.logger.error(f"Ошибка запуска потока: {e}")
            return False
    def stop_all_threads(self, *args, **kwargs) -> None:
        for thread in list(self.active_threads):
            try:
                thread.stop()
            except Exception as e:
                self.logger.error(f"Ошибка остановки потока: {e}")
    def stop_thread(self, thread: BaseThread, *args, **kwargs) -> None:
        try:
            thread.stop()
        except Exception as e:
            self.logger.error(f"Ошибка остановки потока: {e}")
    def _on_thread_finished(self, thread: BaseThread, *args, **kwargs) -> None:
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        self.completed_threads.add(thread)
        if self.parent and hasattr(self.parent, '_on_thread_finished'):
            self.parent._on_thread_finished(thread)
    def _on_thread_error(self, thread: BaseThread, error_message: str, *args, **kwargs) -> None:
        if self.parent and hasattr(self.parent, '_on_thread_error'):
            self.parent._on_thread_error(thread, error_message)
    def get_active_count(self, *args, **kwargs) -> int:
        return len(self.active_threads)
    def get_completed_count(self, *args, **kwargs) -> int:
        return len(self.completed_threads)
    def get_total_count(self, *args, **kwargs) -> int:
        return len(self.threads)
    def is_all_finished(self, *args, **kwargs) -> bool:
        return len(self.active_threads) == 0
    def clear_completed(self, *args, **kwargs) -> None:
        self.completed_threads.clear()
        self.threads = [t for t in self.threads if t in self.active_threads]
    def get_thread_by_session(self, session, *args, **kwargs):
        for thread in self.threads:
            if hasattr(thread, 'session_file') and thread.session_file == session:
                return thread
            if thread == session:
                return thread
        return None
class DelayedThreadStarter(QObject):
    delay_signal = pyqtSignal(int)
    def __init__(self, thread_manager: ThreadManager, min_delay: int = 0, max_delay: int = 0):
        super().__init__()
        self.thread_manager = thread_manager
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.pending_threads: List[BaseThread] = []
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.setSingleShot(False)
        self.current_thread = None
        self._delay_left = 0
        self._next_thread = None
    def add_threads(self, threads: List[BaseThread], *args, **kwargs) -> None:
        self.pending_threads.extend(threads)
    def start_all(self, *args, **kwargs) -> None:
        if self.pending_threads and not self.current_thread:
            self._start_next_thread()
    def _start_next_thread(self, *args, **kwargs) -> None:
        if not self.pending_threads:
            self.current_thread = None
            self._next_thread = None
            self.timer.stop()
            self.delay_signal.emit(0)
            return
        if self.current_thread:
            return
        thread = self.pending_threads.pop(0)
        self.current_thread = thread
        thread.done_signal.connect(self._on_thread_finished)
        self.thread_manager.start_thread(thread)
        if self.pending_threads:
            delay = random.randint(self.min_delay, self.max_delay) if self.min_delay and self.max_delay and self.max_delay > 0 else 0
            self._delay_left = delay
            self._next_thread = self.pending_threads[0]
            if delay > 0:
                self.timer.start(1000)
                self.delay_signal.emit(self._delay_left)
            else:
                self._delay_left = 0
                self.timer.stop()
                self.delay_signal.emit(0)
        else:
            self._delay_left = 0
            self._next_thread = None
            self.timer.stop()
            self.delay_signal.emit(0)
    def _on_timer_tick(self):
        if self._delay_left > 0:
            self._delay_left -= 1
            self.delay_signal.emit(self._delay_left)
        if self._delay_left <= 0:
            self.timer.stop()
            self._start_next_thread()
    def _on_thread_finished(self, *args, **kwargs):
        self.current_thread = None
        if self._delay_left <= 0:
            self._start_next_thread()
    def stop(self, *args, **kwargs) -> None:
        self.timer.stop()
        self.pending_threads.clear()
        self.current_thread = None
        self._delay_left = 0
        self._next_thread = None
        self.delay_signal.emit(0)
class ThreadStopMixin:
    def __init__(self, *args, **kwargs):
        self.thread_manager = ThreadManager(self)
        self.delayed_starter = None
    def setup_delayed_starter(self, min_delay: int = 0, max_delay: int = 0, *args, **kwargs):
        self.delayed_starter = DelayedThreadStarter(self.thread_manager, min_delay, max_delay)
        self.delayed_starter.delay_signal.connect(self._on_delayed_starter_delay)
    def start_threads_with_delay(self, threads: List[BaseThread], min_delay: int = 0, max_delay: int = 0, *args, **kwargs):
        if not self.delayed_starter:
            self.setup_delayed_starter(min_delay, max_delay)
        self.delayed_starter.add_threads(threads)
        self.delayed_starter.start_all()
    def stop_all_operations(self, *args, **kwargs):
        if self.delayed_starter:
            self.delayed_starter.stop()
        if hasattr(self, 'thread_manager'):
            self.thread_manager.stop_all_threads()
    def _on_delayed_starter_delay(self, delay):
        if hasattr(self, 'update_delay_label'):
            self.update_delay_label(delay)
    def _on_thread_finished(self, thread: BaseThread, *args, **kwargs):
        pass
    def _on_thread_error(self, thread: BaseThread, error_message: str, *args, **kwargs):
        pass
