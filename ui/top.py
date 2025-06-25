import os
import sys
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QToolButton, QGraphicsDropShadowEffect,
)
from .svg_utils import get_themed_icon
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), os.pardir, relative_path)
class TopBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.is_dark_theme = main_window.is_dark_theme
    def create_top_bar(self, *args, **kwargs):
        top_content = QWidget()
        top_content.setFixedHeight(50)
        top_layout = QHBoxLayout(top_content)
        top_layout.setContentsMargins(5, 5, 5, 5)
        top_layout.setSpacing(5)
        shadow_top = QGraphicsDropShadowEffect(self.main_window)
        shadow_top.setBlurRadius(4)
        shadow_top.setOffset(0, 1)
        top_content.setGraphicsEffect(shadow_top)
        self.api_btn = self._create_tool_button(get_themed_icon('settings', self.is_dark_theme), "Параметры Api", self.main_window.open_api_params)
        top_layout.addWidget(self.api_btn)
        self.proxy_btn = self._create_tool_button(get_themed_icon('globe', self.is_dark_theme), "Параметры прокси", self.main_window.open_proxy_params)
        top_layout.addWidget(self.proxy_btn)
        self.folder_btn = self._create_tool_button(get_themed_icon('folder', self.is_dark_theme), "Выбрать путь к папке с сессиями", self.main_window.choose_session_folder)
        top_layout.addWidget(self.folder_btn)
        self.bot_token_folder_btn = self._create_tool_button(get_themed_icon('folder', self.is_dark_theme), "Выбрать путь к папке с токенами ботов", self.main_window.choose_bot_token_folder)
        top_layout.addWidget(self.bot_token_folder_btn)
        self.text_btn = self._create_tool_button(get_themed_icon('edit', self.is_dark_theme), "Создать текст", self.main_window.open_create_text_dialog)
        top_layout.addWidget(self.text_btn)
        self.edit_txt_btn = self._create_tool_button(get_themed_icon('file', self.is_dark_theme), "Открыть и редактировать txt файл", self.main_window.open_edit_txt_dialog)
        top_layout.addWidget(self.edit_txt_btn)
        self.color_update_btn = self._create_tool_button(get_themed_icon('palette', self.is_dark_theme), "Обновить цвета интерфейса", self.main_window.update_interface_colors)
        top_layout.addWidget(self.color_update_btn)
        self.instructions_btn = self._create_tool_button(get_themed_icon('info', self.is_dark_theme), "Показать инструкцию к текущему окну", self.main_window.toggle_instruction_panel)
        top_layout.addWidget(self.instructions_btn)
        top_layout.addStretch(1)
        theme_icon_name = 'moon' if self.is_dark_theme else 'sun'
        self.theme_btn = self._create_tool_button(get_themed_icon(theme_icon_name, self.is_dark_theme), "Сменить тему", self.toggle_theme)
        top_layout.addWidget(self.theme_btn)
        return top_content
    def _create_shadow(self, blur=8, offset=(0, 0), color=(0, 0, 0, 120)):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setOffset(*offset)
        shadow.setColor(QColor(*color))
        return shadow
    def _create_tool_button(self, icon, tooltip, callback, icon_size=50, shadow_blur=8, shadow_offset=(0,0), shadow_color=(0,0,0,120)):
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setIcon(icon)
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                padding: 4px;
            }
            QToolButton:hover {
                background: transparent;
                border: none;
                padding: 6px 2px 2px 6px;
            }
            QToolButton:pressed {
                background: transparent;
                border: none;
                padding: 7px 1px 1px 7px;
            }
        """)
        shadow = self._create_shadow(shadow_blur, shadow_offset, shadow_color)
        btn.setGraphicsEffect(shadow)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        return btn
    def toggle_theme(self, *args, **kwargs):
        self.main_window.is_dark_theme = not self.main_window.is_dark_theme
        self.main_window.toggle_theme()
        self.update_theme_icon()
    def update_theme_icon(self, *args, **kwargs):
        self.is_dark_theme = self.main_window.is_dark_theme
        theme_icon_name = 'moon' if self.is_dark_theme else 'sun'
        if hasattr(self, 'theme_btn'):
            self.theme_btn.setIcon(get_themed_icon(theme_icon_name, self.is_dark_theme))
    def update_icons(self, dark, *args, **kwargs):
        if hasattr(self, 'api_btn'):
            self.api_btn.setIcon(get_themed_icon('settings', dark))
            self.proxy_btn.setIcon(get_themed_icon('globe', dark))
            self.folder_btn.setIcon(get_themed_icon('folder', dark))
            self.bot_token_folder_btn.setIcon(get_themed_icon('folder', dark))
            if hasattr(self, 'text_btn'):
                self.text_btn.setIcon(get_themed_icon('edit', dark))
            if hasattr(self, 'edit_txt_btn'):
                self.edit_txt_btn.setIcon(get_themed_icon('file', dark))
            self.color_update_btn.setIcon(get_themed_icon('palette', dark))
            self.instructions_btn.setIcon(get_themed_icon('info', dark))
        self.update_theme_icon()
