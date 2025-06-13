import os
import sys
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QToolButton, QGraphicsDropShadowEffect,
)
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
        self.api_btn = self._create_tool_button("icons/icon40.png", "Параметры Api", self.main_window.open_api_params)
        top_layout.addWidget(self.api_btn)
        self.proxy_btn = self._create_tool_button("icons/icon41.png", "Параметры прокси", self.main_window.open_proxy_params)
        top_layout.addWidget(self.proxy_btn)
        self.folder_btn = self._create_tool_button("icons/icon42.png", "Выбрать путь к папке с сессиями", self.main_window.choose_session_folder)
        top_layout.addWidget(self.folder_btn)
        self.bot_token_folder_btn = self._create_tool_button("icons/icon45.png", "Выбрать путь к папке с токенами ботов", self.main_window.choose_bot_token_folder)
        top_layout.addWidget(self.bot_token_folder_btn)
        self.text_btn = self._create_tool_button("icons/icon43.png", "Создать текст", self.main_window.open_create_text_dialog)
        top_layout.addWidget(self.text_btn)
        self.edit_txt_btn = self._create_tool_button("icons/icon54.png", "Открыть и редактировать txt файл", self.main_window.open_edit_txt_dialog)
        top_layout.addWidget(self.edit_txt_btn)
        self.color_update_btn = self._create_tool_button("icons/icon63.png", "Обновить цвета интерфейса", self.main_window.update_interface_colors)
        top_layout.addWidget(self.color_update_btn)
        self.instructions_btn = self._create_tool_button("icons/icon62.png", "Показать инструкцию к текущему окну", self.main_window.toggle_instruction_panel)
        top_layout.addWidget(self.instructions_btn)
        top_layout.addStretch(1)
        self.theme_btn = self._create_tool_button("icons/icon93.png", "Сменить тему", self.toggle_theme)
        top_layout.addWidget(self.theme_btn)
        self.update_theme_icon()
        return top_content
    def _create_shadow(self, blur=8, offset=(0, 0), color=(0, 0, 0, 120)):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur)
        shadow.setOffset(*offset)
        shadow.setColor(QColor(*color))
        return shadow
    def _create_tool_button(self, icon_path, tooltip, callback, icon_size=50, shadow_blur=8, shadow_offset=(0,0), shadow_color=(0,0,0,120)):
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setIcon(QIcon(resource_path(icon_path)))
        btn.setIconSize(QSize(icon_size, icon_size))
        btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
            }
            QToolButton:hover {
                padding: 2px;
                border: none;
                icon-size: 44px;
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
        icon_path = resource_path("icons/icon93.png") if self.is_dark_theme else resource_path("icons/icon83.png")
        if hasattr(self, 'theme_btn'):
            self.theme_btn.setIcon(QIcon(icon_path))
    def update_icons(self, dark, *args, **kwargs):
        if hasattr(self, 'api_btn'):
            icon = lambda n: QIcon(resource_path(f"icons/{n}"))
            if dark:
                self.api_btn.setIcon(icon('icon40.png'))
                self.proxy_btn.setIcon(icon('icon41.png'))
                self.folder_btn.setIcon(icon('icon42.png'))
                self.bot_token_folder_btn.setIcon(icon('icon45.png'))
                if hasattr(self, 'text_btn'):
                    self.text_btn.setIcon(icon('icon43.png'))
                if hasattr(self, 'edit_txt_btn'):
                    self.edit_txt_btn.setIcon(icon('icon44.png'))
                self.instructions_btn.setIcon(icon('icon62.png'))
            else:
                self.api_btn.setIcon(icon('icon50.png'))
                self.proxy_btn.setIcon(icon('icon51.png'))
                self.folder_btn.setIcon(icon('icon52.png'))
                self.bot_token_folder_btn.setIcon(icon('icon55.png'))
                if hasattr(self, 'text_btn'):
                    self.text_btn.setIcon(icon('icon53.png'))
                if hasattr(self, 'edit_txt_btn'):
                    self.edit_txt_btn.setIcon(icon('icon54.png'))
                self.instructions_btn.setIcon(icon('icon62.png'))
