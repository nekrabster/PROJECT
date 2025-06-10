import os
import re
from io import BytesIO
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QFileDialog, QMessageBox, QCheckBox, QDialogButtonBox, QWidget, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QPixmap, QImage
import logging
class MessageEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_path = None
        self.preview_image = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self.setup_ui()
    def setup_ui(self):
        self.setWindowTitle("Текст сообщения")
        self.setMinimumSize(800, 600)
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        randomization_layout = QHBoxLayout()
        self.randomize_checkbox = QCheckBox("Рандомизатор текста")
        self.randomize_checkbox.setToolTip(
            "При включении каждая сессия будет отправлять уникальный текст.\n"
            "Пример: Привет {друг|товарищ|коллега}! Как {дела|жизнь|всё}?\n"
            "Каждая сессия выберет случайный вариант из {вариант1|вариант2|вариант3}"
        )
        self.randomize_checkbox.toggled.connect(self.on_randomize_toggled)
        randomization_layout.addWidget(self.randomize_checkbox)
        randomization_layout.addStretch()
        input_layout.addLayout(randomization_layout)
        format_buttons = QHBoxLayout()
        buttons = [
            ("B", "**", "**", "Жирный текст"),
            ("I", "*", "*", "Курсив"),
            ("S", "~~", "~~", "Зачёркнутый текст"),
            ("U", "__", "__", "Подчёркнутый текст"),
            ("👁", "||", "||", "Спойлер"),
            ("M", "`", "`", "Моноширинный текст"),
            ("🔗", "[", "](url)", "Ссылка"),
            ("<>", "```\n", "\n```", "Блок кода"),
            ("🎲", "{", "}", "Рандомизация")
        ]
        for text, prefix, suffix, tooltip in buttons:
            btn = QPushButton(text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, p=prefix, s=suffix: self.insert_formatting(p, s))
            format_buttons.addWidget(btn)
        input_layout.addLayout(format_buttons)
        self.message_input = QTextEdit()
        self.message_input.textChanged.connect(self.update_preview)
        input_layout.addWidget(self.message_input)
        media_layout = QHBoxLayout()
        self.media_button = QPushButton("Загрузить изображение")
        self.media_button.clicked.connect(self.load_media)
        self.media_label = QLabel("Изображение не загружено")
        media_layout.addWidget(self.media_button)
        media_layout.addWidget(self.media_label)
        input_layout.addLayout(media_layout)
        splitter.addWidget(input_widget)
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.addWidget(QLabel("Предпросмотр:"))
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text)
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.hide()
        preview_layout.addWidget(self.image_preview)
        splitter.addWidget(preview_widget)
        layout.addWidget(splitter)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def load_media(self, file_path=None, *args, **kwargs):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Выберите изображение",
                "", "Изображения (*.png *.jpg *.jpeg *.gif)"
            )
        if not file_path:
            return
        try:
            with Image.open(file_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                max_size = 400
                ratio = min(max_size / img.width, max_size / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                qimg = QImage.fromData(img_byte_arr)
                self.preview_image = QPixmap.fromImage(qimg)
                self.media_path = file_path
            self.media_label.setText(f"Загружено: {os.path.basename(file_path)}")
            self.media_label.setStyleSheet("color: green;")
            self.update_preview()
            self.image_preview.setPixmap(self.preview_image)
            self.image_preview.show()
        except Exception as e:
            self._logger.error(f"Ошибка загрузки медиа: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить изображение: {str(e)}")
    def insert_formatting(self, prefix: str, suffix: str, *args, **kwargs):
        cursor = self.message_input.textCursor()
        selected_text = cursor.selectedText()
        if selected_text:
            cursor.insertText(f"{prefix}{selected_text}{suffix}")
        else:
            cursor.insertText(f"{prefix}{suffix}")
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(suffix))
            self.message_input.setTextCursor(cursor)
    def update_preview(self, *args, **kwargs):
        text = self.message_input.toPlainText()
        formatted_text = self._apply_formatting(text)
        self.preview_text.setHtml(formatted_text)
    def _apply_formatting(self, text: str) -> str:
        text = text.replace('\n', '<br>')
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text, flags=re.DOTALL)
        text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text, flags=re.DOTALL)
        text = re.sub(r'__(.+?)__', r'<u>\1</u>', text, flags=re.DOTALL)
        text = re.sub(r'\|\|(.+?)\|\|', r"<span class='spoiler'>\1</span>", text, flags=re.DOTALL)
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text, flags=re.DOTALL)
        text = re.sub(r'```(.+?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
        return f"<body>{text}</body>"
    def get_message(self, *args, **kwargs) -> Tuple[str, Optional[str], bool]:
        return self.message_input.toPlainText(), self.media_path, self.randomize_checkbox.isChecked()
    def on_randomize_toggled(self, checked, *args, **kwargs):
        if checked and not self.message_input.toPlainText():
            example_text = (
                "Привет {друг|товарищ|коллега}!\n"
                "Как {дела|жизнь|всё}?\n"
                "Надеюсь, у тебя всё {хорошо|отлично|замечательно}!"
            )
            self.message_input.setPlainText(example_text)
            self.update_preview() 
