import os
import sys
import asyncio
import socks
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit, QProgressBar, QMessageBox,
    QSpinBox, QMenu, QRadioButton, QDialog, QGridLayout, QGroupBox,
    QCheckBox
)
from ui.proxy_utils import parse_proxy_string
from ui.thread_base import BaseThread, ThreadManager
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)
class ProxyCheckerThread(BaseThread):
    def __init__(self, proxies, api_id, api_hash, timeout=5, parent=None):
        super().__init__(parent=parent)
        self.proxies = proxies
        self.api_id = api_id
        self.api_hash = api_hash
        self.timeout = timeout
        self.working_proxies = []
        self.stats = {"total": len(proxies), "success": 0, "fail": 0}
    async def process(self, *args):
        async def check_proxy(proxy):
            proxy_str = f"{proxy['ip']}:{proxy['port']}"
            proxy_type_str = proxy.get('type', '').lower()
            proxy_type = None
            if proxy_type_str == 'socks5':
                proxy_type = socks.SOCKS5
            elif proxy_type_str == 'socks4':
                proxy_type = socks.SOCKS4
            elif proxy_type_str in ['http', 'https']:
                proxy_type = socks.HTTP
            else:
                proxy_type = socks.SOCKS5
                proxy_type_str = 'socks5'
            s = socks.socksocket()
            try:
                login = proxy.get('login', '')
                password = proxy.get('password', '')
                if login and password:
                    s.set_proxy(proxy_type, proxy['ip'], int(proxy['port']), username=login, password=password)
                else:
                    s.set_proxy(proxy_type, proxy['ip'], int(proxy['port']))
                s.settimeout(self.timeout)
                import time
                start_time = time.time()
                s.connect(('api.telegram.org', 443))
                elapsed_time = time.time() - start_time
                if elapsed_time < 1:
                    status = "Отличное соединение"
                elif elapsed_time < 2:
                    status = "Хорошее соединение"
                else:
                    status = "Слабое соединение"
                s.close()
                return proxy, status, elapsed_time
            except Exception as e:
                return proxy, f"Ошибка: {str(e)}", 0
        total = len(self.proxies)
        completed = 0
        for proxy in self.proxies:
            if not self.running:
                break
            proxy, status, elapsed_time = await asyncio.get_event_loop().run_in_executor(None, lambda: check_proxy(proxy))
            proxy_str = f"{proxy.get('type', 'socks5')}://{proxy['ip']}:{proxy['port']}"
            if proxy.get('login') and proxy.get('password'):
                proxy_str = f"{proxy.get('type', 'socks5')}://{proxy['login']}:{proxy['password']}@{proxy['ip']}:{proxy['port']}"
            if "Ошибка" in status:
                log_message = f'<span style="color:#FF5252;">❌ {proxy_str} - {status}</span>'
                self.stats["fail"] += 1
            else:
                if "Отличное" in status:
                    color = "#4CAF50"
                elif "Хорошее" in status:
                    color = "#2196F3"
                else:
                    color = "#FFC107"
                log_message = f'<span style="color:{color};">✅ {proxy_str} - {status} ({elapsed_time*1000:.0f} мс)</span>'
                self.stats["success"] += 1
                proxy['status'] = status
                proxy['speed'] = elapsed_time
                self.working_proxies.append(proxy)
            self.log_signal.emit(log_message)
            completed += 1
            progress_value = int((completed / total) * 100)
            self.progress_signal.emit(progress_value, "")
        self.done_signal.emit()
