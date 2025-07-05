from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QTextBrowser, QGroupBox, QSizePolicy, QPushButton, QScrollArea, QGraphicsDropShadowEffect, QStyle, QApplication, QStackedWidget
)
class AppTile(QWidget):
    clicked = pyqtSignal()
    def __init__(self, icon: QIcon, title: str, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.title = title
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(120, 120)
        self.setMaximumSize(180, 180)
        self.setStyleSheet("")
        self._setup_ui()
        self._setup_shadow()
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(48, 48)
        pixmap = self.icon.pixmap(48, 48)
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)
        title_label = QLabel(self.title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("San Francisco", 13, QFont.Weight.Medium))
        title_label.setStyleSheet("color: palette(window-text);")
        layout.addWidget(title_label)
    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
class TileDetailWidget(QWidget):
    def __init__(self, title, html_content, icon=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setStyleSheet("background: transparent;")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        card = QWidget()
        card.setObjectName("DetailCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 12, 36, 32)
        card_layout.setSpacing(18)
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(48, 48))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(f"<h2>{title}</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: palette(window-text);")
        card_layout.addWidget(title_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_label = QLabel()
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setText(html_content)
        content_label.setWordWrap(True)
        content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_label.setFont(QFont("Segoe UI", 12))
        content_label.setStyleSheet("line-height: 1.6; font-size: 15px; color: palette(window-text);")
        content_layout.addWidget(content_label)
        scroll.setWidget(content_widget)
        card_layout.addWidget(scroll)
        card.setStyleSheet('''
            QWidget#DetailCard {
                background: palette(base);
                border-radius: 22px;
                border: none;
                padding: 0px;
            }
        ''')
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)
        accent = QFrame(card)
        accent.setFixedWidth(5)
        accent.setStyleSheet('background: palette(highlight); border-radius: 3px;')
        card_layout.insertWidget(0, accent)
        outer_layout.addWidget(card)
    def show_near_button(self, btn):
        btn_geom = btn.geometry()
        btn_pos = btn.mapToGlobal(btn_geom.topLeft())
        screen = QApplication.primaryScreen().availableGeometry()
        self.setWindowOpacity(0)
        self.show()
        self.adjustSize()
        my_size = self.size()
        self.hide()
        self.setWindowOpacity(1)
        x = btn_pos.x() + btn_geom.width() // 2 - my_size.width() // 2
        y = btn_pos.y() - my_size.height() - 8
        if y < screen.top() + 8:
            y = btn_pos.y() + btn_geom.height() + 8
        x = max(screen.left() + 8, min(x, screen.right() - my_size.width() - 8))
        self.move(x, y)
        self.show()
class UpdateCard(QWidget):
    def __init__(self, icon: QIcon, title: str, html_content: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        self.setStyleSheet("")
        self._setup_ui(icon, title, html_content)
        self._setup_shadow()
    def _setup_ui(self, icon, title, html_content):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(12)
        if icon:
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(32, 32))
            title_layout.addWidget(icon_label)            
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1976d2;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()        
        content_layout.addWidget(title_widget)
        content_browser = QTextBrowser()
        content_browser.setText(html_content)
        content_browser.setOpenExternalLinks(True)
        content_browser.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                line-height: 1.6;
                font-size: 14px;
                color: palette(window-text);
                margin: 0;
                padding: 0;
            }
            QTextBrowser a {
                color: #1976d2;
                text-decoration: none;
            }
            QTextBrowser a:hover {
                text-decoration: underline;
            }
        """)
        content_browser.setFont(QFont("Segoe UI", 13))
        content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content_layout.addWidget(content_browser)
        content_browser.document().adjustSize()
        doc_height = int(content_browser.document().size().height())
        content_widget.setMinimumHeight(doc_height + 32)
        content_widget.setStyleSheet("""
            QWidget {
                background: palette(base);
                border-radius: 16px;
            }
        """)
        layout.addWidget(content_widget)
    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)
class LaunchpadBar(QWidget):
    def __init__(self, tiles, on_tile_clicked, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(160)
        self.setMaximumHeight(200)
        self.setStyleSheet("")
        self._setup_ui(tiles, on_tile_clicked)
    def _setup_ui(self, tiles, on_tile_clicked):
        layout = QHBoxLayout(self)
        layout.setSpacing(40)
        layout.setContentsMargins(0, 0, 0, 0)
        for tile in tiles:
            app_tile = AppTile(tile["icon"], tile["title"])
            app_tile.clicked.connect(lambda checked=False, t=tile: on_tile_clicked(t))
            layout.addWidget(app_tile)
        layout.addStretch(1)
#class TelegramChatButton(QWidget):
#    def __init__(self, parent=None):
#        super().__init__(parent)
#        self._setup_ui()

#    def _setup_ui(self):
#        layout = QVBoxLayout(self)
#        layout.setContentsMargins(0, 0, 0, 0)
#        layout.setSpacing(8)
#        desc = QLabel("В чате Soft-K — уверенные пользователи софта и разработчик. Присоединяйтесь!")
#        desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
#        desc.setWordWrap(True)
#        desc.setFont(QFont("Segoe UI", 13))
#        desc.setStyleSheet("color: palette(window-text);")
#        layout.addWidget(desc)
        # Кнопка
#        btn = QPushButton("\U0001F4AC  Перейти в Telegram-чат")
#        btn.setCursor(Qt.CursorShape.PointingHandCursor)
#        btn.setFixedHeight(44)
#        btn.setMinimumWidth(220)
#        btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
#        btn.setStyleSheet('''
#            QPushButton {
#                background: palette(highlight);
#                color: palette(highlighted-text);
#                border: none;
#                border-radius: 22px;
#                font-size: 16px;
#                font-weight: bold;
#                padding: 0 32px;
#                letter-spacing: 0.5px;
#            }
#            QPushButton:hover {
#                background: palette(link);
#            }
#        ''')
#        btn.clicked.connect(self.open_telegram)
#        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)

#    def open_telegram(self):
#        QDesktopServices.openUrl(QUrl("https://t.me/+Q46t-EXiM0OGNh"))

class UpdateCarousel(QWidget):
    def __init__(self, updates, parent=None):
        super().__init__(parent)
        self.updates = updates
        self._setup_ui()
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.carousel = QStackedWidget()
        self.carousel.setMinimumHeight(90)
        self.carousel.setMaximumHeight(120)
        for upd in self.updates:
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(12, 8, 12, 8)
            l.setSpacing(12)
            if upd.get("icon"):
                icon_label = QLabel()
                icon_label.setPixmap(upd["icon"].pixmap(36, 36))
                l.addWidget(icon_label)
            if upd.get("img"):
                img_label = QLabel()
                img_label.setPixmap(QPixmap(upd["img"]).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                l.addWidget(img_label)
            text = QLabel(upd["text"])
            text.setWordWrap(True)
            text.setFont(QFont("San Francisco", 11))
            l.addWidget(text, 1)
            self.carousel.addWidget(w)
        # Стрелки
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(6)
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setStyleSheet("border-radius:14px;background:#e3eafc;font-size:16px;")
        prev_btn.clicked.connect(self.prev_update)
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(28, 28)
        next_btn.setStyleSheet("border-radius:14px;background:#e3eafc;font-size:16px;")
        next_btn.clicked.connect(self.next_update)
        nav.addStretch(1)
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        nav.addStretch(1)
        layout.addWidget(self.carousel)
        layout.addLayout(nav)
        self.setStyleSheet('''
            QWidget {
                background: #f7fbff;
                border-radius: 14px;
                border: 1.5px solid #e3eafc;
            }
        ''')
    def prev_update(self):
        idx = self.carousel.currentIndex()
        self.carousel.setCurrentIndex((idx - 1) % self.carousel.count())
    def next_update(self):
        idx = self.carousel.currentIndex()
        self.carousel.setCurrentIndex((idx + 1) % self.carousel.count())
class TopBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        new_look_title = QLabel("Soft-K: Новый взгляд на Telegram")
        new_look_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        new_look_title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        new_look_title.setStyleSheet("""
            color: palette(window-text);
            margin-top: 18px;
            letter-spacing: -0.5px;
        """)
        vbox.addWidget(new_look_title)
        new_look_subtitle = QLabel("Современные инструменты для продвижения, оптимизации и управления аккаунтами и ботами")
        new_look_subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        new_look_subtitle.setFont(QFont("Segoe UI", 13))
        new_look_subtitle.setStyleSheet("""
            color: palette(text);
            margin-bottom: 2px;
            opacity: 0.8;
            letter-spacing: 0.2px;
        """)
        new_look_subtitle.setWordWrap(True)
        vbox.addWidget(new_look_subtitle)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("""
            QFrame {
                border: none;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1976d2, stop:0.5 #2196f3, stop:1 #1976d2);
                height: 2px;
                margin: 8px 0;
            }
        """)
        vbox.addWidget(line)        
        layout.addLayout(vbox, 1)
class InfoWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Soft-K — Главная")
        self.setMinimumSize(900, 700)
        self.setStyleSheet("")
        self.detail_overlay = None
        self._setup_ui()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.detail_overlay:
            self.detail_overlay.setGeometry(0, 0, self.width(), self.height())
            max_card_height = int(self.height() * 0.85)
            self.overlay_card.setMaximumHeight(max_card_height)
            self.overlay_content.setMaximumHeight(int(self.height() * 0.7))
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)
        top_bar = TopBarWidget()
        main_layout.addWidget(top_bar)
        right_menu = QWidget()
        right_menu_layout = QVBoxLayout(right_menu)
        right_menu_layout.setContentsMargins(12, 12, 12, 12)
        right_menu_layout.setSpacing(14)
        menu_buttons = []
        plans_block = QWidget()
        plans_layout = QVBoxLayout(plans_block)
        plans_layout.setContentsMargins(0, 0, 0, 8)
        plans_layout.setSpacing(2)
        plans_title = QLabel("<b>🚀 Планы по Soft-K:</b>")
        plans_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        plans_title.setStyleSheet("color: #1976d2;")
        plans_layout.addWidget(plans_title)
        plans_list = QLabel("""
