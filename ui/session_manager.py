import os, json, phonenumbers, shutil, traceback, logging
import sys
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QFileDialog, QMessageBox, QToolButton, QFrame, QInputDialog,
    QDialog, QListWidget, QListWidgetItem, QScrollArea,
    QLineEdit, QSizePolicy, QSplitter
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QColor, QPixmap
from ui.session_win import SessionWindow
from ui.sim_manager import SimManagerWindow
from ui.loader import load_config, load_proxy
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)
class StatBlock(QFrame):
    ICONS = {
        'Сессий': '',
        'Спам': '',
        'Без спама': '',
        'Премиум': '',
    }
    GRADIENTS = {
        'Сессий': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f8cff, stop:1 #a6c8ff);',
        'Спам': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff5252, stop:1 #ffb199);',
        'Без спама': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #43e97b, stop:1 #38f9d7);',
        'Премиум': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffe259, stop:1 #ffa751);',
    }
    SHADOWS = {
        'Сессий': '#4f8cff',
        'Спам': '#ff5252',
        'Без спама': '#43e97b',
        'Премиум': '#ffa751',
    }
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        gradient = self.GRADIENTS.get(title, '#fff')
        self.setStyleSheet(f'''
            QFrame {{
                background: {gradient};
                border-radius: 14px;
                padding: 0 6px 0 6px;
                border: 1.5px solid rgba(0,0,0,0.07);
            }}
        ''')
        self.setFixedHeight(120)
        self.setFixedWidth(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.number_label = QLabel("0")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        font = QFont()
        font.setPointSize(48)
        font.setBold(True)
        self.number_label.setFont(font)
        self.number_label.setStyleSheet('color: white; background: transparent; border: none;')
        layout.addWidget(self.number_label, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet('color: #f7f7f7; opacity: 0.85; background: transparent; border: none;')
        layout.addWidget(self.title_label)
    def set_number(self, number):
        self.number_label.setText(str(number))
class FilterDialog(QDialog):
    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(350)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.selected_panel = QFrame()
        self.selected_panel.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        selected_layout = QHBoxLayout(self.selected_panel)
        selected_layout.setSpacing(5)
        self.selected_labels = []
        layout.addWidget(self.selected_panel)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        for item in items:
            list_item = QListWidgetItem()
            item_widget = self.create_item_widget(item)
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)
        scroll = QScrollArea()
        scroll.setWidget(self.list_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        layout.addWidget(scroll)
        
        apply_btn = QPushButton("Применить")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        apply_btn.clicked.connect(self.accept)
        layout.addWidget(apply_btn)
        self.selected_countries = set()
    def create_item_widget(self, item, *args):
        item_widget = QWidget()
        item_widget.setStyleSheet("background-color: transparent;")
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(10)
        flag_code = item['flag']
        flag_path = resource_path(os.path.join("icons", f"{flag_code.lower()}.png"))
        if os.path.exists(flag_path):
            pixmap = QPixmap(flag_path)
            pixmap = pixmap.scaled(12, 12, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            flag_label = QLabel()
            flag_label.setPixmap(pixmap)
            flag_label.setFixedWidth(16)
            item_layout.addWidget(flag_label)
        else:
            flag_label = QLabel(flag_code)
            flag_label.setFixedWidth(30)
            item_layout.addWidget(flag_label)        
        code_label = QLabel(item['code'])
        code_label.setFixedWidth(40)
        code_label.setStyleSheet("color: #666666;")
        item_layout.addWidget(code_label)
        name_label = QLabel(item['name'])
        name_label.setStyleSheet("color: #666666;")
        item_layout.addWidget(name_label)
        item_layout.addStretch()
        count_label = QLabel(str(item['count']))
        count_label.setFixedWidth(40)
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        count_label.setStyleSheet("""
            QLabel {
                margin-right: 10px;
                padding-right: 5px;
                color: #666666;
            }
        """)
        item_layout.addWidget(count_label)
        item_widget.mousePressEvent = lambda e, i=item: self.toggle_country(i)
        item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        item_widget.setToolTip(f"{item['name']} ({item['code']})")
        return item_widget
    def toggle_country(self, item, *args):
        flag = item['flag']
        if flag in self.selected_countries:
            self.selected_countries.remove(flag)
        else:
            self.selected_countries.add(flag)
        self.update_selected_panel()
    def update_selected_panel(self, *args):
        for label in self.selected_labels:
            label.deleteLater()
        self.selected_labels.clear()
        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if not widget:
                continue
            labels = widget.findChildren(QLabel)
            if len(labels) >= 2:
                code = labels[1].text()
                flag_code = code
                if flag_code in self.selected_countries:
                    selected_widget = QWidget()
                    selected_layout = QHBoxLayout(selected_widget)
                    selected_layout.setContentsMargins(3, 3, 3, 3)
                    selected_layout.setSpacing(4)
                    flag_path = resource_path(os.path.join("icons", f"{flag_code.lower()}.png"))
                    if os.path.exists(flag_path):
                        pixmap = QPixmap(flag_path)
                        pixmap = pixmap.scaled(10, 10, Qt.AspectRatioMode.KeepAspectRatio, 
                                             Qt.TransformationMode.SmoothTransformation)
                        flag_label = QLabel()
                        flag_label.setPixmap(pixmap)
                        selected_layout.addWidget(flag_label)
                    code_label = QLabel(f"{code} ✕")
                    code_label.setStyleSheet("color: #666666; font-size: 11px;")
                    selected_layout.addWidget(code_label)
                    selected_widget.setStyleSheet("""
                        QWidget {
                            background-color: #e0e0e0;
                            border-radius: 3px;
                            margin: 2px;
                        }
                    """)
                    selected_widget.mousePressEvent = lambda e, f=flag_code: self.remove_filter(f)
                    selected_widget.setCursor(Qt.CursorShape.PointingHandCursor)
                    self.selected_labels.append(selected_widget)
                    self.selected_panel.layout().addWidget(selected_widget)
        if self.selected_panel.layout().count() > 0:
            self.selected_panel.layout().addStretch()   
    def remove_filter(self, flag):
        self.selected_countries.remove(flag)
        self.update_selected_panel()
    def get_selected_items(self):
        return list(self.selected_countries)
class BooleanFilterDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(300)
        self.setMaximumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.selected_panel = QFrame()
        self.selected_panel.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        selected_layout = QHBoxLayout(self.selected_panel)
        selected_layout.setSpacing(5)
        self.selected_label = None
        layout.addWidget(self.selected_panel)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        for item in ["Все", "Да", "Нет"]:
            list_item = QListWidgetItem()
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked)            
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(10)
            status_label = QLabel(item)
            item_layout.addWidget(status_label) 
            count_label = QLabel("0")
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            item_layout.addWidget(count_label)            
            item_layout.addStretch()
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)
        layout.addWidget(self.list_widget)
        apply_btn = QPushButton("Применить")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        apply_btn.clicked.connect(self.accept)
        layout.addWidget(apply_btn)
        self.list_widget.itemChanged.connect(self.update_selected_panel)
    def update_selected_panel(self, item, *args):
        if self.selected_label:
            self.selected_label.deleteLater()
            self.selected_label = None
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                widget = self.list_widget.itemWidget(item)
                text = widget.findChild(QLabel).text()
                
                label = QLabel(f"{text} ✕")
                label.setStyleSheet("""
                    QLabel {
                        background-color: #e0e0e0;
                        padding: 3px 8px;
                        border-radius: 3px;
                        margin: 2px;
                    }
                """)
                label.mousePressEvent = lambda e, t=text: self.remove_filter(t)
                self.selected_label = label
                self.selected_panel.layout().addWidget(label)
                break        
        if self.selected_panel.layout().count() > 0:
            self.selected_panel.layout().addStretch()
    def remove_filter(self, text, *args):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget.findChild(QLabel).text() == text:
                item.setCheckState(Qt.CheckState.Unchecked)
                break
    def get_value(self, *args):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                return self.list_widget.itemWidget(item).findChild(QLabel).text()
        return "Все"
class SessionManagerWindow(QWidget):
    stats_updated = pyqtSignal(dict)
    def __init__(self, session_folder, parent=None):
        super().__init__(parent)
        self.session_folder = session_folder
        self.main_window = parent
        self.logger = logging.getLogger('SessionManagerWindow')
        self.logger.setLevel(logging.INFO)
        self.config = load_config()
        self.proxy = load_proxy(self.config) if self.config else None
        if parent and hasattr(parent, 'config_changed'):
            self.main_window.config_changed.connect(self.on_config_changed)
        self.filters = {
            'geo': [],
            'spamblock': "Все",
            'premium': "Все"
        }
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_table_dimensions)
        self.setup_ui()
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        self.session_window.folder_updated.connect(self.on_folder_changed)
        self.load_sessions()
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)
    def update_table_dimensions(self, *args, **kwargs):
        if not self.table:
            return
        visible_rows = sum(not self.table.isRowHidden(i) for i in range(self.table.rowCount()))
        row_height = 0
        if self.table.rowCount() > 0:
            first_visible_row_index = -1
            for i in range(self.table.rowCount()):
                if not self.table.isRowHidden(i):
                    first_visible_row_index = i
                    break
            if first_visible_row_index != -1:
                row_height = self.table.rowHeight(first_visible_row_index)
            elif visible_rows == 0 and self.table.rowCount() > 0:
                row_height = self.table.rowHeight(0)
            else:
                row_height = 30
        else:
            row_height = 30
        header_height = self.table.horizontalHeader().height()
        content_actual_height = visible_rows * row_height
        table_final_height = header_height + content_actual_height
        if visible_rows > 0:
            table_final_height += 4
        else:
            table_final_height += 4
        self.table.setFixedHeight(table_final_height)
        self.table_wrapper_widget.setFixedHeight(table_final_height)
        self.table.horizontalScrollBar().setValue(0)
        self.table.verticalScrollBar().setValue(0)
    def setup_ui(self, *args):
        self.session_window = SessionWindow(self.session_folder, parent=self)
        self.session_window.setStyleSheet("""
            QWidget { background-color: transparent; }
            QGroupBox { border: 1px solid #CCCCCC; border-radius: 3px; margin-top: 1em; padding-top: 1em; background-color: transparent; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; margin-left: 5px; }
        """)        
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)        
        left_panel_layout = QVBoxLayout()
        left_panel_layout.setSpacing(0)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        stats_panel = QFrame()
        stats_panel.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        stats_panel.raise_()        
        stats_layout = QHBoxLayout(stats_panel)
        stats_layout.setSpacing(5)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        self.sessions_block = StatBlock("Сессий")
        self.spam_block = StatBlock("Спам")
        self.non_spamblock_block = StatBlock("Без спама")
        self.premium_block = StatBlock("Премиум")        
        stats_layout.addWidget(self.sessions_block)
        stats_layout.addWidget(self.spam_block)
        stats_layout.addWidget(self.non_spamblock_block)
        stats_layout.addWidget(self.premium_block)
        stats_layout.addStretch()
        left_panel_layout.addWidget(stats_panel)
        buttons_panel = QHBoxLayout()
        buttons_panel.setSpacing(5)
        buttons_panel.setContentsMargins(5, 5, 5, 5)
        self.create_folder_btn = QToolButton()
        self.create_folder_btn.setIcon(QIcon(resource_path("icons/papka.png")))
        self.create_folder_btn.setIconSize(QSize(24, 24))
        self.create_folder_btn.setToolTip("Создать новую папку")
        self.create_folder_btn.clicked.connect(self.create_new_folder)
        self.move_sessions_btn = QToolButton()
        self.move_sessions_btn.setIcon(QIcon(resource_path("icons/papka1.png")))
        self.move_sessions_btn.setIconSize(QSize(24, 24))
        self.move_sessions_btn.setToolTip("Переместить выбранные сессии")
        self.move_sessions_btn.clicked.connect(self.move_selected_sessions)
        buttons_panel.addWidget(self.create_folder_btn)
        buttons_panel.addWidget(self.move_sessions_btn)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(self.filter_table)
        self.search_input.setFixedWidth(100)
        buttons_panel.addWidget(self.search_input)        
        buttons_panel.addStretch()    
        left_panel_layout.addLayout(buttons_panel)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent;
            }
            QScrollArea > QWidget > QWidget { 
                background: transparent;
            }
        """)
        
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Select", "#", "Номер", "Гео", "Спамблок", "Окончание спама", "Имя / Фамилия", "Премиум", "Изменить"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.table.cellClicked.connect(self.handle_cell_click)        
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table_wrapper_widget = QWidget()
        self.table_wrapper_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)        
        table_wrapper_layout = QHBoxLayout(self.table_wrapper_widget)
        table_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        table_wrapper_layout.setSpacing(0)
        table_wrapper_layout.addWidget(self.table)
        scroll_area.setWidget(self.table_wrapper_widget)
        left_panel_layout.addWidget(scroll_area)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 81)   # Select
        self.table.setColumnWidth(1, 54)   # #
        self.table.setColumnWidth(2, 216)  # Номер
        self.table.setColumnWidth(3, 108)  # Гео
        self.table.setColumnWidth(4, 135)  # Спамблок
        self.table.setColumnWidth(5, 162)  # Окончание спама
        self.table.setColumnWidth(6, 162)  # Имя / Фамилия
        self.table.setColumnWidth(7, 135)  # Премиум
        self.table.setColumnWidth(8, 162)  # Изменить        
        for col in [3, 4, 6]:
            header_item = self.table.horizontalHeaderItem(col)
            if header_item:
                header_item.setText(header_item.text() + " ▼")
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_click)
        left_panel_wrapper_widget = QWidget()
        left_panel_wrapper_widget.setLayout(left_panel_layout)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel_wrapper_widget)
        splitter.addWidget(self.session_window)
        splitter.setSizes([700, 250])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        main_layout.addWidget(splitter)
    def get_checkbox_for_row(self, row):
        checkbox_widget = self.table.cellWidget(row, 0)
        if checkbox_widget:
            return checkbox_widget.findChild(QCheckBox)
        return None
    def handle_header_click(self, column, *args):
        if column == 0: 
            all_checked = True
            for row in range(self.table.rowCount()):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox and not checkbox.isChecked():
                    all_checked = False
                    break
            for row in range(self.table.rowCount()):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox:
                    checkbox.setChecked(not all_checked)
            self.update_edit_button_state()
            return
        if column == 3:  
            geo_counts = {}
            for row in range(self.table.rowCount()):
                cell_widget = self.table.cellWidget(row, 3)
                if cell_widget:
                    labels = cell_widget.findChildren(QLabel)
                    country_code = ""
                    if len(labels) >= 2:
                        country_code = labels[1].text().strip()
                    if not country_code:
                        phone_item = self.table.item(row, 2)
                        if phone_item:
                            phone = phone_item.text()
                            country_code = self.get_country_from_phone(phone)
                    if country_code:
                        geo_counts[country_code] = geo_counts.get(country_code, 0) + 1
            items = []
            for code, count in geo_counts.items():
                country_name = self.get_country_name(code)
                items.append({
                    'flag': code,
                    'code': code,
                    'name': country_name,
                    'count': count
                })
            dialog = FilterDialog("Фильтр по гео", items, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.filters['geo'] = dialog.get_selected_items()
                self.apply_filters()
        elif column == 4:
            if self.filters['spamblock'] == "Все":
                self.filters['spamblock'] = "Да"
            elif self.filters['spamblock'] == "Да":
                self.filters['spamblock'] = "Нет"
            else:
                self.filters['spamblock'] = "Все"            
            header_item = self.table.horizontalHeaderItem(4)
            if header_item:
                base_text = "Спамблок"
                if self.filters['spamblock'] != "Все":
                    base_text += f" ({self.filters['spamblock']})"
                header_item.setText(base_text + " ▼")
            self.apply_filters()        
        elif column == 6:
            if self.filters['premium'] == "Все":
                self.filters['premium'] = "Да"
            elif self.filters['premium'] == "Да":
                self.filters['premium'] = "Нет"
            else:
                self.filters['premium'] = "Все"
            header_item = self.table.horizontalHeaderItem(6)
            if header_item:
                base_text = "Премиум"
                if self.filters['premium'] != "Все":
                    base_text += f" ({self.filters['premium']})"
                header_item.setText(base_text + " ▼") 
            self.apply_filters()
        else:
            self.table.sortItems(column, Qt.SortOrder.AscendingOrder)
            self.update_row_numbers()
    def get_country_from_phone(self, phone, *args):
        try:
            phone = ''.join(c for c in phone if c.isdigit() or c == '+')
            if not phone.startswith('+'):
                phone = '+' + phone
            parsed_number = phonenumbers.parse(phone)
            if phonenumbers.is_valid_number(parsed_number):
                country_code = phonenumbers.region_code_for_number(parsed_number)
                if country_code:
                    return country_code
            return "XX"
        except Exception as e:
            print(f"Error parsing phone number {phone}: {e}")
            return "XX" 
    def get_flag_label(self, country_code, size=16, show_code=True, *args):
        if not country_code or country_code == "XX":
            country_code = "xx" 
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flag_path = resource_path(os.path.join("icons", f"{country_code.lower()}.png"))
        if os.path.exists(flag_path):
            pixmap = QPixmap(flag_path)
            pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            flag_label = QLabel()
            flag_label.setPixmap(pixmap)
            flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(flag_label)
        if show_code:
            code_label = QLabel(country_code.upper())
            code_label.setStyleSheet("color: #666666; font-size: 10px;")
            code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(code_label)
        return widget
    def get_country_name(self, country_code, *args):
        country_names = {
            'RU': 'Россия', 'US': 'США', 'GB': 'Великобритания', 'DE': 'Германия', 
            'FR': 'Франция', 'IT': 'Италия', 'ES': 'Испания', 'PT': 'Португалия', 
            'NL': 'Нидерланды', 'BE': 'Бельгия', 'CH': 'Швейцария', 'AT': 'Австрия', 
            'SE': 'Швеция', 'NO': 'Норвегия', 'DK': 'Дания', 'FI': 'Финляндия', 
            'PL': 'Польша', 'CZ': 'Чехия', 'SK': 'Словакия', 'HU': 'Венгрия', 
            'RO': 'Румыния', 'BG': 'Болгария', 'GR': 'Греция', 'TR': 'Турция', 
            'UA': 'Украина', 'BY': 'Беларусь', 'KZ': 'Казахстан', 'UZ': 'Узбекистан', 
            'AZ': 'Азербайджан', 'AM': 'Армения', 'GE': 'Грузия', 'MD': 'Молдова', 
            'LV': 'Латвия', 'LT': 'Литва', 'EE': 'Эстония', 'IL': 'Израиль', 
            'SA': 'Саудовская Аравия', 'AE': 'ОАЭ', 'QA': 'Катар', 'KW': 'Кувейт', 
            'BH': 'Бахрейн', 'OM': 'Оман', 'IN': 'Индия', 'PK': 'Пакистан', 
            'BD': 'Бангладеш', 'LK': 'Шри-Ланка', 'NP': 'Непал', 'BT': 'Бутан', 
            'MV': 'Мальдивы', 'CN': 'Китай', 'JP': 'Япония', 'KR': 'Южная Корея', 
            'KP': 'Северная Корея', 'VN': 'Вьетнам', 'TH': 'Таиланд', 'MY': 'Малайзия', 
            'SG': 'Сингапур', 'ID': 'Индонезия', 'PH': 'Филиппины', 'AU': 'Австралия', 
            'NZ': 'Новая Зеландия', 'CA': 'Канада', 'MX': 'Мексика', 'BR': 'Бразилия', 
            'AR': 'Аргентина', 'CL': 'Чили', 'CO': 'Колумбия', 'PE': 'Перу', 
            'VE': 'Венесуэла', 'ZA': 'ЮАР', 'EG': 'Египет', 'MA': 'Марокко', 
            'DZ': 'Алжир', 'TN': 'Тунис', 'LY': 'Ливия', 'SD': 'Судан', 'ET': 'Эфиопия', 
            'KE': 'Кения', 'NG': 'Нигерия', 'GH': 'Гана', 'SN': 'Сенегал', 
            'CI': 'Кот-д\'Ивуар', 'CM': 'Камерун', 'AO': 'Ангола', 'MZ': 'Мозамбик', 
            'TZ': 'Танзания', 'UG': 'Уганда', 'RW': 'Руанда', 'BI': 'Бурунди', 
            'CD': 'ДР Конго', 'CG': 'Республика Конго', 'GA': 'Габон', 
            'GQ': 'Экваториальная Гвинея', 'CF': 'ЦАР', 'TD': 'Чад', 'NE': 'Нигер', 
            'ML': 'Мали', 'BF': 'Буркина-Фасо', 'BJ': 'Бенин', 'TG': 'Того', 
            'GM': 'Гамбия', 'GN': 'Гвинея', 'GW': 'Гвинея-Бисау', 'SL': 'Сьерра-Леоне', 
            'LR': 'Либерия', 'MR': 'Мавритания', 'SO': 'Сомали', 'DJ': 'Джибути', 
            'ER': 'Эритрея', 'SS': 'Южный Судан', 'ZM': 'Замбия', 'ZW': 'Зимбабве', 
            'BW': 'Ботсвана', 'NA': 'Намибия', 'SZ': 'Свазиленд', 'LS': 'Лесото', 
            'MG': 'Мадагаскар', 'KM': 'Коморы', 'MU': 'Маврикий', 'SC': 'Сейшелы', 
            'CV': 'Кабо-Верде', 'ST': 'Сан-Томе и Принсипи',
            'XX': 'Неизвестно'
        }
        return country_names.get(country_code.upper(), country_code.upper())
    def get_country_code_from_flag(self, country_code, *args):
        return country_code
    def filter_rows_by_conditions(self, conditions, *args, **kwargs):
        for row in range(self.table.rowCount()):
            show_row = True
            for cond in conditions:
                if not cond(row):
                    show_row = False
                    break
            self.table.setRowHidden(row, not show_row)
        self.update_row_numbers()
        self.update_table_dimensions()
    def apply_filters(self, *args):
        conditions = []
        if self.filters['geo']:
            def geo_cond(row):
                geo_widget = self.table.cellWidget(row, 3)
                if geo_widget:
                    labels = geo_widget.findChildren(QLabel)
                    country_code = ""
                    if len(labels) >= 2:
                        country_code = labels[1].text().strip()
                    return country_code in self.filters['geo']
                return False
            conditions.append(geo_cond)
        if self.filters['spamblock'] != "Все":
            def spamblock_cond(row):
                spamblock_item = self.table.item(row, 4)
                if spamblock_item:
                    value = "Да" if self.filters['spamblock'] == "Да" else "Нет"
                    return spamblock_item.text() == value
                return False
            conditions.append(spamblock_cond)
        if self.filters['premium'] != "Все":
            def premium_cond(row):
                premium_item = self.table.item(row, 6)
                if premium_item:
                    value = "Да" if self.filters['premium'] == "Да" else "Нет"
                    return premium_item.text() == value
                return False
            conditions.append(premium_cond)
        self.filter_rows_by_conditions(conditions)
    def update_row_numbers(self, *args):
        visible_row = 1
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                number_item = QTableWidgetItem(str(visible_row))
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, number_item)
                visible_row += 1
    def on_folder_changed(self, folders):
        self.load_sessions()
        self.update_stats()
        self.apply_filters()
    def on_sessions_updated(self, valid_sessions):
        if not valid_sessions:
            self.logger.warning("Нет ни одной сессии с корректными API_ID и API_HASH. Операция не будет выполнена.")
            self.move_sessions_btn.setEnabled(False)
        else:
            self.move_sessions_btn.setEnabled(True)
            self.load_sessions()
            self.update_stats()
            self.apply_filters()
    def calculate_stats(self, sessions):
        total_sessions = len(sessions)
        spam_count = sum(1 for s in sessions if s.get('is_spamblocked'))
        non_spamblock_count = total_sessions - spam_count
        premium_count = sum(1 for s in sessions if s.get('is_premium'))
        return {
            'total': total_sessions,
            'spam': spam_count,
            'non_spam': non_spamblock_count,
            'premium': premium_count
        }
    def get_country_info(self, phone, size=16, show_code=True):
        country_code = self.get_country_from_phone(phone)
        country_name = self.get_country_name(country_code)
        flag_widget = self.get_flag_label(country_code, size=size, show_code=show_code)
        return country_code, country_name, flag_widget
    def load_sessions(self, *args):
        self.table.setRowCount(0)
        sessions = []
        selected_sessions = self.session_window.get_selected_sessions()
        self.logger.info(f"Всего выбрано сессий: {len(selected_sessions)}")
        for session_name in selected_sessions:
            try:
                phone = os.path.splitext(os.path.basename(session_name))[0]
                session_file, json_file = self.find_session_and_json_files(phone)
                session_path = session_file if session_file else os.path.join(self.session_window.session_folder, session_name)
                json_path = json_file if json_file else session_path.replace('.session', '.json')
                session_data = {
                    'phone': phone,
                    'is_spamblocked': False,
                    'name': "",
                    'is_premium': False,
                    'spam_count': 0
                }
                if json_file and os.path.exists(json_file):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            session_data.update({
                                'phone': data.get('phone', phone),
                                'spam_count': data.get('spam_count', 0),
                                'is_spamblocked': data.get('spamblock', False),
                                'first_name': data.get('first_name', ''),
                                'last_name': data.get('last_name', ''),
                                'is_premium': data.get('is_premium', False),
                                'spamblock_end_date': data.get('spamblock_end_date'),
                                'spamblock_check_date': data.get('spamblock_check_date'),
                            })
                            spamblock_end_date = data.get('spamblock_end_date')
                            if spamblock_end_date:
                                try:
                                    spamblock_end_date_dt = datetime.fromisoformat(spamblock_end_date)
                                    if datetime.now() < spamblock_end_date_dt:
                                        session_data['is_spamblocked'] = True
                                except Exception:
                                    pass
                    except Exception as e:
                        self.logger.error(f"Ошибка чтения JSON для {phone}: {str(e)}")
                country_code, country_name, flag_widget = self.get_country_info(session_data['phone'])
                session_data.update({
                    'country_code': country_code,
                    'country_name': country_name,
                    'flag_widget': flag_widget,
                    'session_path': session_path,
                    'json_path': json_path,
                    'name': f"{session_data.get('first_name', '')} {session_data.get('last_name', '')}".strip()
                })     
                sessions.append(session_data)
                self.logger.debug(f"Добавлена сессия: {phone} (спамблок: {session_data['is_spamblocked']})")
            except Exception as e:
                self.logger.error(f"Ошибка обработки сессии {session_name}: {str(e)}")
                traceback.print_exc()
        stats = self.calculate_stats(sessions)
        self.sessions_block.set_number(stats['total'])
        self.spam_block.set_number(stats['spam'])
        self.non_spamblock_block.set_number(stats['non_spam'])
        self.premium_block.set_number(stats['premium'])
        self.stats_updated.emit(stats)
        self.table.setRowCount(len(sessions))
        self.logger.info(f"Установлено строк в таблице: {len(sessions)}")
        for i, session in enumerate(sessions):
            try:
                checkbox = QCheckBox()
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                checkbox_widget.setStyleSheet("background-color: transparent;")
                checkbox.stateChanged.connect(self.update_edit_button_state)
                self.table.setCellWidget(i, 0, checkbox_widget)
                number_item = QTableWidgetItem(str(i + 1))
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, number_item)
                phone_item = QTableWidgetItem(session['phone'])
                phone_item.setData(Qt.ItemDataRole.UserRole, session['phone'])
                self.table.setItem(i, 2, phone_item)
                self.table.setCellWidget(i, 3, session['flag_widget'])
                spamblock_item = QTableWidgetItem("Да" if session['is_spamblocked'] else "Нет")
                spamblock_item.setData(Qt.ItemDataRole.UserRole, session['is_spamblocked'])
                spamblock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                spamblock_item.setForeground(QColor(255, 0, 0) if session['is_spamblocked'] else QColor(0, 128, 0))
                self.table.setItem(i, 4, spamblock_item)
                spam_end = ""
                if session['is_spamblocked']:
                    spam_end = session.get('spamblock_end_date') or session.get('spamblock_check_date') or ""
                    if spam_end:
                        try:
                            dt = datetime.fromisoformat(spam_end)
                            spam_end = dt.strftime("%d.%m.%Y")
                        except Exception:
                            pass
                spam_end_item = QTableWidgetItem(spam_end)
                spam_end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 5, spam_end_item)
                self.table.setItem(i, 6, QTableWidgetItem(session['name']))
                premium_item = QTableWidgetItem("Да" if session['is_premium'] else "Нет")
                premium_item.setData(Qt.ItemDataRole.UserRole, session['is_premium'])
                premium_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 7, premium_item)
                edit_btn = QPushButton("Изменить")
                edit_btn.setStyleSheet("""
                    QPushButton {
                        border: none;
                        background: transparent;
                        color: #4CAF50;
                        padding: 2px 5px;
                    }
                    QPushButton:hover {
                        text-decoration: underline;
                    }
                """)
                edit_btn.clicked.connect(lambda checked, row=i: self.open_sim_manager(row))
                self.table.setCellWidget(i, 8, edit_btn)
                self.logger.debug(f"Добавлена строка {i + 1} для сессии {session['phone']}")
            except Exception as e:
                self.logger.error(f"Ошибка добавления строки {i}: {str(e)}")
                traceback.print_exc()
        self.apply_filters()
        self.update_edit_button_state()
        self.table.viewport().update()
        self.update_table_dimensions()
    def update_edit_button_state(self, *args, **kwargs):
        has_selected = False
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox and checkbox.isChecked():
                    has_selected = True
                    break
        if hasattr(self, 'move_sessions_btn'):
            self.move_sessions_btn.setEnabled(has_selected)
    def filter_table(self, text, *args, **kwargs):
        def search_cond(row):
            for col in range(self.table.columnCount() - 1):
                item = self.table.item(row, col)
                if item and text.lower() in item.text().lower():
                    return True
            return False
        self.filter_rows_by_conditions([search_cond])
    def toggle_all_sessions(self, state, *args, **kwargs):
        self.select_all.blockSignals(True)
        for row in range(self.table.rowCount()):
            checkbox_widget = self.table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(state == Qt.CheckState.Checked)
        self.select_all.blockSignals(False)
    def create_new_folder(self, *args, **kwargs):
        folder_name, ok = QInputDialog.getText(
            self, "Создать папку", "Введите название папки:"
        )
        if ok and folder_name:
            try:
                new_folder = os.path.join(self.session_folder, folder_name)
                os.makedirs(new_folder, exist_ok=True)
                QMessageBox.information(
                    self, "Успех", f"Папка {folder_name} успешно создана"
                )
                self.session_window.update_session_folder(self.session_folder)
            except Exception as e:
                QMessageBox.warning(
                    self, "Ошибка", f"Не удалось создать папку: {str(e)}"
                )
    def get_folder_mtime(self, *args, **kwargs):
        pass
    def check_for_updates(self, *args, **kwargs):
        pass
    def move_selected_sessions(self, *args, **kwargs):
        selected_sessions = []
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                checkbox_widget = self.table.cellWidget(row, 0)
                if checkbox_widget:
                    checkbox = checkbox_widget.findChild(QCheckBox)
                    if checkbox and checkbox.isChecked():
                        phone_item = self.table.item(row, 2)
                        if phone_item:
                            selected_sessions.append(phone_item.text())
        if not selected_sessions:
            QMessageBox.warning(self, "Предупреждение", "Выберите сессии для перемещения")
            return
        target_folder = QFileDialog.getExistingDirectory(self, "Выберите папку назначения")
        if not target_folder:
            return
        if not os.access(target_folder, os.W_OK):
            QMessageBox.critical(self, "Ошибка", "Нет прав на запись в выбранную папку")
            return
        try:
            moved_count = 0
            files_to_move = []
            for phone in selected_sessions:
                session_file, json_file = self.find_session_and_json_files(phone)
                if session_file:
                    session_name = os.path.basename(session_file)
                    target_session_path = os.path.join(target_folder, session_name)
                    files_to_move.append((session_file, target_session_path))
                if json_file:
                    json_name = os.path.basename(json_file)
                    target_json_path = os.path.join(target_folder, json_name)
                    files_to_move.append((json_file, target_json_path))
            for source_path, target_path in files_to_move:
                if os.path.exists(source_path):
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    shutil.move(source_path, target_path)
                    moved_count += 0.5
                else:
                    self.logger.warning(f"Файл не найден: {source_path}")
            moved_count = int(moved_count)
            if moved_count > 0:
                QMessageBox.information(
                    self, "Успех", f"Успешно перемещено {moved_count} сессий"
                )
                self.session_window.update_sessions_list()
                self.load_sessions()
            else:
                QMessageBox.warning(
                    self, "Внимание", "Ни один файл не был перемещён"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось переместить сессии:\n{str(e)}"
            )
    def find_session_and_json_files(self, phone):
        session_file = None
        json_file = None
        session_folder = self.session_window.session_folder
        direct_session_path = os.path.join(session_folder, f"{phone}.session")
        direct_json_path = os.path.join(session_folder, f"{phone}.json")        
        if os.path.exists(direct_session_path):
            session_file = direct_session_path 
        if os.path.exists(direct_json_path):
            json_file = direct_json_path
        if not session_file or not json_file:
            clean_phone = ''.join(c for c in phone if c.isdigit())
            for root, _, files in os.walk(session_folder):
                for filename in files:
                    if filename.endswith('.json') and not json_file:
                        current_json_path = os.path.join(root, filename)
                        try:
                            with open(current_json_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                json_phone = data.get('phone', '')
                                json_phone_clean = ''.join(c for c in json_phone if c.isdigit())
                                if json_phone_clean and json_phone_clean.endswith(clean_phone):
                                    json_file = current_json_path
                                    session_file_name = data.get('session_file', os.path.splitext(filename)[0])
                                    potential_session_path = os.path.join(root, f"{session_file_name}.session")
                                    if os.path.exists(potential_session_path):
                                        session_file = potential_session_path
                                        break
                        except Exception:
                            pass
        return session_file, json_file
    def update_stats(self, *args):
        sessions = []
        for session in self.session_window.get_selected_sessions():
            phone = os.path.splitext(os.path.basename(session))[0]
            session_file, json_file = self.find_session_and_json_files(phone)
            json_path = json_file if json_file else os.path.join(self.session_folder, session).replace('.session', '.json')
            is_spamblocked = False
            is_premium = False
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    is_spamblocked = data.get('spamblock', False)
                    is_premium = data.get('is_premium', False)
            except:
                pass
            sessions.append({'is_spamblocked': is_spamblocked, 'is_premium': is_premium})
        stats = self.calculate_stats(sessions)
        self.sessions_block.set_number(stats['total'])
        self.spam_block.set_number(stats['spam'])
        self.non_spamblock_block.set_number(stats['non_spam'])
        self.premium_block.set_number(stats['premium'])
        self.stats_updated.emit(stats)
    def open_sim_manager(self, row=None, *args, **kwargs):
        selected_sessions = []
        if row is not None:
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    checkbox_widget = self.table.cellWidget(r, 0)
                    if checkbox_widget:
                        checkbox = checkbox_widget.findChild(QCheckBox)
                        if checkbox and checkbox.isChecked():
                            phone_item = self.table.item(r, 2)
                            if phone_item:
                                phone = phone_item.text()
                                session_path = self.find_session_file_by_phone(phone)
                                if session_path:
                                    selected_sessions.append(session_path)
            if not selected_sessions:
                phone_item = self.table.item(row, 2)
                if phone_item:
                    phone = phone_item.text()
                    session_path = self.find_session_file_by_phone(phone)
                    if session_path:
                        selected_sessions.append(session_path)
        else:
            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    checkbox_widget = self.table.cellWidget(row, 0)
                    if checkbox_widget:
                        checkbox = checkbox_widget.findChild(QCheckBox)
                        if checkbox and checkbox.isChecked():
                            phone_item = self.table.item(row, 2)
                            if phone_item:
                                phone = phone_item.text()
                                session_path = self.find_session_file_by_phone(phone)
                                if session_path:
                                    selected_sessions.append(session_path)
        if not selected_sessions:
            QMessageBox.warning(self, "Предупреждение", "Выберите сессии для редактирования")
            return
        sim_manager = SimManagerWindow(
            session_folder=self.session_window.session_folder,
            selected_sessions=selected_sessions,
            parent=self
        )
        sim_manager.exec()
    def find_session_file_by_phone(self, phone, *args):
        session_file, _ = self.find_session_and_json_files(phone)
        return session_file
    def on_config_changed(self, config, *args, **kwargs):
        if config is None:
            return
        if 'SESSION_FOLDER' in config:
            self.session_folder = config['SESSION_FOLDER']
            self.session_window.update_session_folder(self.session_folder)
            self.session_window.update_sessions_list() 
            self.load_sessions()
        use_proxy = bool(config.get('PROXY_TYPE'))
        if hasattr(self, 'use_proxy_checkbox'):
            self.use_proxy_checkbox.setChecked(use_proxy)
        self.proxy = load_proxy(config) if config else None
    def handle_cell_click(self, row, col, *args):
        if col == 0:
            return
        checkbox = self.get_checkbox_for_row(row)
        if checkbox:
            checkbox.setChecked(not checkbox.isChecked())
        self.table.selectRow(row)
    def handle_selection_changed(self, *args):
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        for row in range(self.table.rowCount()):
            checkbox = self.get_checkbox_for_row(row)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(row in selected_rows)
                checkbox.blockSignals(False)
        self.update_edit_button_state()
    def closeEvent(self, event, *args, **kwargs):
        self.logger.info("Закрытие окна SessionManagerWindow...")
        self._is_running = False
        if hasattr(self, 'resize_timer'):
            self.resize_timer.stop()        
        super().closeEvent(event)
        self.logger.info("Окно SessionManagerWindow закрыто.")
