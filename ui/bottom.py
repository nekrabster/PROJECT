import os
import sys
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QGraphicsDropShadowEffect, QToolButton
)
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)
class BottomBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.is_dark_theme = main_window.is_dark_theme
    def _button_style(self, *args, **kwargs):
        return """
            QToolButton {
                background: transparent;
                border: none;
            }
            QToolButton:hover {
                padding: 2px;
                border: none;
                icon-size: 44px;
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
        btn_subscribe.setIcon(QIcon(resource_path("icons/icon5.png")))
        btn_subscribe.setIconSize(QSize(36, 36))
        btn_subscribe.setToolTip("Subscribe")
        btn_subscribe.setAutoRaise(True)
        btn_subscribe.setStyleSheet(self._button_style())
        btn_subscribe.clicked.connect(lambda: self.main_window.handle_window_switch('subscribe'))
        bottom_layout.addWidget(btn_subscribe)
        btn_session = QToolButton()
        btn_session.setIcon(QIcon(resource_path("icons/icon2.png")))
        btn_session.setIconSize(QSize(36, 36))
        btn_session.setToolTip("Session")
        btn_session.setAutoRaise(True)
        btn_session.setStyleSheet(self._button_style())
        btn_session.clicked.connect(lambda: self.main_window.handle_window_switch('session'))
        bottom_layout.addWidget(btn_session)
        btn_rass = QToolButton()
        btn_rass.setIcon(QIcon(resource_path("icons/icon12.png")))
        btn_rass.setIconSize(QSize(36, 36))
        btn_rass.setToolTip("Rass")
        btn_rass.setAutoRaise(True)
        btn_rass.setStyleSheet(self._button_style())
        btn_rass.clicked.connect(lambda: self.main_window.handle_window_switch('rass'))
        bottom_layout.addWidget(btn_rass)
        bottom_layout.addStretch(1)
        return bottom_content 