<ul style='margin:0; padding-left:18px; font-size:13px;'>
<li>В ближайшее время планируем сделать продукт публичным — чтобы как можно больше пользователей смогли протестировать и оценить его возможности.</li>
<li>Готовим реферальную программу с потенциальным доходом до 50% от платежей привлечённых пользователей (подробности — ближе к запуску).</li>
<li>Функциональность софта будет постоянно расширяться, включая новые модули и улучшения текущих функций.</li>
<li>В приоритете — переработка автоответов: цель — перенести их выполнение на серверную часть, чтобы они продолжали работать даже при выключенном приложении (даже без аренды VPS). Сейчас ведётся проектирование и оценка затрат.</li>
</ul>
""")
        plans_list.setTextFormat(Qt.TextFormat.RichText)
        plans_list.setStyleSheet("color: palette(window-text); margin:0; font-size:13px;")
        plans_list.setWordWrap(True)
        plans_layout.addWidget(plans_list)
        right_menu_layout.insertWidget(0, plans_block)
        for tile in [
            {
                "icon": self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),
                "title": "Быстрый старт",
                "detail": "<h4>Пошаговая инструкция:</h4>"
                          "<ol>"
                          "<li>Выберите нужный модуль в меню слева (боты, сессии, рассылки и др.).</li>"
                          "<li>Для корректной работы окна 'Создать сессию', 'Создать бота', необходимо указать параметры <strong>api_id</strong> и <strong>api_hash</strong> в параметрах API - кнопка наверху.</li>"
                          "<li>Если у вас нет этих параметров, получите их на <a href='https://my.telegram.org/auth'>my.telegram.org</a>, 'Delete Account or Manage Apps' в разделе API development tools.</li>"
                          "<li>Далее нужно нажать 'Инструменты разработки API': появится окно 'Создать новое приложение'. Заполните данные нового приложения. Нет необходимости вводить какой-либо URL-адрес, позже можно изменить только первые два поля (название приложения и краткое имя).</li>"
                          "<li>Вы можете нажать на восклицательный знак наверху - поулчить инструкцию для каждого модуля отдельно.</li>"
                          "<li>Для загрузки <strong>своих сессий</strong> создайте папку с любым названием и укажите путь к ней в параметрах SESSION - кнопка наверху.</li>"
                          "<li>Для загрузки <strong>своих ботов</strong> создайте txt-файл, где каждый токен бота указывается с новой строки, и выберите этот файл в соответствующей кнопке сверху.</li>"
                          "<li>Если у вас нет сессий, вы можете их приобрести в формате session+json на площадках, или вручную создать сессию в модуле 'Создать сессию'. Предварительно у вас должен быть зарегистрирован аккаунт в телеграм для получения смс кода.</li>"
                          "<li>Для использования прокси из txt файла, необходимо нажать на флажок 'Использовать прокси из txt' и указать путь к файлу (Каждая прокси в новой строке).</li>"
                          "<li>Для использования единой прокси для всех сессий, необходимо нажать на параметр 'PROXY '- кнопка наверху - в модулях использовать флажок 'Использовать прокси'.</li>"
                          "</ol>"
            },
            {
                "icon": self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView),
                "title": "FAQ и советы",
                "detail": "<ul style='margin-top:5px;'>"
                          "<li>💡 <b>Безопасность:</b> Никогда не передавайте свои api_id, api_hash и сессии третьим лицам...</li>"
                          "<li>🚀 <b>Ускорение работы:</b> Для быстрой загрузки и корректной работы софта убедитель что у вас свободно не меньше 4гб оперативной памяти и скорость интернета больше 25мб/с.</li>"
                          "<li>🔄 <b>Обновления:</b> Следите за новыми версиями — они появляются в окне активаций. Всегда содержат улучшения и исправления.</li>"
                          "<li>❗ <b>Частые ошибки:</b> Если что-то не работает — проверьте api_id, api_hash, интернет и права доступа к папкам, также релевантно не сохранять софт в папке program files, иначе потребуется запуск от имени администратора. Если выходит ошибка или вылет программы, выходит окно с ссылкой на телеграм, ошибка сразу компурется в буфер обмена, просто вставьте ее в личное сообщение..</li>"
                          "<li>⚙️ <b>Окно информации:</b> Параметры API, Прокси и Путь к папке с сессиями задается сверху в кнопках-иконках. Быстро создать текстовый файл и отредактировать его можно в соответствующей кнопке сверху.</li>"
                          "<li>📱 <b>P.S:</b> Софт работает локально на устройстве - для бесперебойной работы и управления с телефона используйте виртуальный сервер</li>"
                          "</ul>"
            },
            {
                "icon": self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton),
                "title": "Возможности",
                "detail": "<ul style='margin-top:5px;'>"
                          "<li>🤖 Нашим софтом вы можете управлять не только сессиями, но и ботами</li>"
                          "<li>⚡ Создавайте ботов быстро и безопасно</li>"
                          "<li>👥 Собирайте базу юзеров и используйте для прогрева модуль автоответов</li>"
                          "<li>📢 Быстрые и безопасные рассылки для множества ботов</li>"
                          "</ul>"
            },
        ]:
            btn = QPushButton(tile["title"])
            btn.setIcon(tile["icon"])
            btn.setIconSize(QSize(24, 24))
            btn.setMinimumHeight(44)
            btn.setStyleSheet('''
                QPushButton {
                    background: transparent;
                    color: palette(window-text);
                    border-radius: 12px;
                    font-size: 15px;
                    font-weight: 500;
                    padding: 8px 18px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: palette(highlight);
                    color: palette(highlighted-text);
                }
            ''')
            btn.clicked.connect(lambda checked=False, t=tile, b=btn: self.show_tile_detail(t, b))
            right_menu_layout.addWidget(btn)
            menu_buttons.append(btn)
        right_menu_layout.addStretch(1)

        right_menu.setFixedWidth(320)
        right_menu.setStyleSheet('''
            QWidget {
                border-left: 1px solid rgba(25, 118, 210, 0.2);
                background: transparent;
                padding-left: 16px;
                padding-right: 16px;
            }
            QPushButton {
                background: transparent;
                color: palette(window-text);
                border-radius: 12px;
                font-size: 15px;
                font-weight: 500;
                padding: 12px 20px;
                text-align: left;
                border: 1px solid transparent;
            }
            QPushButton:hover {
                background: rgba(25, 118, 210, 0.1);
                color: #1976d2;
                border: 1px solid rgba(25, 118, 210, 0.2);
            }
            QPushButton:pressed {
                background: rgba(25, 118, 210, 0.15);
            }
            QLabel {
                color: palette(window-text);
                font-size: 13px;
                line-height: 1.5;
            }
        ''')
        plans_title.setStyleSheet("""
            color: #1976d2;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
            letter-spacing: 0.2px;
        """)        
        plans_list.setStyleSheet("""
            color: palette(window-text);
            margin: 0;
            font-size: 13px;
            line-height: 1.6;
            opacity: 0.9;
        """)
        plans_block_bottom = QWidget()
        plans_layout_bottom = QVBoxLayout(plans_block_bottom)
        plans_layout_bottom.setContentsMargins(0, 16, 0, 0)
        plans_layout_bottom.setSpacing(2)
        plans_title_bottom = QLabel("<b>❤️ Мы учитываем ваше мнение при использовании нашего продукта:</b>")
        plans_title_bottom.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        plans_title_bottom.setStyleSheet("color: #1976d2;")
        plans_title_bottom.setWordWrap(True)
        plans_layout_bottom.addWidget(plans_title_bottom)
        plans_list_bottom = QLabel("""
