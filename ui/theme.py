from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication
from ui.damkrat import ColorGenerator
class ThemeManager:
    @staticmethod
    def detect_theme():
        app = QApplication.instance()
        palette = app.palette()
        return palette.color(QPalette.ColorRole.Window).value() < 128
    @staticmethod
    def toggle_theme(is_dark_theme):
        app = QApplication.instance()
        palette = QPalette()
        if is_dark_theme:
            palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 231, 227))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.Button, QColor(233, 231, 227))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)
        return palette
    @staticmethod
    def update_interface_colors(main_window):
        is_dark = ThemeManager.detect_theme()
        palette = ColorGenerator.generate_theme_palette(is_dark)
        main_window.update_stylesheet(
            custom_widget_bg=palette["custom_widget_bg"],
            btn_bg=palette["btn_bg"],
            btn_hover=palette["btn_hover"],
            btn_fg=palette["btn_fg"],
            lbl_fg=palette["lbl_fg"],
            inp_bg=palette["inp_bg"],
            inp_fg=palette["inp_fg"],
            inp_border=palette["inp_border"],
            textedit_bg=palette["textedit_bg"]
        )
        main_window.sidebar_styles = palette["sidebar_styles"]
        main_window.apply_sidebar_style()
        return palette
