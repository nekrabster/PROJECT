from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QSizePolicy, QGroupBox
)
from aiogram.types import BotCommand
from ui.progress import ProgressWidget
import re
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.appchuy import AiogramBotConnection
class BotThread(BaseThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(str, bool, str, str)
    def __init__(self, token, param, value, min_delay=1, max_delay=3, list_value=None, idx=None, total=None, parent=None):
        super().__init__(session_file=token, parent=parent)
        self.token = token
        self.param = param
        self.value = value
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.list_value = list_value
        self.idx = idx
        self.total = total
        self._running = True
        self.bot_manager = AiogramBotConnection(token)
        self.bot_manager.log_signal.connect(self.log_signal.emit)
        self.bot_manager.error_signal.connect(lambda t, e: self.error_signal.emit(t, e.message))
    def stop(self, *args, **kwargs):
        self._running = False
    async def process(self, *args, **kwargs):
        if not self._running:
            self.finished_signal.emit(self.token, False, self.param, self.value)
            return
        try:
            bot = await self.bot_manager.connect()
            bot_name = None
            try:
                bot_info = await bot.get_me()
                bot_name = bot_info.username or "Без имени"
            except Exception:
                bot_name = None
            value = self.value
            if self.list_value is not None and self.idx is not None:
                if self.idx < len(self.list_value):
                    value = self.list_value[self.idx].strip()
            if self.param == 'name' and value:
                await bot.set_my_name(name=value)
                self.log_signal.emit(f"✅ Имя изменено для {bot_name} ({self.token[:10]}...): '{value}'")
            elif self.param == 'description' and value:
                await bot.set_my_description(description=value)
                self.log_signal.emit(f"✅ Описание изменено для {bot_name} ({self.token[:10]}...): '{value}'")
            elif self.param == 'short_description' and value:
                await bot.set_my_short_description(short_description=value)
                self.log_signal.emit(f"✅ Краткое описание изменено для {bot_name} ({self.token[:10]}...): '{value}'")
            commands = [
                BotCommand(command="/start", description="Запустить бота"),
                BotCommand(command="/help", description="Получить помощь"),
            ]
            await bot.set_my_commands(commands)
            await self.bot_manager.disconnect()
            self.progress_signal.emit(100, f"Готово для {bot_name} ({self.token[:10]}...)")
            self.finished_signal.emit(self.token, True, self.param, value)
        except Exception as e:
            msg = str(e)
            if 'flood' in msg.lower() or 'too many requests' in msg.lower():
                seconds = self._extract_flood_seconds(msg)
                bot_id = bot_name if bot_name else f"{self.token[:10]}..."
                if seconds:
                    msg = f"⏳ FloodWait для бота {bot_id}: слишком много запросов. Подождите {seconds} секунд и попробуйте снова."
                else:
                    msg = f"⏳ FloodWait для бота {bot_id}: слишком много запросов. Подождите и попробуйте снова."
            self.error_signal.emit(self.token, msg)
            self.finished_signal.emit(self.token, False, self.param, value)
    def _extract_flood_seconds(self, msg, *args, **kwargs):
        match = re.search(r'(\d+)\s*seconds?', msg)
        if match:
            return match.group(1)
        match = re.search(r'wait\s*(\d+)', msg)
        if match:
            return match.group(1)
        return None
class BotManagerDialog(QDialog, ThreadStopMixin):
    bot_updated = pyqtSignal(str, str, str)
    def __init__(self, session_folder=None, selected_sessions=None, parent=None):
        super().__init__(parent)
        ThreadStopMixin.__init__(self)
        self.selected_tokens = selected_sessions or []
        self.completed_tokens = set()
        self.total_tokens = len(self.selected_tokens)
        self.active_param = None
        self.running = False
        self._is_closing = False
        self.report_shown = False
        self.setup_ui()
        if self.selected_tokens:
            if len(self.selected_tokens) == 1:
                self.log_area.append(f"✏️ Редактирование бота: {self.selected_tokens[0][:10]}...")
            else:
                self.log_area.append(f"📝 Выбрано ботов для редактирования: {len(self.selected_tokens)}")
    def select_param(self, param, *args, **kwargs):
        if param == 'name':
            self.set_active_param('name', self.name_btn)
        elif param == 'description':
            self.set_active_param('description', self.desc_btn)
        elif param == 'short_description':
            self.set_active_param('short_description', self.short_desc_btn)
    def setup_ui(self, *args, **kwargs):
        self.setWindowTitle("Редактор ботов")
        if len(self.selected_tokens) == 1:
            self.setWindowTitle(f"Редактор бота: {self.selected_tokens[0][:10]}...")
        self.setMinimumWidth(800)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QVBoxLayout(self)
        bot_actions_group = QGroupBox("Управление параметрами бота")
        bot_actions_layout = QVBoxLayout(bot_actions_group)
        bot_actions_group.setLayout(bot_actions_layout) 
        button_layout = QHBoxLayout()
        font = QFont()
        font.setPointSize(9)
        self.name_btn = QPushButton("👤 Имя")
        self.name_btn.setFont(font)
        self.name_btn.setFixedHeight(40)
        self.name_btn.setMinimumWidth(120)
        self.name_btn.setMaximumWidth(300)
        self.name_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.name_btn.clicked.connect(lambda: self.select_param('name'))
        button_layout.addWidget(self.name_btn)
        self.desc_btn = QPushButton("📝 Описание")
        self.desc_btn.setFont(font)
        self.desc_btn.setFixedHeight(40)
        self.desc_btn.setMinimumWidth(120)
        self.desc_btn.setMaximumWidth(300)
        self.desc_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.desc_btn.clicked.connect(lambda: self.select_param('description'))
        button_layout.addWidget(self.desc_btn)
        self.short_desc_btn = QPushButton("📋 Краткое")
        self.short_desc_btn.setFont(font)
        self.short_desc_btn.setFixedHeight(40)
        self.short_desc_btn.setMinimumWidth(120)
        self.short_desc_btn.setMaximumWidth(300)
        self.short_desc_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.short_desc_btn.clicked.connect(lambda: self.select_param('short_description'))
        button_layout.addWidget(self.short_desc_btn)        
        bot_actions_layout.addLayout(button_layout)
        self.param_input = QTextEdit(self)
        self.param_input.setPlaceholderText("Введите новые значения (каждое с новой строки)...")
        self.param_input.setMinimumHeight(100)
        self.param_input.setMaximumHeight(200)
        bot_actions_layout.addWidget(self.param_input)
        action_buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ Начать")
        self.stop_btn = QPushButton("⏹ Остановить")
        self.start_btn.clicked.connect(self.start_update)
        self.stop_btn.clicked.connect(self.stop_update)
        self.stop_btn.setEnabled(False)
        action_buttons_layout.addWidget(self.start_btn)
        action_buttons_layout.addWidget(self.stop_btn)
        bot_actions_layout.addLayout(action_buttons_layout)
        main_layout.addWidget(bot_actions_group)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area)
        self.progress_widget = ProgressWidget(self)
        main_layout.addWidget(self.progress_widget)
        QTimer.singleShot(100, self.param_input.setFocus)
    def set_active_param(self, param: str, btn: QPushButton, *args, **kwargs) -> None:
        self.active_param = param
        for b in [self.name_btn, self.desc_btn, self.short_desc_btn]:
            if b == btn:
                b.setStyleSheet("background-color: #aee571;")
            else:
                b.setStyleSheet("")
        self.param_input.setEnabled(True)
        self.param_input.setPlaceholderText("Введите новое значение...")
        self.param_input.setFocus()
    def start_update(self, *args, **kwargs) -> None:
        if self.running:
            self.log_area.append("⚠️ Процесс уже запущен")
            return
        if not self.selected_tokens:
            self.log_area.append("⚠️ Не выбрано ни одного бота")
            return
        if not self.active_param:
            self.log_area.append("⚠️ Выберите действие (имя, описание и т.д.)")
            return
        values = [v.strip() for v in self.param_input.toPlainText().split('\n') if v.strip()]
        if not values:
            self.log_area.append(f"⚠️ Введите новое значение для {self.active_param}")
            return
        self.running = True
        self.completed_tokens = set()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        for btn in [self.name_btn, self.desc_btn, self.short_desc_btn]:
            btn.setEnabled(False)
        self.param_input.setEnabled(False)
        self.total_tokens = len(self.selected_tokens)
        self.progress_widget.update_progress(0, "Запуск процесса...")
        if len(values) < len(self.selected_tokens):
            values.extend([values[-1]] * (len(self.selected_tokens) - len(values)))
        for idx, token in enumerate(self.selected_tokens):
            thread = BotThread(
                token=token,
                param=self.active_param,
                value=values[0],
                min_delay=3,
                max_delay=3,
                list_value=values, 
                idx=idx, 
                total=len(self.selected_tokens),
                parent=self
            )
            thread.log_signal.connect(lambda msg: self.log_area.append(msg))
            thread.error_signal.connect(self.handle_session_error)
            thread.progress_signal.connect(self.update_session_progress)
            thread.finished_signal.connect(self._handle_thread_finished)
            self.thread_manager.start_thread(thread)
            launch_progress = self.thread_manager.get_total_count() * 100 // self.total_tokens
            self.progress_widget.update_progress(
                launch_progress,
                f"Запущено {self.thread_manager.get_total_count()}/{self.total_tokens}"
            )
    def stop_update(self, *args, **kwargs) -> None:
        self.running = False
        self.log_area.append("⏹️ Останавливаем процесс...")
        self.stop_all_operations()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_widget.update_progress(100, "Остановлено")
        self.log_area.append("✅ Все процессы остановлены")
        for btn in [self.name_btn, self.desc_btn, self.short_desc_btn]:
            btn.setEnabled(True)
        self.param_input.setEnabled(True)
    def handle_session_error(self, error_type: str, message: str, *args, **kwargs) -> None:
        error_prefix = {
            'FloodWait': '⏳',
            'AuthError': '🔒',
            'NetworkError': '🌐',
            'FileError': '📁',
            'ThreadError': '⚠️',
            'ProcessError': '❌',
            'InitError': '⚠️'
        }.get(error_type, '❌')
        self.log_area.append(f"{error_prefix} {message}")
    def update_session_progress(self, percent: int, message: str, *args, **kwargs) -> None:
        if not self._is_closing:
            self.progress_widget.update_progress(percent, message)
    def _handle_thread_finished(self, token: str, success: bool, param: str, value: str, *args, **kwargs) -> None:
        if success:
            self.bot_updated.emit(token, param, value)
        
        self._on_thread_finished(self.thread_manager.get_thread_by_session(token))
    def _on_thread_finished(self, thread: BaseThread, *args, **kwargs):
        self.completed_tokens.add(thread.token)
        progress = len(self.completed_tokens) * 100 // self.total_tokens
        self.progress_widget.update_progress(
            progress,
            f"Завершено {len(self.completed_tokens)}/{self.total_tokens}"
        )
        if len(self.completed_tokens) >= self.total_tokens and not self.report_shown:
            self.report_shown = True
            self.running = False            
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.name_btn.setEnabled(True)
            self.desc_btn.setEnabled(True)
            self.short_desc_btn.setEnabled(True)
            self.param_input.setEnabled(True)            
            self.active_param = None
            for btn in [self.name_btn, self.desc_btn, self.short_desc_btn]:
                btn.setStyleSheet("")            
            self.progress_widget.update_progress(100, "Все задачи завершены")
            self.log_area.append(f"✅ Все {self.total_tokens} ботов обработаны")
    def closeEvent(self, event, *args) -> None:
        self._is_closing = True
        self.log_area.append("Ожидание завершения процессов перед закрытием...")
        self.stop_all_operations()
        event.accept()