<ul style='margin:0; padding-left:18px; font-size:13px;'>
  <li>Открыты к предложениям по улучшению и развитию продукта.</li>
  <li>Вы можете предложить свои идеи и пожелания.</li>
  <li>Мы будем рады вашим предложениям.</li>
  <li>Рассмотрим и дадим обратную связь каждому пользователю.</li>
</ul>
""")
        plans_list_bottom.setTextFormat(Qt.TextFormat.RichText)
        plans_list_bottom.setStyleSheet("color: palette(window-text); margin:0; font-size:13px;")
        plans_list_bottom.setWordWrap(True)
        plans_layout_bottom.addWidget(plans_list_bottom)
        right_menu_layout.insertWidget(1, plans_block_bottom)
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(32)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        update_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        update_title = "Обновления"
        update_html = (
            "<b>🚀 Soft-K: Обновление 2.4.0</b><br>"
            "<br>"
            "<span style='color:#1976d2;'>🔥 <strong>Новый функционал в накрутке:</strong> Добавлена возможность греть каналы - подписка + просмотры на 3 поста. Делайте ежедневный нагрев в течение 14 дней для максимальной эффективности.</span><br>"
            "<br>"
            "<span style='color:#e53935;'>🆕 <strong>Серверные рассылки (ранний доступ):</strong> Добавлен экспериментальный модуль серверных рассылок. Внимание: в данный момент ведутся технические работы на сервере, функционал временно недоступен.</span><br>"
            "<br>"
            "<span style='color:#e53935;'>⚠️ <strong>Ограничение:</strong> В серверном бета автоответов рекомендуется использовать не более 2 ботов.</span><br>"
            "<br>"
            "<span style='color:#388e3c;'>✨ <strong>Улучшения:</strong> Значительные улучшения стабильности и производительности во всех модулях приложения.</span><br>"
            "<br>"
            "<span style='color:#388e3c;'>🔧 <strong>Исправления:</strong> Устранены мелкие ошибки и улучшена общая отзывчивость интерфейса.</span><br>"
        )
        update_card = UpdateCard(update_icon, update_title, update_html)
        cards_layout = QVBoxLayout()
        cards_layout.setSpacing(16)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cards_layout.addWidget(update_card)
        main_content_container = QWidget()
        main_content_container.setLayout(cards_layout)
        main_content_layout.addWidget(main_content_container)
        main_content_layout.addWidget(right_menu)
        main_layout.addLayout(main_content_layout)
        main_layout.addStretch(1)
        bottom_buttons_container = QWidget()
        bottom_buttons_layout = QHBoxLayout(bottom_buttons_container)
        bottom_buttons_layout.setContentsMargins(0, 16, 0, 0)
        bottom_buttons_layout.setSpacing(12)
        for btn in menu_buttons:
            bottom_buttons_layout.addWidget(btn)
        bottom_buttons_layout.addStretch(1)
        main_layout.addWidget(bottom_buttons_container)
        self.detail_overlay = QWidget(self)
        self.detail_overlay.hide()
        self.overlay_outer = QVBoxLayout()
        self.overlay_outer.setContentsMargins(0, 0, 0, 0)
        self.overlay_outer.setSpacing(0)
        self.overlay_outer.addStretch(1)
        self.overlay_card = QWidget()
        self.overlay_card.setObjectName("OverlayCard")
        self.overlay_card.setMinimumWidth(420)
        self.overlay_card.setMaximumWidth(600)
        self.overlay_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        overlay_layout = QVBoxLayout(self.overlay_card)
        overlay_layout.setContentsMargins(36, 32, 36, 32)
        overlay_layout.setSpacing(18)
        self.overlay_icon = QLabel()
        self.overlay_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_icon.setFixedSize(48, 48)
        overlay_layout.addWidget(self.overlay_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        self.overlay_title = QLabel()
        self.overlay_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.overlay_title.setStyleSheet("color: palette(window-text);")
        overlay_layout.addWidget(self.overlay_title)
        self.overlay_content = QTextBrowser()
        self.overlay_content.setOpenExternalLinks(True)
        self.overlay_content.setStyleSheet("background: transparent; border: none; font-size: 15px; line-height: 1.6; color: palette(window-text);")
        self.overlay_content.setMinimumHeight(200)
        overlay_layout.addWidget(self.overlay_content)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.hide_detail_overlay)
        close_btn.setFixedWidth(140)
        close_btn.setStyleSheet('''
            QPushButton {
                border-radius: 20px;
                padding: 12px 32px;
                background: rgba(25, 118, 210, 0.1);
                color: #1976d2;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid rgba(25, 118, 210, 0.2);
            }
            QPushButton:hover {
                background: rgba(25, 118, 210, 0.15);
                border: 1px solid rgba(25, 118, 210, 0.3);
            }
            QPushButton:pressed {
                background: rgba(25, 118, 210, 0.2);
            }
        ''')
        overlay_layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        shadow = QGraphicsDropShadowEffect(self.overlay_card)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.overlay_card.setGraphicsEffect(shadow)
        self.overlay_card.setStyleSheet('''
            QWidget#OverlayCard {
                background: palette(base);
                border-radius: 24px;
                border: 1px solid rgba(25, 118, 210, 0.2);
                padding: 0px;
            }
        ''')
        accent = QFrame(self.overlay_card)
        accent.setFixedWidth(4)
        accent.setStyleSheet('''
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #1976d2, stop:1 #2196f3);
            border-radius: 2px;
        ''')
        overlay_layout.insertWidget(0, accent)
        self.overlay_title.setStyleSheet("""
            color: #1976d2;
            font-size: 20px;
            font-weight: bold;
            letter-spacing: -0.5px;
            margin: 8px 0;
        """)
        
        self.overlay_content.setStyleSheet("""
            QTextBrowser {
                background: transparent;
                border: none;
                font-size: 14px;
                line-height: 1.6;
                color: palette(window-text);
                padding: 0;
            }
            QTextBrowser a {
                color: #1976d2;
                text-decoration: none;
            }
            QTextBrowser a:hover {
                text-decoration: underline;
            }
        """)
        
        close_btn.setStyleSheet('''
            QPushButton {
                border-radius: 20px;
                padding: 12px 32px;
                background: rgba(25, 118, 210, 0.1);
                color: #1976d2;
                font-weight: bold;
                font-size: 14px;
                border: 1px solid rgba(25, 118, 210, 0.2);
            }
            QPushButton:hover {
                background: rgba(25, 118, 210, 0.15);
                border: 1px solid rgba(25, 118, 210, 0.3);
            }
            QPushButton:pressed {
                background: rgba(25, 118, 210, 0.2);
            }
        ''')
        self.overlay_outer.addWidget(self.overlay_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.overlay_outer.addStretch(1)
        self.detail_overlay.setLayout(self.overlay_outer)
        self.detail_overlay.raise_()
        self.detail_overlay.setGeometry(0, 0, self.width(), self.height())
    def show_tile_detail(self, tile, btn=None):
        self.overlay_icon.setPixmap(tile["icon"].pixmap(48, 48))
        self.overlay_title.setText(f"<h2>{tile['title']}</h2>")
        self.overlay_content.setHtml(tile["detail"])
        overlay_layout = self.overlay_card.layout()
        if overlay_layout:
            overlay_layout.setContentsMargins(36, 12, 36, 32)        
        if btn is not None:
            btn_pos = btn.mapToGlobal(btn.rect().topLeft())
            screen = QApplication.primaryScreen().availableGeometry()            
            card_x = btn_pos.x() + btn.width()//2 - self.overlay_card.width()//2
            card_y = btn_pos.y() - self.overlay_card.height() - 10            
            if card_y < screen.top():
                card_y = btn_pos.y() + btn.height() + 10                
            card_x = max(screen.left() + 10, min(card_x, screen.right() - self.overlay_card.width() - 10))
            self.overlay_card.move(card_x, card_y)
        self.detail_overlay.setGeometry(0, 0, self.width(), self.height())
        self.detail_overlay.show()
        self.detail_overlay.raise_()
    def hide_detail_overlay(self):
        self.detail_overlay.hide()
    def create_info_card(self, title, content, icon="", accent_color="#1976d2"):
        card = QGroupBox()
        card_layout = QVBoxLayout(card)        
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)        
        if icon:
            icon_label = QLabel(icon)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet(f"""
                font-size: 22px;
                color: {accent_color};
                margin-right: 5px;
            """)
            header_layout.addWidget(icon_label)        
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setFont(self.get_font(1.0, True))
        title_label.setStyleSheet(f"color: {accent_color};")        
        header_layout.addWidget(title_label)
        header_layout.addStretch()        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("color: #212121; padding: 5px;")
        content_label.setFont(self.get_font(0.85))        
        card_layout.addWidget(header)
        card_layout.addWidget(content_label)        
        card.setStyleSheet(f"""
            QGroupBox {{
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid {accent_color};
                border-radius: 10px;
                padding: 12px;
                margin-top: 15px;
            }}
        """)        
        return card
    def create_fancy_divider(self):
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("""
            QFrame {
                border: none;
                background-color: #bbdefb;
                height: 2px;
                margin: 5px 0px;
            }
        """)
        return divider
    def create_text_browser(self, html_content, size_multiplier):
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        text_browser.setHtml(html_content)
        text_browser.setMinimumHeight(150)
        text_browser.setFont(self.get_font(size_multiplier))
        text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(255, 255, 255, 0.7);
                border-radius: 10px;
                border: 1px solid #bbdefb;
                padding: 5px;
            }
        """)
        return text_browser
    def create_label(self, html_content, size_multiplier, is_centered=False):
        label = QLabel(html_content)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter if is_centered else Qt.AlignmentFlag.AlignLeft)
        label.setWordWrap(True)
        label.setFont(self.get_font(size_multiplier))
        return label
    def get_font(self, size_multiplier, is_bold=False):
        font = QFont("Segoe UI", int(11 * size_multiplier))
        font.setBold(is_bold)
        return font
