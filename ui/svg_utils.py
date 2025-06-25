from PyQt6.QtGui import QIcon, QPixmap
from .svg_icons import get_svg_icons, get_icon_color
def create_svg_icon(svg_content, color="#87CEEB"):
    svg_data = svg_content.replace("currentColor", color).encode('utf-8')
    pixmap = QPixmap()
    pixmap.loadFromData(svg_data, "SVG")
    return QIcon(pixmap)
def get_themed_icon(icon_name, is_dark_theme=True):
    svg_icons = get_svg_icons()
    color = get_icon_color(is_dark_theme)
    if icon_name in svg_icons:
        return create_svg_icon(svg_icons[icon_name], color)
    return QIcon() 