import os, asyncio, logging
from typing import Dict, List, Optional, Tuple, Set
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox,
    QCheckBox, QSizePolicy, QScrollArea, QPushButton,
    QHBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, pyqtSlot
from PyQt6.QtGui import QPainter, QColor, QPen
from ui.loader import get_session_config
class ToggleSwitch(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(QSize(50, 24))
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.1);
                border: none;
                border-radius: 12px;
            }
            QPushButton:checked {
                background-color:
            }
        """)
    def paintEvent(self, event, *args):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 2))
        if self.isChecked():
            painter.setBrush(QColor("white"))
            painter.drawEllipse(26, 2, 20, 20)
        else:
            painter.setBrush(QColor("white"))
            painter.drawEllipse(4, 2, 20, 20)
class SessionWindow(QWidget):
    sessions_updated = pyqtSignal(list)
    folder_updated = pyqtSignal(list)
    @pyqtSlot(dict)
    def on_config_changed(self, config):
        if config is None:
            return
        if 'SESSION_FOLDER' in config:
            self.update_session_folder(config['SESSION_FOLDER'])
    def __init__(self, session_folder: str, parent=None):
        super().__init__(parent)
        self.session_folder = session_folder
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.session_cache: Dict[str, Tuple] = {}
        self.folder_checkboxes: Dict[str, QCheckBox] = {}
        self.session_checkboxes: Dict[str, QCheckBox] = {}
        self.folder_sessions: Dict[str, List[str]] = {}
        self._last_valid_sessions: Set[str] = set()
        self._last_folder_state: Dict[str, float] = {}
        self._default_selected = True
        self.show_folders = True
        self._monitor_task = None
        self._is_running = True
        self._last_emitted_sessions = set()
        self.setFixedWidth(270)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("QWidget { font-size: 11pt; } ")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(8)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(5, 5, 5, 5)
        toggle_layout.setSpacing(10)
        self.mode_label = QLabel("Папки")
        font_mode = self.mode_label.font()
        font_mode.setPointSize(12)
        font_mode.setBold(True)
        self.mode_label.setFont(font_mode)
        self.mode_label.setToolTip("Переключить режим отображения: Папки/Сессии")
        self.mode_toggle = ToggleSwitch()
        self.mode_toggle.setChecked(True)
        self.mode_toggle.setToolTip("Переключить режим отображения")
        self.mode_toggle.clicked.connect(self.on_display_mode_changed)
        toggle_layout.addWidget(self.mode_label)
        toggle_layout.addWidget(self.mode_toggle)
        toggle_layout.addStretch()
        self.main_layout.addLayout(toggle_layout)
        self.select_all_checkbox = QCheckBox("Выбрать все")
        font_select_all = self.select_all_checkbox.font()
        font_select_all.setPointSize(11)
        font_select_all.setBold(True)
        self.select_all_checkbox.setFont(font_select_all)
        self.select_all_checkbox.setToolTip("Выбрать или снять выделение со всех элементов")
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)
        self.main_layout.addWidget(self.select_all_checkbox)
        self.session_groupbox = QGroupBox("Выберите папки с сессиями")
        font = self.session_groupbox.font()
        font.setPointSize(12)
        font.setBold(True)
        self.session_groupbox.setFont(font)
        self.session_groupbox.setStyleSheet("QGroupBox { margin-top: 12px; padding: 8px 0 0 0; font-weight: bold; border: 1px solid #ccc; border-radius: 8px; } ")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)
        container = QWidget()
        self.session_layout = QVBoxLayout(container)
        self.session_layout.setSpacing(8)
        self.session_layout.setContentsMargins(8, 8, 8, 8)
        self.session_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        self.session_groupbox.setLayout(QVBoxLayout())
        self.session_groupbox.layout().addWidget(scroll)
        self.main_layout.addWidget(self.session_groupbox)
        self.logger = logging.getLogger('SessionWindow')
        self.logger.setLevel(logging.ERROR)
        QTimer.singleShot(0, self.start_async_tasks)
    def start_async_tasks(self, *args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._monitor_task = loop.create_task(self.monitor_folder_changes())
        loop.create_task(self.load_sessions_async())
    @lru_cache(maxsize=100)
    def get_session_config_cached(self, session_path: str, *args) -> Optional[Tuple]:
        return get_session_config(session_path)
    async def load_sessions_async(self, *args):
        try:
            sessions = []
            for root, dirs, files in os.walk(self.session_folder):
                for file in files:
                    if file.endswith('.session'):
                        sessions.append(os.path.relpath(os.path.join(root, file), self.session_folder))
            folder_sessions = {}
            valid_sessions = []
            for sess in sessions:
                path = os.path.join(self.session_folder, sess)
                cfg = await asyncio.get_event_loop().run_in_executor(
                    self.executor, self.get_session_config_cached, path
                )
                if not cfg or not cfg[0] or not cfg[1] or str(cfg[0]) == '0' or not str(cfg[1]).strip():
                    self.logger.warning(f"Invalid API_ID or API_HASH for session {sess}")
                    continue
                valid_sessions.append(sess)
                self.session_cache[sess] = cfg
                folder = os.path.dirname(sess)
                if folder:
                    if folder not in folder_sessions:
                        folder_sessions[folder] = []
                    folder_sessions[folder].append(sess)
            self.folder_sessions = folder_sessions
            self.update_sessions_list(valid_sessions)
            self.sessions_updated.emit(valid_sessions)
        except Exception as e:
            self.logger.error(f"Error loading sessions: {e}")
    async def monitor_folder_changes(self, *args):
        while self._is_running:
            try:
                current_state = {}
                for root, dirs, files in os.walk(self.session_folder):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        current_state[dir_path] = os.path.getmtime(dir_path)
                    for file in files:
                        if file.endswith('.session'):
                            file_path = os.path.join(root, file)
                            current_state[file_path] = os.path.getmtime(file_path)
                if current_state != self._last_folder_state:
                    self.logger.debug("Detected folder changes, updating sessions...")
                    self._last_folder_state = current_state
                    self.session_checkboxes.clear()
                    self.folder_checkboxes.clear()
                    await self.load_sessions_async()
            except Exception as e:
                self.logger.error(f"Error monitoring folder changes: {e}")
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
    def on_display_mode_changed(self, checked: bool, *args):
        self.show_folders = checked
        self.mode_label.setText("Папки" if checked else "Сессии")
        folder_states = {}
        session_states = {}
        if self.show_folders:
            for session, cb in self.session_checkboxes.items():
                session_states[session] = cb.isChecked()
            self.session_checkboxes.clear()
        else:
            for folder, cb in self.folder_checkboxes.items():
                folder_states[folder] = cb.isChecked()
            self.folder_checkboxes.clear()
        self.update_sessions_list(force_update=True)
        if self.show_folders:
            for folder, state in folder_states.items():
                if folder in self.folder_checkboxes:
                    self.folder_checkboxes[folder].setChecked(state)
        elif not self.show_folders:
            for session, state in session_states.items():
                if session in self.session_checkboxes:
                    self.session_checkboxes[session].setChecked(state)
    def on_select_all_changed(self, state, *args):
        is_checked = bool(state)
        if self.show_folders:
            for folder_cb in self.folder_checkboxes.values():
                folder_cb.setChecked(is_checked)
        else:
            for session_cb in self.session_checkboxes.values():
                session_cb.setChecked(is_checked)
    def update_sessions_list(self, valid_sessions: Optional[List[str]] = None, force_update: bool = False, *args):
        if valid_sessions is None:
            valid_sessions = list(self.session_cache.keys())
        if not force_update and hasattr(self, '_last_valid_sessions'):
            if set(valid_sessions) == set(self._last_valid_sessions):
                return
        self._last_valid_sessions = valid_sessions
        layout = self.session_layout
        folder_states = {folder: cb.isChecked() for folder, cb in self.folder_checkboxes.items()}
        session_states = {session: cb.isChecked() for session, cb in self.session_checkboxes.items()}
        self.folder_checkboxes.clear()
        self.session_checkboxes.clear()
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget and widget != self.mode_toggle:
                layout.removeWidget(widget)
                widget.deleteLater()
        if self.show_folders:
            for folder, sessions in sorted(self.folder_sessions.items()):
                folder_name = os.path.basename(folder)
                session_count = len(sessions)
                folder_container = QWidget()
                folder_layout = QVBoxLayout(folder_container)
                folder_layout.setSpacing(2)
                folder_layout.setContentsMargins(0, 8, 0, 12)
                folder_cb = QCheckBox(folder_name)
                font = folder_cb.font()
                font.setBold(True)
                font.setPointSize(12)
                folder_cb.setFont(font)
                folder_cb.setToolTip(f"Папка: {folder_name}\nСессий: {session_count}")
                folder_cb.setChecked(folder_states.get(folder, True))
                folder_cb.stateChanged.connect(lambda state, f=folder: self.on_folder_state_changed(f, state))
                self.folder_checkboxes[folder] = folder_cb
                sessions_label = QLabel(f"{session_count} сессий")
                sessions_label.setStyleSheet("font-size: 10pt; margin-left: 8px;")
                folder_layout.addWidget(folder_cb)
                folder_layout.addWidget(sessions_label)
                folder_layout.addSpacing(4)
                layout.addWidget(folder_container)
        else:
            for session in sorted(valid_sessions):
                session_cb = QCheckBox(os.path.basename(session))
                font = session_cb.font()
                font.setPointSize(11)
                font.setBold(False)
                session_cb.setFont(font)
                session_cb.setToolTip(f"Сессия: {session}")
                session_cb.setChecked(session_states.get(session, True))
                session_cb.stateChanged.connect(lambda state, s=session: self.on_session_state_changed(s, state))
                self.session_checkboxes[session] = session_cb
                layout.addWidget(session_cb)
        if self.show_folders:
            all_checked = all(cb.isChecked() for cb in self.folder_checkboxes.values())
            self.select_all_checkbox.setChecked(all_checked)
        else:
            all_checked = all(cb.isChecked() for cb in self.session_checkboxes.values())
            self.select_all_checkbox.setChecked(all_checked)
        selected_sessions = list(self._last_emitted_sessions) if self._last_emitted_sessions else []
        self.sessions_updated.emit(selected_sessions)
        self.folder_updated.emit(list(self.folder_sessions.keys()))
    def on_folder_state_changed(self, folder: str, state: int, *args):
        selected_sessions = []
        for f, cb in self.folder_checkboxes.items():
            if cb and cb.isChecked() and f in self.folder_sessions:
                selected_sessions.extend(self.folder_sessions[f])
        self._last_emitted_sessions = set(selected_sessions)
        self.sessions_updated.emit(selected_sessions)
    def on_session_state_changed(self, session: str, state: int, *args):
        selected_sessions = []
        for s, cb in self.session_checkboxes.items():
            if cb and cb.isChecked():
                selected_sessions.append(s)
        self._last_emitted_sessions = set(selected_sessions)
        self.sessions_updated.emit(selected_sessions)
    def get_selected_sessions(self, *args) -> List[str]:
        selected_sessions = []
        try:
            if self.show_folders:
                for folder, cb in list(self.folder_checkboxes.items()):
                    try:
                        if cb and cb.isChecked() and folder in self.folder_sessions:
                            selected_sessions.extend(self.folder_sessions[folder])
                    except RuntimeError:
                        continue
            else:
                for session, cb in list(self.session_checkboxes.items()):
                    try:
                        if cb and cb.isChecked():
                            selected_sessions.append(session)
                    except RuntimeError:
                        continue
            if not selected_sessions and self._default_selected:
                all_sessions = []
                for folder, sessions in self.folder_sessions.items():
                    all_sessions.extend(sessions)
                return all_sessions
        except Exception as e:
            self.logger.error(f"Ошибка при получении выбранных сессий: {e}")
        return selected_sessions
    def get_session_config(self, session_name: str, *args) -> Optional[Tuple]:
        return self.session_cache.get(session_name)
    def update_session_folder(self, new_folder: str, *args):
        self.session_folder = new_folder
        self.session_cache.clear()
        self.folder_checkboxes.clear()
        self.folder_sessions.clear()
        asyncio.create_task(self.load_sessions_async())
    def refresh_sessions(self, *args):
        asyncio.create_task(self.load_sessions_async())
    def closeEvent(self, event, *args):
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        self.executor.shutdown(wait=False)
        super().closeEvent(event)
    def __del__(self, *args):
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        self.executor.shutdown(wait=False)
