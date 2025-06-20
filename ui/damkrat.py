from PyQt6.QtGui import QColor
from random import randint
class ColorGenerator:
    @staticmethod
    def generate_base_colors(is_dark):
        if is_dark:
            base_color = QColor(randint(20, 80), randint(20, 80), randint(20, 80))
        else:
            base_color = QColor(randint(180, 240), randint(180, 240), randint(180, 240))
        lighter_color = base_color.lighter(120)
        darker_color = base_color.darker(120)
        return base_color, lighter_color, darker_color
    @staticmethod
    def get_widget_colors(base_color, lighter_color, darker_color, is_dark):
        if is_dark:
            btn_bg_color = base_color.darker(140)
            btn_hover_color = base_color.darker(140)
            inp_bg_color = lighter_color.lighter(150)
            btn_fg_color = '#EAECEE'
            label_fg_color = '#EAECEE'
            inp_fg_color = '#FFFFFF'
            textedit_bg_color = base_color.darker(150)
        else:
            btn_bg_color = base_color.darker(140)
            btn_hover_color = base_color.darker(140)
            inp_bg_color = base_color.lighter(130)
            btn_fg_color = '#4A4A4A'
            label_fg_color = '#4A4A4A'
            inp_fg_color = base_color.darker(180).name()
            textedit_bg_color = base_color.darker(150)
        inp_border_color = darker_color.name()
        return btn_bg_color, btn_hover_color, inp_bg_color, btn_fg_color, label_fg_color, inp_fg_color, inp_border_color, textedit_bg_color
    @staticmethod
    def generate_theme_palette(is_dark):
        base_color, lighter_color, darker_color = ColorGenerator.generate_base_colors(is_dark)
        btn_bg_color, btn_hover_color, inp_bg_color, btn_fg_color, label_fg_color, inp_fg_color, inp_border_color, textedit_bg_color = ColorGenerator.get_widget_colors(
            base_color, lighter_color, darker_color, is_dark
        )
        if is_dark:
            bg = f"qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba({base_color.lighter(500).red()},{base_color.lighter(500).green()},{base_color.lighter(500).blue()},90), stop:0.12 rgba({base_color.lighter(300).red()},{base_color.lighter(300).green()},{base_color.lighter(300).blue()},140), stop:0.25 rgba({base_color.lighter(200).red()},{base_color.lighter(200).green()},{base_color.lighter(200).blue()},180), stop:0.40 rgba({base_color.darker(100).red()},{base_color.darker(100).green()},{base_color.darker(100).blue()},200), stop:0.60 rgba({base_color.darker(200).red()},{base_color.darker(200).green()},{base_color.darker(200).blue()},220), stop:0.80 rgba({base_color.darker(300).red()},{base_color.darker(300).green()},{base_color.darker(300).blue()},240), stop:1 rgba({base_color.darker(400).red()},{base_color.darker(400).green()},{base_color.darker(400).blue()},255))"
        else:
            bg = f"qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba(255,255,255,255), stop:0.12 rgba({base_color.lighter(150).red()},{base_color.lighter(150).green()},{base_color.lighter(150).blue()},252), stop:0.25 rgba({base_color.lighter(120).red()},{base_color.lighter(120).green()},{base_color.lighter(120).blue()},250), stop:0.40 rgba({base_color.lighter(100).red()},{base_color.lighter(100).green()},{base_color.lighter(100).blue()},245), stop:0.60 rgba({base_color.lighter(80).red()},{base_color.lighter(80).green()},{base_color.lighter(80).blue()},240), stop:0.80 rgba({base_color.lighter(60).red()},{base_color.lighter(60).green()},{base_color.lighter(60).blue()},230), stop:1 rgba({base_color.lighter(40).red()},{base_color.lighter(40).green()},{base_color.lighter(40).blue()},210))"
        sidebar_base = base_color.darker(180)
        if is_dark:
            sidebar_gradient = f"qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba({sidebar_base.lighter(150).red()},{sidebar_base.lighter(150).green()},{sidebar_base.lighter(150).blue()},80), stop:0.3 rgba({sidebar_base.lighter(100).red()},{sidebar_base.lighter(100).green()},{sidebar_base.lighter(100).blue()},180), stop:0.6 rgba({sidebar_base.red()},{sidebar_base.green()},{sidebar_base.blue()},230), stop:1 rgba({sidebar_base.darker(150).red()},{sidebar_base.darker(150).green()},{sidebar_base.darker(150).blue()},255))"
        else:
            sidebar_gradient = f"qradialgradient(cx:0.3, cy:0.5, radius:1.1, fx:0.3, fy:0.5, stop:0 rgba({sidebar_base.lighter(120).red()},{sidebar_base.lighter(120).green()},{sidebar_base.lighter(120).blue()},255), stop:0.2 rgba({sidebar_base.lighter(100).red()},{sidebar_base.lighter(100).green()},{sidebar_base.lighter(100).blue()},255), stop:0.45 rgba({sidebar_base.lighter(80).red()},{sidebar_base.lighter(80).green()},{sidebar_base.lighter(80).blue()},255), stop:0.6 rgba({sidebar_base.lighter(60).red()},{sidebar_base.lighter(60).green()},{sidebar_base.lighter(60).blue()},255), stop:0.8 rgba({sidebar_base.lighter(40).red()},{sidebar_base.lighter(40).green()},{sidebar_base.lighter(40).blue()},255), stop:1 rgba({sidebar_base.red()},{sidebar_base.green()},{sidebar_base.blue()},255))"
        return {
            "custom_widget_bg": bg,
            "btn_bg": sidebar_gradient,
            "btn_hover": btn_hover_color.name(),
            "btn_fg": "#FFFFFF",
            "lbl_fg": label_fg_color,
            "inp_bg": inp_bg_color.name(),
            "inp_fg": inp_fg_color,
            "inp_border": inp_border_color,
            "textedit_bg": f"rgba({textedit_bg_color.red()}, {textedit_bg_color.green()}, {textedit_bg_color.blue()}, 0.9)",
            "sidebar_styles": {
                'bg': sidebar_gradient,
                'text_color': '#FFFFFF',
                'hover_color': btn_hover_color.name(),
                'status_color': btn_fg_color,
            }
        } 