class SamitWindow(QWidget):
    def __init__(self, parent=None, api_id=None, api_hash=None):
        super().__init__(parent)
        self.parent = parent
        self.api_id = api_id if api_id is not None else getattr(parent, 'api_id', 0)
        self.api_hash = api_hash if api_hash is not None else getattr(parent, 'api_hash', '')
        self.thread_manager = ThreadManager(self)
        self.working_proxies = []
        self.init_ui()
    def init_ui(self, *args):
        main_layout = QVBoxLayout(self)
        title_label = QLabel("Проверка прокси")
        title_label.setObjectName("page_title")
        main_layout.addWidget(title_label)
        top_panel_layout = QHBoxLayout()
        self.file_path_label = QLabel("Файл с прокси не выбран")
        top_panel_layout.addWidget(self.file_path_label)
        load_file_btn = QPushButton("Загрузить файл")
        load_file_btn.clicked.connect(self.load_proxy_file)
        top_panel_layout.addWidget(load_file_btn)
        top_panel_layout.addSpacing(20)
        timeout_label = QLabel("Таймаут:")
        top_panel_layout.addWidget(timeout_label)
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setMinimum(1)
        self.timeout_spinbox.setMaximum(30)
        self.timeout_spinbox.setValue(5)
        self.timeout_spinbox.setSuffix(" сек")
        top_panel_layout.addWidget(self.timeout_spinbox)
        top_panel_layout.addStretch(1)
        top_panel_layout.addStretch(1)
        main_layout.addLayout(top_panel_layout)
        controls_group = QGroupBox("")
        controls_grid_layout = QGridLayout() 
        self.start_btn = QPushButton("Начать проверку")
        self.start_btn.clicked.connect(self.start_checking)
        self.start_btn.setEnabled(False)
        controls_grid_layout.addWidget(self.start_btn, 0, 0)
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.clicked.connect(self.stop_checking)
        self.stop_btn.setEnabled(False)
        controls_grid_layout.addWidget(self.stop_btn, 0, 1)
        self.export_btn = QPushButton("Экспорт рабочих прокси")
        self.export_btn.clicked.connect(self.export_working_proxies)
        self.export_btn.setEnabled(False)
        controls_grid_layout.addWidget(self.export_btn, 1, 0)
        self.copy_btn = QPushButton("Копировать в буфер")
        self.copy_btn.clicked.connect(self.copy_proxies_to_clipboard)
        self.copy_btn.setEnabled(False)
        controls_grid_layout.addWidget(self.copy_btn, 1, 1) 
        controls_group.setLayout(controls_grid_layout)
        main_layout.addWidget(controls_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(200)
        self.log_area.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_area.customContextMenuRequested.connect(self.show_log_context_menu)
        main_layout.addWidget(self.log_area, 1)
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Готов к проверке")
        status_layout.addWidget(self.status_label)
        self.stat_label = QLabel("Проверено: 0 | Успешно: 0 | Ошибки: 0")
        status_layout.addWidget(self.stat_label, 0, Qt.AlignmentFlag.AlignRight)
        main_layout.addLayout(status_layout)
        self.stats = {"total": 0, "success": 0, "fail": 0}
    def load_proxy_file(self, *args):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл с прокси", "", "Text Files (*.txt)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            self.proxies = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                proxy = parse_proxy_string(line)
                if proxy and proxy.get('ip') and proxy.get('port'):
                    self.proxies.append(proxy)
            if not self.proxies:
                raise ValueError("Не найдено корректных прокси в файле")
            self.file_path_label.setText(f"Загружено прокси: {len(self.proxies)}")
            self.start_btn.setEnabled(True)
            self.log_area.clear()
            self.add_log(f"Загружено {len(self.proxies)} прокси из файла {os.path.basename(file_path)}")
            self.stats = {"total": len(self.proxies), "success": 0, "fail": 0}
            self.update_stats()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить файл: {str(e)}")
    def start_checking(self, *args):
        if not self.api_id or not self.api_hash:
            QMessageBox.warning(
                self, "Ошибка",
                "API ID и API Hash не установлены. Пожалуйста, установите их в настройках."
            )
            return
        if not hasattr(self, 'proxies') or not self.proxies:
            QMessageBox.warning(self, "Ошибка", "Нет загруженных прокси для проверки")
            return
        self.progress_bar.setValue(0)
        self.log_area.clear()
        self.working_proxies = []
        self.add_log(f"Начинаем проверку {len(self.proxies)} прокси...")
        timeout = self.timeout_spinbox.value()
        self.proxy_checker_thread = ProxyCheckerThread(self.proxies, self.api_id, self.api_hash, timeout)
        self.proxy_checker_thread.log_signal.connect(self.add_log)
        self.proxy_checker_thread.progress_signal.connect(lambda value, _: self.update_progress(value))
        self.proxy_checker_thread.done_signal.connect(self.on_checking_finished)
        self.thread_manager.add_thread(self.proxy_checker_thread)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.status_label.setText("Проверка прокси...")
        self.thread_manager.start_thread(self.proxy_checker_thread)
    def stop_checking(self, *args):
        if self.proxy_checker_thread and self.proxy_checker_thread.isRunning():
            self.add_log("Останавливаем проверку...")
            self.thread_manager.stop_thread(self.proxy_checker_thread)
            self.status_label.setText("Останавливаем...")
            self.stop_btn.setEnabled(False)
    def update_progress(self, value, *args):
        self.progress_bar.setValue(value)
    def on_checking_finished(self, *args):
        if self.proxy_checker_thread:
            self.working_proxies = self.proxy_checker_thread.working_proxies
            stats = self.proxy_checker_thread.stats
            self.stats = stats
            self.update_stats()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        working_proxies_count = len(self.working_proxies)
        self.export_btn.setEnabled(working_proxies_count > 0)
        self.copy_btn.setEnabled(working_proxies_count > 0)
        self.add_log(f"<b>Проверка завершена. Найдено {working_proxies_count} рабочих прокси.</b>")
        self.status_label.setText("Проверка завершена")
    def export_working_proxies(self, *args):
        if not self.working_proxies:
            QMessageBox.warning(self, "Ошибка", "Нет рабочих прокси для экспорта")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Настройки экспорта")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        quality_group = QGroupBox("Фильтр качества")
        quality_layout = QVBoxLayout(quality_group)
        self.export_all_rb = QRadioButton("Все рабочие прокси")
        self.export_all_rb.setChecked(True)
        quality_layout.addWidget(self.export_all_rb)
        self.export_excellent_rb = QRadioButton("Только отличные")
        quality_layout.addWidget(self.export_excellent_rb)
        self.export_good_rb = QRadioButton("Отличные и хорошие")
        quality_layout.addWidget(self.export_good_rb)
        layout.addWidget(quality_group)
        format_group = QGroupBox("Формат экспорта")
        format_layout = QVBoxLayout(format_group)
        self.include_comments_cb = QCheckBox("Включить комментарии о качестве")
        self.include_comments_cb.setChecked(True)
        format_layout.addWidget(self.include_comments_cb)
        layout.addWidget(format_group)
        buttons_layout = QHBoxLayout()
        export_btn = QPushButton("Экспорт")
        export_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(export_btn)
        layout.addLayout(buttons_layout)
        if not dialog.exec():
            return
        filtered_proxies = []
        for proxy in self.working_proxies:
            if self.export_all_rb.isChecked():
                filtered_proxies.append(proxy)
            elif self.export_excellent_rb.isChecked() and "Отличное" in proxy['status']:
                filtered_proxies.append(proxy)
            elif self.export_good_rb.isChecked() and ("Отличное" in proxy['status'] or "Хорошее" in proxy['status']):
                filtered_proxies.append(proxy)
        if not filtered_proxies:
            QMessageBox.warning(self, "Ошибка", "Нет прокси, соответствующих выбранным критериям")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить рабочие прокси", "", "Text Files (*.txt)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for proxy in filtered_proxies:
                    proxy_str = f"{proxy.get('type', 'socks5')}://"
                    if proxy.get('login') and proxy.get('password'):
                        proxy_str += f"{proxy['login']}:{proxy['password']}@"
                    proxy_str += f"{proxy['ip']}:{proxy['port']}"
                    if self.include_comments_cb.isChecked():
                        speed_info = f" # {proxy['status']} ({proxy['speed']*1000:.0f} мс)"
                        f.write(proxy_str + speed_info + '\n')
                    else:
                        f.write(proxy_str + '\n')
            self.add_log(f"<b>Рабочие прокси экспортированы в {os.path.basename(file_path)}</b>")
            QMessageBox.information(
                self, "Успех",
                f"Экспортировано {len(filtered_proxies)} прокси в файл {os.path.basename(file_path)}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить файл: {str(e)}")
    def copy_proxies_to_clipboard(self, *args):
        if not self.working_proxies:
            QMessageBox.warning(self, "Ошибка", "Нет рабочих прокси для копирования")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Копировать в буфер обмена")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        quality_group = QGroupBox("Фильтр качества")
        quality_layout = QVBoxLayout(quality_group)
        self.copy_all_rb = QRadioButton("Все рабочие прокси")
        self.copy_all_rb.setChecked(True)
        quality_layout.addWidget(self.copy_all_rb)
        self.copy_excellent_rb = QRadioButton("Только отличные")
        quality_layout.addWidget(self.copy_excellent_rb)
        self.copy_good_rb = QRadioButton("Отличные и хорошие")
        quality_layout.addWidget(self.copy_good_rb)
        layout.addWidget(quality_group)
        format_group = QGroupBox("Формат")
        format_layout = QVBoxLayout(format_group)
        self.copy_comments_cb = QCheckBox("Включить комментарии о качестве")
        self.copy_comments_cb.setChecked(False)
        format_layout.addWidget(self.copy_comments_cb)
        layout.addWidget(format_group)
        buttons_layout = QHBoxLayout()
        copy_btn = QPushButton("Копировать")
        copy_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(dialog.reject)
        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(copy_btn)
        layout.addLayout(buttons_layout)
        if not dialog.exec():
            return
        filtered_proxies = []
        for proxy in self.working_proxies:
            if self.copy_all_rb.isChecked():
                filtered_proxies.append(proxy)
            elif self.copy_excellent_rb.isChecked() and "Отличное" in proxy['status']:
                filtered_proxies.append(proxy)
            elif self.copy_good_rb.isChecked() and ("Отличное" in proxy['status'] or "Хорошее" in proxy['status']):
                filtered_proxies.append(proxy)
        if not filtered_proxies:
            QMessageBox.warning(self, "Ошибка", "Нет прокси, соответствующих выбранным критериям")
            return
        clipboard_text = ""
        for proxy in filtered_proxies:
            proxy_str = f"{proxy.get('type', 'socks5')}://"
            if proxy.get('login') and proxy.get('password'):
                proxy_str += f"{proxy['login']}:{proxy['password']}@"
            proxy_str += f"{proxy['ip']}:{proxy['port']}"
            if self.copy_comments_cb.isChecked():
                speed_info = f" # {proxy['status']} ({proxy['speed']*1000:.0f} мс)"
                clipboard_text += proxy_str + speed_info + '\n'
            else:
                clipboard_text += proxy_str + '\n'
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(clipboard_text)

        self.add_log(f"<b>Скопировано {len(filtered_proxies)} прокси в буфер обмена</b>")

        QMessageBox.information(
            self, "Успех",
            f"Скопировано {len(filtered_proxies)} прокси в буфер обмена"
        )
    def show_log_context_menu(self, position, *args):
        menu = QMenu()
        copy_action = QAction("Копировать", self)
        copy_action.triggered.connect(self.log_area.copy)
        menu.addAction(copy_action)
        select_all_action = QAction("Выделить всё", self)
        select_all_action.triggered.connect(self.log_area.selectAll)
        menu.addAction(select_all_action)
        clear_action = QAction("Очистить", self)
        clear_action.triggered.connect(self.log_area.clear)
        menu.addAction(clear_action)
        menu.exec(self.log_area.mapToGlobal(position))
    def update_stats(self, *args):
        success_count = self.stats['success']
        fail_count = self.stats['fail']
        total = self.stats['total']
        completed = success_count + fail_count
        stats_html = (
            f"Проверено: <b>{completed}/{total}</b> | "
            f"Успешно: <span style='color:#4CAF50;'><b>{success_count}</b></span> | "
            f"Ошибки: <span style='color:#FF5252;'><b>{fail_count}</b></span>"
        )
        self.stat_label.setText(stats_html)
        self.stat_label.setTextFormat(Qt.TextFormat.RichText)
    def add_log(self, message, *args):
        self.log_area.append(message)
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
