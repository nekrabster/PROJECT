from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel
class ProgressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Готов к работе")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        self._last_progress_value = None
        self._last_status_text = None
    def update_progress(self, value: int, status_text: str, *args):
        if value == self._last_progress_value and status_text == self._last_status_text:
            return
        self._last_progress_value = value
        self._last_status_text = status_text
        self.progress_bar.setValue(value)
        self.status_label.setText(status_text)
