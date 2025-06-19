from PyQt6.QtWidgets import (
    QWidget, QCheckBox, QSizePolicy, QScrollArea,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
class BaseTableManager(QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.table = None
        self.search_input = None
        self.table_wrapper_widget = None
        self.filters = {}
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.update_table_dimensions)
    def setup_table_ui(self, column_config, parent_layout, *args, **kwargs):
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(self.filter_table)
        self.search_input.setFixedWidth(100)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)
        self.table = QTableWidget()
        self.table.setColumnCount(len(column_config))
        self.table.setHorizontalHeaderLabels([c['label'] for c in column_config])
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self.handle_selection_changed)
        self.table.cellClicked.connect(self.handle_cell_click)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        for i, config in enumerate(column_config):
            header.setSectionResizeMode(i, config.get('resize_mode', QHeaderView.ResizeMode.Interactive))
            if 'width' in config:
                self.table.setColumnWidth(i, config['width'])
        header.sectionClicked.connect(self.handle_header_click)
        self.table_wrapper_widget = QWidget()
        self.table_wrapper_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_wrapper_layout = QHBoxLayout(self.table_wrapper_widget)
        table_wrapper_layout.setContentsMargins(10, 0, 10, 0)
        table_wrapper_layout.setSpacing(0)
        table_wrapper_layout.addWidget(self.table)
        scroll_area.setWidget(self.table_wrapper_widget)
        parent_layout.addWidget(scroll_area)        
    def resizeEvent(self, event, *args, **kwargs):
        super().resizeEvent(event)
        self.resize_timer.start(100)
    def update_table_dimensions(self, *args, **kwargs):
        if not self.table:
            return
        header = self.table.horizontalHeader()
        stretch_column_found = False
        for i in range(header.count()):
            if header.sectionResizeMode(i) == QHeaderView.ResizeMode.Stretch:
                stretch_column_found = True
                break
        if not stretch_column_found:
            for i in range(header.count() - 1, -1, -1):
                if header.sectionResizeMode(i) == QHeaderView.ResizeMode.Interactive:
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                    break
        self.table.resizeColumnsToContents()
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
        table_final_height += 4 
        self.table.setFixedHeight(table_final_height)
        self.table_wrapper_widget.setFixedHeight(table_final_height)
        self.table.horizontalScrollBar().setValue(0)
        self.table.verticalScrollBar().setValue(0)
        self.adjust_column_widths()
    def adjust_column_widths(self, *args, **kwargs):
        if not self.table:
            return
        header = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            if header.sectionResizeMode(i) == QHeaderView.ResizeMode.Interactive:
                self.table.resizeColumnToContents(i)
                current_width = self.table.columnWidth(i)
                self.table.setColumnWidth(i, current_width + 15)
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
            except TypeError:
                pass
            for row in range(self.table.rowCount()):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox:
                    checkbox.setChecked(not all_checked)
            try:
                self.table.itemSelectionChanged.connect(self.handle_selection_changed)
            except TypeError:
                pass
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
            for col in range(self.table.columnCount()):
                if self.table.cellWidget(row, col) and isinstance(self.table.cellWidget(row,col).layout().itemAt(0).widget(), QCheckBox):
                    continue
                item = self.table.item(row, col)
                if item and text.lower() in item.text().lower():
                    return True
            return False
        self.filter_rows_by_conditions([search_cond])
    def filter_rows_by_conditions(self, conditions, *args, **kwargs):
        for row in range(self.table.rowCount()):
            show_row = all(cond(row) for cond in conditions)
            self.table.setRowHidden(row, not show_row)
        self.update_row_numbers()
        self.update_table_dimensions()
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
    def update_edit_button_state(self, *args, **kwargs):
        has_selected = False
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                checkbox = self.get_checkbox_for_row(row)
                if checkbox and checkbox.isChecked():
                    has_selected = True
                    break
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
