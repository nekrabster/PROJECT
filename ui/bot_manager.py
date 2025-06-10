import logging
from typing import Dict, List, Set, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QSizePolicy, QScrollArea, QPushButton,
    QHBoxLayout, QLabel, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QSplitter,
    QApplication, QLineEdit, QMenu, QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from ui.bots_win import BotTokenWindow
from ui.bombardo import BotManagerDialog
from ui.bot_transfer import BotTransferDialog
class StatBlock(QFrame):
    ICONS = {
        'Всего': '',
        'Активных': '',
        'Неактивных': '',
    }
    GRADIENTS = {
        'Всего': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f8cff, stop:1 #a6c8ff);',
        'Активных': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #43e97b, stop:1 #38f9d7);',
        'Неактивных': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff5252, stop:1 #ffb199);',
    }
    SHADOWS = {
        'Всего': '#4f8cff',
        'Активных': '#43e97b',
        'Неактивных': '#ff5252',
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
    def set_number(self, number, *args, **kwargs):
        try:
            self.number_label.setText(str(number))
            self.number_label.repaint()
            logging.getLogger('BotManagerWindow').info(f"Обновлен блок {self.title}: {number}")
        except Exception as e:
            logging.getLogger('BotManagerWindow').error(f"Ошибка обновления блока {self.title}: {e}")
class BotManagerWindow(QWidget):
    stats_updated = pyqtSignal(dict)
    def __init__(self, token_folder, parent=None):
        super().__init__(parent)
        self.token_folder = token_folder
        self.main_window = parent
        self._is_running = True
        self.logger = logging.getLogger('BotManagerWindow')
        self.logger.setLevel(logging.INFO)
        self.filters = {
            'active': "Все",
            'description': "Все"
        }
        self.all_bots_data: Dict[str, Dict[str, Any]] = {}
        self.current_display_tokens: List[str] = []
        self.total_bots = 0 
        self.loaded_bots_count_for_current_fetch_batch = 0
        self.current_batch_total_to_fetch = 0  
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_table_update)
        self._pending_token_updates_for_ui = set()
        self._ui_update_batch_timer = QTimer(self)
        self._ui_update_batch_timer.setSingleShot(True)
        self._ui_update_batch_timer.setInterval(100) 
        self._ui_update_batch_timer.timeout.connect(self._process_batched_ui_updates)
        self._batch_size = 50
        self._current_batch = []
        self.setup_ui()
        self.bot_token_window.tokens_updated.connect(self.on_tokens_updated)
        self.bot_token_window.files_updated.connect(self.on_folder_changed)
        self.bot_token_window.bot_details_updated.connect(self._on_bot_details_updated)
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_table_dimensions)        
        QTimer.singleShot(100, self.initial_load_sequence)
    def _delayed_table_update(self, *args, **kwargs):
        self.populate_table_with_selected_tokens()
        self.update_stats_for_selected_tokens()
    def _process_batched_ui_updates(self):
        if not self._pending_token_updates_for_ui:
            return        
        self.logger.debug(f"Processing batched UI updates for {len(self._pending_token_updates_for_ui)} tokens.")
        for token_to_update in list(self._pending_token_updates_for_ui): # Iterate over a copy
            if token_to_update in self.current_display_tokens and token_to_update in self.all_bots_data:
                row_index = -1
                for i in range(self.table.rowCount()):
                    token_item_in_row = self.table.item(i, 4) 
                    if token_item_in_row and token_item_in_row.text() == token_to_update:
                        row_index = i
                        break
                if row_index != -1:
                    bot_info = self.all_bots_data[token_to_update]
                    username_val = bot_info.get('username', 'Загрузка...') 
                    bot_name_val = bot_info.get('name', username_val)
                    has_error_val = bot_info.get('has_error', True)
                    name_item = self.create_table_item(bot_name_val, has_error_val)
                    self.table.setItem(row_index, 2, name_item)
                    username_item = self.create_table_item(username_val, has_error_val)
                    self.table.setItem(row_index, 3, username_item)
        self._pending_token_updates_for_ui.clear()
        self.update_stats_for_selected_tokens()
        self.update_table_dimensions()
        self.table.viewport().update()
    def resizeEvent(self, event, *args, **kwargs):
        super().resizeEvent(event)
        self.resize_timer.start(100)
    def setup_ui(self, *args):
        self.bot_token_window = BotTokenWindow(token_folder_path=self.parent().bot_token_folder if self.parent() else self.token_folder)        
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)        
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
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
        self.total_block = StatBlock("Всего")
        self.active_block = StatBlock("Активных")
        self.inactive_block = StatBlock("Неактивных")
        stats_layout.addWidget(self.total_block)
        stats_layout.addWidget(self.active_block)
        stats_layout.addWidget(self.inactive_block)
        stats_layout.addStretch()
        left_panel_layout.addWidget(stats_panel)
        buttons_panel = QHBoxLayout()
        buttons_panel.setSpacing(5)
        buttons_panel.setContentsMargins(5, 5, 5, 5)
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
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Select", "#", "Имя бота", "Username", "Токен", "Действия"
        ])
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 81)   # Select
        self.table.setColumnWidth(1, 54)   # #
        self.table.setColumnWidth(2, 216)  # Имя бота
        self.table.setColumnWidth(3, 150)  # Username
        self.table.setColumnWidth(4, 500)  # Токен
        self.table.setColumnWidth(5, 162)  # Действия
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.table.cellClicked.connect(self.handle_cell_click)
        self.table_wrapper_widget = QWidget()
        self.table_wrapper_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_wrapper_layout = QHBoxLayout(self.table_wrapper_widget)
        table_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        table_wrapper_layout.setSpacing(0)
        table_wrapper_layout.addWidget(self.table)
        scroll_area.setWidget(self.table_wrapper_widget)
        left_panel_layout.addWidget(scroll_area)
        left_panel_wrapper_widget = QWidget()
        left_panel_wrapper_widget.setLayout(left_panel_layout)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel_wrapper_widget)
        splitter.addWidget(self.bot_token_window)
        splitter.setSizes([700, 250])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        main_layout.addWidget(splitter)
    def get_checkbox_for_row(self, row, *args, **kwargs):
        checkbox_widget = self.table.cellWidget(row, 0)
        if checkbox_widget:
            return checkbox_widget.findChild(QCheckBox)
        return None
    def handle_header_click(self, column, *args, **kwargs):
        if column == 0: 
            all_checked = True
            for row in range(self.table.rowCount()):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox and not checkbox.isChecked():
                    all_checked = False
                    break
            try:
                self.table.itemSelectionChanged.disconnect(self.handle_selection_changed)
            except Exception:
                pass
            self._checkbox_states = [self.get_checkbox_for_row(row).isChecked() if self.get_checkbox_for_row(row) else False for row in range(self.table.rowCount())]
            for row in range(self.table.rowCount()):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox:
                    checkbox.setChecked(not all_checked)
            self.table.itemSelectionChanged.connect(self.handle_selection_changed)
            self.update_edit_button_state()
            return
        self.table.sortItems(column, Qt.SortOrder.AscendingOrder)
        self.update_row_numbers()
    def update_row_numbers(self, *args, **kwargs):
        visible_row = 1
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                number_item = QTableWidgetItem(str(visible_row))
                number_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 1, number_item)
                visible_row += 1
    def filter_table(self, text, *args, **kwargs):
        def search_cond(row):
            for col in range(self.table.columnCount() - 1):
                item = self.table.item(row, col)
                if item and text.lower() in item.text().lower():
                    return True
            return False
        self.filter_rows_by_conditions([search_cond])
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
    def calculate_stats(self, display_tokens: List[str] = None, *args, **kwargs):
        if display_tokens is None:
            target_tokens = self.current_display_tokens if self.current_display_tokens else list(self.all_bots_data.keys())
        else:
            target_tokens = display_tokens
        total_bots = len(target_tokens)
        active_count = 0
        inactive_count = 0
        self.logger.info(f"Подсчет статистики для {total_bots} ботов из target_tokens")
        for token in target_tokens:
            bot_data = self.all_bots_data.get(token)            
            username = None
            name = None
            is_active = False
            log_reason = "данные отсутствуют"
            if bot_data:
                username = bot_data.get('username')
                name = bot_data.get('name')
                if not bot_data.get('has_error', True):
                    is_active = True
                log_reason = f"username: {username}, name: {name}, has_error: {bot_data.get('has_error')}"
            else:
                username_btw = self.bot_token_window.token_usernames.get(token)
                name_btw = self.bot_token_window.token_names.get(token, username_btw)
                if username_btw and not('Ошибка' in str(username_btw) or username_btw == 'Недоступен' or username_btw == 'Загрузка...'):
                    is_active = True
                log_reason = f"данные из BotTokenWindow: username: {username_btw}, name: {name_btw}"
            if is_active:
                active_count += 1
                self.logger.debug(f"Активный бот: {token} ({log_reason})")
            else:
                inactive_count += 1
                self.logger.debug(f"Неактивный бот: {token} ({log_reason})")
        stats = {
            'total': total_bots,
            'active': active_count,
            'inactive': inactive_count
        }
        self.logger.info(f"Статистика: всего={total_bots}, активных={active_count}, неактивных={inactive_count}")
        QTimer.singleShot(0, lambda: self._update_stat_blocks(stats))
        return stats
    def _update_stat_blocks(self, stats, *args, **kwargs):
        try:
            if not self.total_block or not self.active_block or not self.inactive_block:
                self.logger.warning("Блоки статистики не инициализированы")
                return                
            self.total_block.set_number(stats['total'])
            self.active_block.set_number(stats['active'])
            self.inactive_block.set_number(stats['inactive'])
            self.logger.info("Блоки статистики обновлены")
        except Exception as e:
            self.logger.error(f"Ошибка обновления блоков статистики: {e}")
    def on_bot_info_loaded(self, *args, **kwargs):
        self.logger.info("Информация о ботах загружена, обновляем таблицу")
        self.initial_load_sequence()
    def refresh_table_ui(self, *args, **kwargs):
        if self.table:
            self.table.viewport().update()
            self.table.update()
            QApplication.processEvents()
    def initial_load_sequence(self, *args, **kwargs):
        self.logger.info("Initial load: Triggering BotTokenWindow refresh.")
        if self.bot_token_window:
             self.bot_token_window.refresh_tokens()
    def _update_table_row(self, row: int, bot_info: Dict[str, Any], *args, **kwargs):
        token = bot_info.get('token')
        if not token:
            self.logger.warning(f"Attempted to update row {row} without token in bot_info.")
            return
        username = bot_info.get('username', 'Загрузка...') 
        bot_name = bot_info.get('name', username)
        has_error = bot_info.get('has_error', True)
        name_item = self.create_table_item(bot_name, has_error)
        self.table.setItem(row, 2, name_item)
        username_item = self.create_table_item(username, has_error)
        self.table.setItem(row, 3, username_item)        
        token_item = self.table.item(row, 4)
        if token_item:
            if token_item.text() != token:
                token_item.setText(token)
        else:
            token_item = self.create_table_item(token)
            self.table.setItem(row, 4, token_item)
        self.table.viewport().update()
        self.logger.debug(f"Row {row} updated in table for token ...{token[-6:]}. Name: {bot_name}, User: {username}")
        self._pending_token_updates_for_ui.add(token)
        if not self._ui_update_batch_timer.isActive():
            self._ui_update_batch_timer.start()
    def populate_table_with_selected_tokens(self, *args, **kwargs):
        self.logger.info(f"Populating table with {len(self.current_display_tokens)} display tokens.")
        self.table.setUpdatesEnabled(False)
        self.table.clearSelection()
        try:
            self.table.setRowCount(0)            
            if not self.current_display_tokens:
                self.logger.info("No tokens to display in table.")
                self.table.setUpdatesEnabled(True)
                self.update_row_numbers()
                self.update_edit_button_state()
                self.update_table_dimensions()
                self.apply_filters()
                self.update_stats_for_selected_tokens()
                return                
            self.table.setRowCount(len(self.current_display_tokens))
            self.logger.debug(f"Table row count set to {len(self.current_display_tokens)}.")            
            for i, token_str in enumerate(self.current_display_tokens):
                checkbox = QCheckBox()
                checkbox.stateChanged.connect(self.update_edit_button_state)
                checkbox_widget = QWidget()
                layout = QHBoxLayout(checkbox_widget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(checkbox)
                self.table.setCellWidget(i, 0, checkbox_widget)
                num_item = QTableWidgetItem(str(i + 1))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, num_item)
                bot_data = self.all_bots_data.get(token_str)
                name_to_display = "Загрузка..."
                username_to_display = "Загрузка..."
                is_error_initial = True
                if bot_data:
                    name_to_display = bot_data.get('name', username_to_display)
                    username_to_display = bot_data.get('username', "N/A")
                    is_error_initial = bot_data.get('has_error', True)
                name_item = self.create_table_item(name_to_display, is_error_initial)
                self.table.setItem(i, 2, name_item)                
                username_item = self.create_table_item(username_to_display, is_error_initial)
                self.table.setItem(i, 3, username_item)                
                token_item = self.create_table_item(token_str)
                self.table.setItem(i, 4, token_item)                
                # Действия в одной колонке
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                actions_layout.setSpacing(8)
                edit_btn = QPushButton("Изменить")
                edit_btn.setStyleSheet("QPushButton { border: none; background: transparent; color: #4CAF50; padding: 2px 5px; } QPushButton:hover { text-decoration: underline; }")
                edit_btn.clicked.connect(lambda checked, r=i, t=token_str: self.open_bot_manager(r, t))
                actions_layout.addWidget(edit_btn)
                transfer_btn = QPushButton("Трансфер")
                transfer_btn.setStyleSheet("QPushButton { border: none; background: transparent; color: #FF9800; padding: 2px 5px; } QPushButton:hover { text-decoration: underline; }")
                transfer_btn.clicked.connect(lambda checked, r=i, t=token_str: self.open_bot_transfer(r, t))
                actions_layout.addWidget(transfer_btn)
                del_btn = QPushButton("Удалить")
                del_btn.setStyleSheet("QPushButton { border: none; background: transparent; color: #FF4444; padding: 2px 5px; } QPushButton:hover { text-decoration: underline; }")
                del_btn.clicked.connect(lambda checked, r=i, t=token_str: self.on_delete_token(r, t))
                actions_layout.addWidget(del_btn)
                actions_layout.addStretch()
                self.table.setCellWidget(i, 5, actions_widget)
                self.logger.debug(f"Row {i} created for token ...{token_str[-6:]}")            
        finally:
            self.table.setUpdatesEnabled(True)
            self.update_row_numbers()
            self.update_edit_button_state()
            self.update_table_dimensions()
            self.apply_filters()
        self.logger.info("Table population finished.")
    def _setup_action_buttons(self, row, token_str):
        pass
    def update_stats_for_selected_tokens(self, *args, **kwargs):
        self.logger.debug(f"Updating stats for {len(self.current_display_tokens)} currently displayed tokens.")
        if not self.current_display_tokens:
            self.logger.debug("No tokens to display, using all known tokens for stats")
            stats = self.calculate_stats()
        else:
            stats = self.calculate_stats(self.current_display_tokens)
        self.stats_updated.emit(stats)
    def on_tokens_updated(self, selected_tokens: List[str], is_initial_call=False, *args, **kwargs):
        self.logger.info(f"Signal on_tokens_updated received. Selected tokens count: {len(selected_tokens)}. Initial: {is_initial_call}")
        if not hasattr(self, 'current_display_tokens') or set(self.current_display_tokens) != set(selected_tokens):
            self.current_display_tokens = sorted(list(selected_tokens))
            self.logger.info(f"current_display_tokens updated to {len(self.current_display_tokens)} tokens. Triggering table populate.")            
            self.populate_table_with_selected_tokens()
        else:
            self.logger.info("current_display_tokens is the same as selected_tokens. No full table populate needed unless forced.")
        self.update_stats_for_selected_tokens() 
    def on_folder_changed(self, files: List[str]):
        self.logger.info(f"Token files changed. Data will be updated via bot_details_updated signal.")
        QTimer.singleShot(0, lambda: self.populate_table_with_selected_tokens()) 
        self.update_stats_for_selected_tokens()
    def handle_cell_click(self, row, col, *args, **kwargs):
        if col == 0:
            return
        checkbox = self.get_checkbox_for_row(row)
        if checkbox:
            checkbox.setChecked(not checkbox.isChecked())
        self.table.selectRow(row)
    def handle_selection_changed(self, *args, **kwargs):
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        for row in range(self.table.rowCount()):
            checkbox = self.get_checkbox_for_row(row)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(row in selected_rows)
                checkbox.blockSignals(False)
        self.update_edit_button_state()
    def apply_filters(self, *args, **kwargs):
        conditions = []
        if self.filters['active'] != "Все":
            def active_cond(row):
                name_item = self.table.item(row, 2)
                if name_item:
                    return "Ошибка" not in name_item.text() if self.filters['active'] == "Да" else "Ошибка" in name_item.text()
                return False
            conditions.append(active_cond)
        self.filter_rows_by_conditions(conditions)
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
    def update_edit_button_state(self, *args, **kwargs):
        has_selected = False
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox and checkbox.isChecked():
                    has_selected = True
                    break
    def open_bot_manager(self, row=None, token_str=None, *args, **kwargs):
        selected_tokens = []
        if row is not None:
            has_checked = False
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    checkbox = self.get_checkbox_for_row(r)
                    if checkbox and checkbox.isChecked():
                        has_checked = True
                        break            
            if not has_checked:
                token = self.table.item(row, 4).text()
                selected_tokens.append(token)
            else:
                for r in range(self.table.rowCount()):
                    if not self.table.isRowHidden(r):
                        checkbox = self.get_checkbox_for_row(r)
                        if checkbox and checkbox.isChecked():
                            token = self.table.item(r, 4).text()
                            selected_tokens.append(token)
        else:
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    checkbox = self.get_checkbox_for_row(r)
                    if checkbox and checkbox.isChecked():
                        token = self.table.item(r, 4).text()
                        selected_tokens.append(token)
        if not selected_tokens:
            QMessageBox.warning(self, "Предупреждение", "Выберите ботов для редактирования")
            return
        try:
            dialog = BotManagerDialog(selected_sessions=selected_tokens, parent=self)
            dialog.bot_updated.connect(self.update_bot_data)
            dialog.exec()
            QTimer.singleShot(1000, self.bot_token_window.refresh_tokens)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно редактирования:\n{str(e)}") 
    def delete_token_from_file(self, token: str, *args, **kwargs) -> bool:
        try:
            file_path = self.bot_token_window.token_to_file_map.get(token)
            if not file_path:
                self.logger.error(f"Не найден файл для токена {token}")
                return False
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            new_lines = [line for line in lines if line.strip() != token]
            if len(lines) == len(new_lines):
                self.logger.warning(f"Токен {token} не найден в файле {file_path}")
                return False
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            self.logger.info(f"Токен {token} успешно удален из файла {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при удалении токена {token}: {e}")
            return False
    def get_selected_bots(self, *args, **kwargs):
        selected_bots = []
        for row in range(self.table.rowCount()):
            checkbox = self.get_checkbox_for_row(row)
            if checkbox and checkbox.isChecked():
                token = self.table.item(row, 4).text()
                username = self.table.item(row, 3).text()
                selected_bots.append((token, username, row))
        return selected_bots
    def on_delete_token(self, clicked_row: int, token_str: str, *args, **kwargs):
        try:
            selected_bots = self.get_selected_bots()            
            if not selected_bots:
                token = self.table.item(clicked_row, 4).text()
                username = self.table.item(clicked_row, 3).text()
                selected_bots = [(token, username, clicked_row)]            
            if not selected_bots:
                QMessageBox.warning(self, "Предупреждение", "Не выбрано ни одного бота для удаления")
                return                
            bots_text = "\n".join([f"@{username}" for _, username, _ in selected_bots])
            count_text = f"{'бота' if len(selected_bots) == 1 else 'ботов'}"            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Подтверждение удаления")
            msg.setText(f"Вы действительно хотите удалить следующих {count_text}?\n\n{bots_text}")
            msg.setInformativeText("Это действие нельзя будет отменить.")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                success_count = 0
                error_count = 0                
                for token, _, _ in selected_bots:
                    if self.delete_token_from_file(token):
                        success_count += 1
                    else:
                        error_count += 1                
                self.bot_token_window.refresh_tokens()
                if success_count > 0 and error_count == 0:
                    QMessageBox.information(self, "Успех", 
                        f"Успешно удалено {success_count} {count_text}")
                elif success_count > 0 and error_count > 0:
                    QMessageBox.warning(self, "Частичный успех", 
                        f"Удалено {success_count} {count_text}, но {error_count} не удалось удалить")
                else:
                    QMessageBox.critical(self, "Ошибка", 
                        "Не удалось удалить выбранных ботов")        
        except Exception as e:
            self.logger.error(f"Ошибка при удалении токенов: {e}")
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при удалении:\n{str(e)}") 
    def closeEvent(self, event, *args, **kwargs):
        self.logger.info("Закрытие окна BotManagerWindow...")
        self._is_running = False
        if hasattr(self, '_update_timer'):
            self._update_timer.stop()
        if hasattr(self, '_ui_update_batch_timer'):
            self._ui_update_batch_timer.stop()
        if hasattr(self, 'load_thread') and self.load_thread:
            self.load_thread.quit()
            self.load_thread.wait()        
        super().closeEvent(event)
        self.logger.info("Окно BotManagerWindow закрыто.") 
    def show_context_menu(self, position, *args, **kwargs):
        menu = QMenu()
        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(self.copy_selected_cells)
        menu.exec(self.table.viewport().mapToGlobal(position))
    def copy_selected_cells(self, *args, **kwargs):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            selected_items = self.table.selectedItems()
            if selected_items:
                QApplication.clipboard().setText(selected_items[0].text())
                return
        texts = []
        for range_ in selected_ranges:
            for row in range(range_.topRow(), range_.bottomRow() + 1):
                row_texts = []
                for col in range(range_.leftColumn(), range_.rightColumn() + 1):
                    item = self.table.item(row, col)
                    if item:
                        row_texts.append(item.text())
                if row_texts:
                    texts.append('\t'.join(row_texts))        
        if texts:
            QApplication.clipboard().setText('\n'.join(texts))
    def create_table_item(self, text, is_error=False, is_selectable=True, *args, **kwargs):
        item_text = str(text) if text is not None else ''
        item = QTableWidgetItem(item_text)
        if is_error:
            item.setForeground(QColor(255, 0, 0))        
        flags = Qt.ItemFlag.ItemIsEnabled
        if is_selectable:
            flags |= Qt.ItemFlag.ItemIsSelectable
        item.setFlags(flags)
        return item
    def _on_bot_details_updated(self, token: str, username: str, bot_name: str, *args, **kwargs):
        self.logger.info(f"Received bot details for ...{token[-6:]}: @{username} (Name: {bot_name})")
        has_error = False
        effective_username = username
        effective_bot_name = bot_name
        if username is None or username.strip() == "" or "Ошибка" in str(username) or username == 'Загрузка...' or username == 'Недоступен':
            has_error = True
            effective_username = "Ошибка" if username is None or username.strip() == "" else username        
        if bot_name is None or bot_name.strip() == "" or "Ошибка" in str(bot_name) or bot_name == 'Загрузка...':
            effective_bot_name = effective_username if not has_error else "Ошибка"
            if not (bot_name is None or bot_name.strip() == ""):
                 has_error = True
        self.all_bots_data[token] = {
            'token': token,
            'name': effective_bot_name,
            'username': effective_username,
            'has_error': has_error
        }
        self.logger.debug(f"all_bots_data updated for ...{token[-6:]}. New data: {self.all_bots_data[token]}")
        self._pending_token_updates_for_ui.add(token)
        if not self._ui_update_batch_timer.isActive():
            self._ui_update_batch_timer.start()
    def update_bot_data(self, token: str, param: str, value: str, *args, **kwargs):
        if token in self.all_bots_data:
            if param == 'name':
                self.all_bots_data[token]['name'] = value
            elif param == 'description':
                self.all_bots_data[token]['description'] = value
            elif param == 'short_description':
                self.all_bots_data[token]['short_description'] = value
            if token in self.current_display_tokens:
                try:
                    row = self.current_display_tokens.index(token)
                    if row < self.table.rowCount():
                        if param == 'name':
                            name_item = self.create_table_item(value)
                            self.table.setItem(row, 2, name_item)
                        self.table.viewport().update()
                        self.update_stats_for_selected_tokens()
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении строки для токена {token}: {e}")
    def open_bot_transfer(self, row=None, token_str=None, *args, **kwargs):
        selected_tokens = []
        selected_usernames = []
        if row is not None:
            has_checked = False
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    checkbox = self.get_checkbox_for_row(r)
                    if checkbox and checkbox.isChecked():
                        has_checked = True
                        break           
            if not has_checked:
                token = self.table.item(row, 4).text()
                username = self.table.item(row, 3).text()
                if username and token:
                    selected_tokens.append(token)
                    selected_usernames.append(username)
            else:
                for r in range(self.table.rowCount()):
                    if not self.table.isRowHidden(r):
                        checkbox = self.get_checkbox_for_row(r)
                        if checkbox and checkbox.isChecked():
                            token = self.table.item(r, 4).text()
                            username = self.table.item(r, 3).text()
                            if username and token:
                                selected_tokens.append(token)
                                selected_usernames.append(username)
        else:
            for r in range(self.table.rowCount()):
                if not self.table.isRowHidden(r):
                    checkbox = self.get_checkbox_for_row(r)
                    if checkbox and checkbox.isChecked():
                        token = self.table.item(r, 4).text()
                        username = self.table.item(r, 3).text()
                        if username and token:
                            selected_tokens.append(token)
                            selected_usernames.append(username)            
        if not selected_tokens:
            QMessageBox.warning(self, "Предупреждение", "Выберите ботов для передачи")
            return
        try:
            dialog = BotTransferDialog(
                selected_tokens=selected_tokens,
                selected_usernames=selected_usernames,
                session_folder=self.main_window.session_folder if hasattr(self.main_window, 'session_folder') else self.token_folder,
                parent=self
            )
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Ошибка при открытии окна передачи бота: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть окно передачи бота:\n{str(e)}")
