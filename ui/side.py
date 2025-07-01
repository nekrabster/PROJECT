import os
import sys
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer, pyqtSignal, QProcess, QThread
from PyQt6.QtGui import QPixmap, QCursor
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QWidget, QSizePolicy, QGraphicsOpacityEffect, QMessageBox, QApplication
)
from ui.session_manager import StatBlock
from ui.styles import StyleManager
from ui.svg_utils import create_svg_icon
from ui.svg_icons import get_svg_icons
import requests
from packaging.version import parse
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), os.pardir, relative_path)
class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str)
    def __init__(self, current_version, *args, **kwargs):
        super().__init__()
        self.current_version = current_version
    def run(self, *args, **kwargs):
        try:
            response = requests.get(
                "https://update.smm-aviator.com/version/update.php",
                timeout=5
            )
            if response.status_code == 200:
                update_info = response.json()
                if "version" in update_info and "update_url" in update_info:
                    latest_version = update_info["version"]
                    update_url = update_info["update_url"]
                    
                    if parse(latest_version) > parse(self.current_version):
                        self.update_available.emit(latest_version, update_url)
        except Exception as e:
            print(f"Ошибка при проверке обновлений: {e}")
class DispatcherLogo(QWidget):
    update_available = pyqtSignal(str, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_version = "2.3.9"
        self.update_url = None
        self.update_checker = None
        self.setup_ui()
        self.setup_update_timer()
    def setup_update_timer(self, *args, **kwargs):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_for_update)
        self.update_timer.start(60000)
        self.check_for_update()        
    def setup_ui(self, *args, **kwargs):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.icon_label = QLabel()
        icon_path = resource_path("icons/dispatcher.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            available_width = 120
            available_height = 120
            scaled_size = min(available_width, available_height) 
            pixmap = pixmap.scaled(
                scaled_size, scaled_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_label.setPixmap(pixmap)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_label.mousePressEvent = self.handle_update_click
        layout.addWidget(self.icon_label)
        self.version_label = QLabel(f"Версия {self.current_version}")
        self.version_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
                padding: 5px;
                background: transparent;
            }
        """)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.mousePressEvent = self.handle_update_click
        layout.addWidget(self.version_label)
    def check_for_update(self, *args, **kwargs):
        if self.update_checker is None:
            self.update_checker = UpdateCheckerThread(self.current_version)
            self.update_checker.update_available.connect(self.on_update_available)
        if not self.update_checker.isRunning():
            self.update_checker.start()            
    def on_update_available(self, latest_version, update_url, *args, **kwargs):
        self.update_url = update_url
        self.show_update_available(latest_version) 
    def show_update_available(self, latest_version, *args, **kwargs):
        self.version_label.setText(f"Доступно обновление {latest_version}")
        self.version_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(59, 130, 246, 0.2);
                border: 1px solid rgba(59, 130, 246, 0.4);
                border-radius: 4px;
                padding: 4px 8px;
                margin: 2px;
            }
            QLabel:hover {
                background-color: rgba(59, 130, 246, 0.3);
                border-color: rgba(59, 130, 246, 0.6);
            }
        """)
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)        
    def handle_update_click(self, event, *args, **kwargs):
        if self.update_url:
            self.download_update()
    def download_update(self, *args, **kwargs):
        import os
        CURRENT_FILE = "Soft-K.exe"
        TEMP_FILE = "Soft-K_temp.exe"
        UPDATER_FILE = "updater.bat"
        try:
            self.version_label.setText("Скачивание...")
            QApplication.processEvents()
            response = requests.get(self.update_url, stream=True)
            if response.status_code == 200:
                with open(TEMP_FILE, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
            else:
                raise Exception(f"Ошибка загрузки: статус {response.status_code}")
            self.version_label.setText("Установка...")
            QApplication.processEvents()
            updater_code = r"""@echo off
            title Обновление программы

            :waitloop
            tasklist | find /i "Soft-K.exe" >nul 2>&1
            if not errorlevel 1 (
                echo Ждем завершения Soft-K.exe...
                taskkill /f /im "Soft-K.exe" >nul 2>&1
                timeout /t 1 >nul
                goto waitloop
            )

            move /Y "Soft-K_temp.exe" "Soft-K.exe" >nul 2>&1
            start "" "Soft-K.exe"
            del "%~f0"
            """
            with open(UPDATER_FILE, "w", encoding="utf-8") as f:
                f.write(updater_code)
            bat_path = os.path.abspath(UPDATER_FILE)
            QProcess.startDetached("cmd.exe", ["/c", bat_path])
            QTimer.singleShot(500, QApplication.quit)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при обновлении:\n{e}")
            self.version_label.setText(f"Версия {self.current_version}")
            self.version_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 0.6);
                    font-size: 11px;
                    padding: 5px;
                    background: transparent;
                }
            """)
class SideBar:
    def __init__(self, main_window):
        self.main_window = main_window
        self.bullet_labels = []
        self._sidebar_sections_widgets = []
    def create_sidebar(self, *args, **kwargs):
        self.sidebar_statblock_styles = StyleManager.get_default_sidebar_styles(getattr(self.main_window, 'is_dark_theme', False))['statblock']
        sidebar = QFrame(self.main_window)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self._add_sidebar_header(layout, sidebar)
        layout.addSpacing(20)
        self._add_main_label(layout)
        layout.addSpacing(8)
        self._add_sidebar_sections(layout, sidebar)
        layout.addStretch(1)
        self._add_sidebar_special_buttons(layout)
        return sidebar
    def _add_sidebar_header(self, layout, sidebar, *args, **kwargs):
        header_container = QFrame()
        header_container.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(header_container)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(0)
        self.dispatcher_logo = DispatcherLogo()
        header_layout.addWidget(self.dispatcher_logo)
        layout.addWidget(header_container)
        bot_stats_container = QWidget()
        bot_stats_container.setObjectName("bot_stats_container")
        bot_stats_container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bot_stats_container.mousePressEvent = lambda event: self.main_window.handle_window_switch('bot_manager')
        bot_stats_layout = QVBoxLayout(bot_stats_container)
        bot_stats_layout.setContentsMargins(10, 5, 10, 5)
        bot_stats_layout.setSpacing(4)
        bot_title = QLabel("Статистика ботов")
        bot_title.setObjectName("bot_stats_title")
        bot_stats_layout.addWidget(bot_title, alignment=Qt.AlignmentFlag.AlignCenter)
        bot_stats_grid = QHBoxLayout()
        bot_stats_grid.setSpacing(4)
        bot_stat_titles = ["Всего", "Активных", "Неактивных"]
        self.sidebar_bot_stat_blocks = []
        for title in bot_stat_titles:
            block = StatBlock(title)
            block.setFixedHeight(28)
            block.setFixedWidth(60)
            current_styles = self.sidebar_statblock_styles
            block.setStyleSheet(current_styles['widget'])
            block.number_label.setText("—")
            block.number_label.setStyleSheet(current_styles['number_label'])
            block.title_label.setStyleSheet(current_styles['title_label'])
            self.sidebar_bot_stat_blocks.append(block)
            bot_stats_grid.addWidget(block)
        bot_stats_layout.addLayout(bot_stats_grid)
        layout.addWidget(bot_stats_container)
        session_stats_container = QWidget()
        session_stats_container.setObjectName("session_stats_container")
        session_stats_container.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        session_stats_container.mousePressEvent = lambda event: self.main_window.handle_window_switch('session_manager')
        session_stats_layout = QVBoxLayout(session_stats_container)
        session_stats_layout.setContentsMargins(10, 5, 10, 5)
        session_stats_layout.setSpacing(4)
        session_title = QLabel("Статистика сессий")
        session_title.setObjectName("session_stats_title")
        session_stats_layout.addWidget(session_title, alignment=Qt.AlignmentFlag.AlignCenter)
        session_stats_grid = QHBoxLayout()
        session_stats_grid.setSpacing(4)
        stat_titles = ["Сессий", "Спам", "Без спама", "Премиум"]
        self.sidebar_stat_blocks = []
        for title in stat_titles:
            block = StatBlock(title)
            block.setFixedHeight(28)
            block.setFixedWidth(60)
            current_styles = self.sidebar_statblock_styles
            block.setStyleSheet(current_styles['widget'])
            block.number_label.setText("—")
            block.number_label.setStyleSheet(current_styles['number_label'])
            block.title_label.setStyleSheet(current_styles['title_label'])
            self.sidebar_stat_blocks.append(block)
            session_stats_grid.addWidget(block)
        session_stats_layout.addLayout(session_stats_grid)
        layout.addWidget(session_stats_container)
    def _add_main_label(self, layout, *args, **kwargs):
        self.main_label = QLabel("Главное")
        self.main_label.setStyleSheet("padding: 4px 8px; font-size: 17px; font-weight: bold; color: #FFFFFF; background: transparent;")
        layout.addWidget(self.main_label)
    def _add_sidebar_sections(self, layout, sidebar, *args, **kwargs):
        svg_icons = get_svg_icons()
        icon_color = "#87CEEB"  
        sections = [
            ("Сессии", create_svg_icon(svg_icons['user'], icon_color), create_svg_icon(svg_icons['arrow_down'], icon_color), [
                ("Создать сессию", "kachok", create_svg_icon(svg_icons['add'], icon_color)),
                ("Менеджер аккаунтов", "session_manager", create_svg_icon(svg_icons['group'], icon_color)),
                ("Бустер/Чекер", "components", create_svg_icon(svg_icons['search'], icon_color)),
                ("Отправка жалоб", "complas", create_svg_icon(svg_icons['edit'], icon_color)),
                ("Накрут/Грев", "subscribe", create_svg_icon(svg_icons['chart'], icon_color)),
                ("Рассылка", "malining", create_svg_icon(svg_icons['send'], icon_color)),
                ("Парсер аудитории", "subs", create_svg_icon(svg_icons['eye'], icon_color)),
            ]),
            ("Боты", create_svg_icon(svg_icons['robot'], icon_color), create_svg_icon(svg_icons['arrow_down'], icon_color), [
                ("Создать ботов", "newtoken", create_svg_icon(svg_icons['add'], icon_color)),
                ("Менеджер ботов", "bot_manager", create_svg_icon(svg_icons['settings'], icon_color)),
                ("Проверка юзеров", "check", create_svg_icon(svg_icons['check'], icon_color)),
                ("Автоответы ботов", "session", create_svg_icon(svg_icons['chat'], icon_color)),
                ("Автоответы ботов (beta)", "sessionbeta", create_svg_icon(svg_icons['chat'], icon_color)),
                ("Рассылка ботов", "rass", create_svg_icon(svg_icons['broadcast'], icon_color)),
            ])
        ]
        single_buttons = [
            ("Поиск", create_svg_icon(svg_icons['search'], icon_color), "search"),
            ("Прокси", create_svg_icon(svg_icons['globe'], icon_color), "samit"),
            ("Мониторинг", create_svg_icon(svg_icons['monitor'], icon_color), "kraken"),
            ("Почта", create_svg_icon(svg_icons['mail'], icon_color), "mail")
        ]
        self._sidebar_sections_widgets = []
        for title, left_icon, right_icon, items in sections:
            header, container = self._build_sidebar_section(title, left_icon, right_icon, items)
            layout.addWidget(header)
            layout.addWidget(container)
        for text, icon, name in single_buttons:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icon)
            btn.setIconSize(QSize(19,19))
            btn.clicked.connect(lambda _, wn=name: self.main_window.handle_window_switch(wn))
            layout.addWidget(btn)
    def _build_sidebar_section(self, title, left_icon, right_icon, items, *args, **kwargs):
        header_btn = QPushButton(title)
        header_btn.setIcon(left_icon)
        header_btn.setIconSize(QSize(19,19))
        header_btn.setFlat(True)
        icon_label = QLabel()
        icon_label.setStyleSheet("background: transparent;")
        icon_pixmap = right_icon.pixmap(QSize(21, 21))
        icon_label.setPixmap(icon_pixmap)
        btn_layout = QHBoxLayout(header_btn)
        btn_layout.setContentsMargins(0,0,0,0)
        btn_layout.setSpacing(0)
        btn_layout.addStretch(1)
        btn_layout.addWidget(icon_label)
        btn_layout.addSpacing(1)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setMaximumHeight(0)
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)
        buttons = []
        for text, name, icon in items:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icon)
            btn.setIconSize(QSize(19,19))
            btn.clicked.connect(lambda _, wn=name: self.main_window.handle_window_switch(wn))
            eff = QGraphicsOpacityEffect(btn)
            btn.setGraphicsEffect(eff)
            eff.setOpacity(0)
            buttons.append((btn, eff))
            c_layout.addWidget(btn)
        anim = QPropertyAnimation(container, b"maximumHeight")
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        def on_clicked():
            total = sum(b.sizeHint().height() for b, _ in buttons)
            current_height = container.maximumHeight()
            if current_height == 0:
                for hdr, cnt, btns, an in self._sidebar_sections_widgets:
                    if cnt is not container and cnt.maximumHeight() > 0:
                        an.setStartValue(cnt.maximumHeight())
                        an.setEndValue(0)
                        an.start()
                        for j, (bb, ee) in enumerate(btns[::-1]):
                            fo = QPropertyAnimation(ee, b"opacity", self.main_window)
                            fo.setDuration(80)
                            fo.setStartValue(1)
                            fo.setEndValue(0)
                            QTimer.singleShot(j * 30, fo.start)
                anim.setStartValue(0)
                anim.setEndValue(total)
                anim.start()
                for i, (bb, ee) in enumerate(buttons):
                    fi = QPropertyAnimation(ee, b"opacity", self.main_window)
                    fi.setDuration(150)
                    fi.setStartValue(0)
                    fi.setEndValue(1)
                    fi.setEasingCurve(QEasingCurve.Type.OutQuad)
                    QTimer.singleShot(i * 50, fi.start)
            else:
                anim.setStartValue(current_height)
                anim.setEndValue(0)
                anim.start()
        header_btn.clicked.connect(on_clicked)
        self._sidebar_sections_widgets.append((header_btn, container, buttons, anim))
        return header_btn, container
    def _add_sidebar_special_buttons(self, layout, *args, **kwargs):
        svg_icons = get_svg_icons()
        icon_color = "#87CEEB"
        instructions_btn = QPushButton("  Информация (Click)")
        instructions_btn.setIcon(create_svg_icon(svg_icons['info'], icon_color))
        instructions_btn.setIconSize(QSize(21, 21))
        sidebar_styles = StyleManager.get_default_sidebar_styles(getattr(self.main_window, 'is_dark_theme', False))
        hover_color = sidebar_styles['hover_color']
        base_text_color = "#FFD700"
        hover_text_color = "#00FFFF"
        instructions_btn_stylesheet = f"""
            QPushButton {{
                text-align:left;
                padding:10px 8px;
                font-size:17px;
                color: {base_text_color};
                font-weight:bold;
                background: transparent;
                border: none;
            }}
            QPushButton:hover {{
                background: {hover_color};
                color: {hover_text_color};
                font-weight: bold;
            }}
        """
        instructions_btn.setStyleSheet(instructions_btn_stylesheet)
        instructions_btn.clicked.connect(lambda: self.main_window.handle_window_switch("informatika"))
        layout.addWidget(instructions_btn)
    def connect_stats_signal(self, *args, **kwargs):
        if hasattr(self.main_window, 'windows') and 'session_manager' in self.main_window.windows:
            session_manager = self.main_window.windows['session_manager']
            session_manager.stats_updated.connect(self.update_sidebar_stats)
        if hasattr(self.main_window, 'windows') and 'bot_manager' in self.main_window.windows:
            bot_manager = self.main_window.windows['bot_manager']
            bot_manager.stats_updated.connect(self.update_sidebar_bot_stats)
    def update_sidebar_stats(self, stats, *args, **kwargs):
        if not stats:
            for block in self.sidebar_stat_blocks:
                block.number_label.setText('—')
        else:
            self.sidebar_stat_blocks[0].number_label.setText(str(stats.get('total', '—')))
            self.sidebar_stat_blocks[1].number_label.setText(str(stats.get('spam', '—')))
            self.sidebar_stat_blocks[2].number_label.setText(str(stats.get('non_spam', '—')))
            self.sidebar_stat_blocks[3].number_label.setText(str(stats.get('premium', '—')))
    def update_sidebar_bot_stats(self, stats, *args, **kwargs):
        if not stats:
            for block in self.sidebar_bot_stat_blocks:
                block.number_label.setText('—')
        else:
            self.sidebar_bot_stat_blocks[0].number_label.setText(str(stats.get('total', '—')))
            self.sidebar_bot_stat_blocks[1].number_label.setText(str(stats.get('active', '—')))
            self.sidebar_bot_stat_blocks[2].number_label.setText(str(stats.get('inactive', '—')))
    def apply_sidebar_style(self, styles=None, *args, **kwargs):
        if styles is None:
            from ui.styles import StyleManager
            styles = StyleManager.get_default_sidebar_styles(getattr(self.main_window, 'is_dark_theme', False))
        if hasattr(self, 'sidebar') and self.sidebar:
            from ui.styles import StyleManager
            self.sidebar.setStyleSheet(StyleManager.get_sidebar_style(styles))
            for lbl in self.bullet_labels:
                lbl.setStyleSheet(f"font-size: 10px; color: {styles['text_color']};")
        statblock_styles = styles.get('statblock')
        if hasattr(self, 'sidebar_stat_blocks') and statblock_styles:
            self.sidebar_statblock_styles = statblock_styles
            for block in self.sidebar_stat_blocks:
                block.setStyleSheet(statblock_styles['widget'])
                block.number_label.setStyleSheet(statblock_styles['number_label'])
                block.title_label.setStyleSheet(statblock_styles['title_label'])
                block.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))    
        if hasattr(self, 'sidebar_bot_stat_blocks') and statblock_styles:
            for block in self.sidebar_bot_stat_blocks:
                block.setStyleSheet(statblock_styles['widget'])
                block.number_label.setStyleSheet(statblock_styles['number_label'])
                block.title_label.setStyleSheet(statblock_styles['title_label'])
                block.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    def update_icons_for_theme(self, *args, **kwargs):
        pass
