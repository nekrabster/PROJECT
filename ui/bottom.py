import os
import sys
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGraphicsDropShadowEffect, QToolButton
)
from ui.svg_utils import create_svg_icon
from ui.svg_icons import get_svg_icons, get_icon_color
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), os.pardir, relative_path)
class BottomBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.is_dark_theme = main_window.is_dark_theme
        self.svg_icons = get_svg_icons()
        self.update_icons()
    def update_icons(self, *args, **kwargs):
        is_dark = getattr(self.main_window, 'is_dark_theme', False)
        self.icon_color = get_icon_color(is_dark)
    def _button_style(self, *args, **kwargs):
        return """
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
        """
    def create_bottom_bar(self, *args, **kwargs):
        bottom_content = QWidget()
        bottom_content.setFixedHeight(50)
        bottom_layout = QHBoxLayout(bottom_content)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)
        shadow_bottom = QGraphicsDropShadowEffect(self.main_window)
        shadow_bottom.setBlurRadius(4)
        shadow_bottom.setOffset(0, -1)
        bottom_content.setGraphicsEffect(shadow_bottom)
        btn_subscribe = QToolButton()
        subscribe_icon = create_svg_icon(self.svg_icons['chart'], getattr(self, 'icon_color', '#87CEEB'))
        btn_subscribe.setIcon(subscribe_icon)
        btn_subscribe.setIconSize(QSize(36, 36))
        btn_subscribe.setToolTip("Накрут/Грев")
        btn_subscribe.setAutoRaise(True)
        btn_subscribe.setStyleSheet(self._button_style())
        btn_subscribe.clicked.connect(lambda: self.main_window.handle_window_switch('subscribe'))
        bottom_layout.addWidget(btn_subscribe)
        btn_session = QToolButton()
        session_icon = create_svg_icon(self.svg_icons['chat'], getattr(self, 'icon_color', '#87CEEB'))
        btn_session.setIcon(session_icon)
        btn_session.setIconSize(QSize(36, 36))
        btn_session.setToolTip("Автоответы ботов")
        btn_session.setAutoRaise(True)
        btn_session.setStyleSheet(self._button_style())
        btn_session.clicked.connect(lambda: self.main_window.handle_window_switch('session'))
        bottom_layout.addWidget(btn_session)
        btn_rass = QToolButton()
        rass_icon = create_svg_icon(self.svg_icons['broadcast'], getattr(self, 'icon_color', '#87CEEB'))
        btn_rass.setIcon(rass_icon)
        btn_rass.setIconSize(QSize(36, 36))
        btn_rass.setToolTip("Рассылка ботов")
        btn_rass.setAutoRaise(True)
        btn_rass.setStyleSheet(self._button_style())
        btn_rass.clicked.connect(lambda: self.main_window.handle_window_switch('rass'))
        bottom_layout.addWidget(btn_rass)
        btn_components = QToolButton()
        components_icon = create_svg_icon(self.svg_icons['search'], getattr(self, 'icon_color', '#87CEEB'))
        btn_components.setIcon(components_icon)
        btn_components.setIconSize(QSize(36, 36))
        btn_components.setToolTip("Бустер/Чекер")
        btn_components.setAutoRaise(True)
        btn_components.setStyleSheet(self._button_style())
        btn_components.clicked.connect(lambda: self.main_window.handle_window_switch('components'))
        bottom_layout.addWidget(btn_components)
        btn_complas = QToolButton()
        complas_icon = create_svg_icon(self.svg_icons['edit'], getattr(self, 'icon_color', '#87CEEB'))
        btn_complas.setIcon(complas_icon)
        btn_complas.setIconSize(QSize(36, 36))
        btn_complas.setToolTip("Отправка жалоб")
        btn_complas.setAutoRaise(True)
        btn_complas.setStyleSheet(self._button_style())
        btn_complas.clicked.connect(lambda: self.main_window.handle_window_switch('complas'))
        bottom_layout.addWidget(btn_complas)
        bottom_layout.addStretch(1)
        return bottom_content 
