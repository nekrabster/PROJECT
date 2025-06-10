import logging, os
from random import randint
import random
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget, QComboBox
)
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam, InputReportReasonViolence, InputReportReasonPornography,
    InputReportReasonOther, InputReportReasonFake, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonGeoIrrelevant,
    InputReportReasonIllegalDrugs, InputReportReasonPersonalDetails,
    User, ReportResultReported, ReportResultAddComment, ReportResultChooseOption
)
from ui.okak import ErrorReportDialog
from ui.loader import (
    load_config, load_proxy
)
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection 
)
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
from ui.thread_base import ThreadStopMixin, BaseThread
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
class ComplaintThread(BaseThread):
    def __init__(self, session_folder, session_file, complaint, target_id, use_proxy, min_interval, max_interval, session_window, parent=None, proxy=None, *args):
        super().__init__(session_file=session_file, parent=parent)
        self.session_folder = session_folder
        self.session_file = session_file
        self.complaint = complaint
        self.target_id = target_id
        self.use_proxy = use_proxy
        self.proxy = proxy
        self.session_window = session_window
        self.reason_key = "spam"
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.log_signal.emit)
        self.set_delay_range(min_interval, max_interval)
    async def process(self, *args, **kwargs):
        self.progress_signal.emit(0, "")
        await self._connect_to_telegram(self.session_file)
        entity_id = await self._get_target_id(self.session_file)
        if not entity_id:
            self.progress_signal.emit(100, f"{os.path.basename(self.session_file)}: ошибка обработки")
            return
        reason_obj = self.get_reason_object(self.reason_key)
        await self._send_complaint(self.session_file, entity_id, reason_obj, self.complaint)
        self.progress_signal.emit(100, f"Жалоба от {os.path.basename(self.session_file)} успешно отправлена")
    async def _connect_to_telegram(self, session_file, *args, **kwargs):
        if not self.connection:
            self.connection = TelegramConnection(self.session_folder)
            self.connection.log_signal.connect(self.log_signal.emit)
        await self.connection.connect(session_file, use_proxy=self.use_proxy, proxy=self.proxy)
    async def _get_target_id(self, session_file, *args, **kwargs):
        try:
            entity = await self.connection.client.get_entity(self.target_id)
        except Exception:
            return None
        if entity is None:
            return None
        if isinstance(entity, User) or hasattr(entity, 'id'):
            return entity.id
        else:
            return None
    async def _send_complaint(self, session_file, entity_id, reason_obj, complaint, *args, **kwargs):
        try:
            result = await self.connection.client(ReportPeerRequest(
                peer=entity_id,
                reason=reason_obj,
                message=complaint
            ))
            if isinstance(result, ReportResultReported) or result is True:
                self.log_signal.emit(f"✅ {os.path.basename(session_file)}: жалоба успешно отправлена")
            elif isinstance(result, ReportResultAddComment):
                self.log_signal.emit(f"⚠️ {os.path.basename(session_file)} | Требуется комментарий (не реализовано)")
            elif isinstance(result, ReportResultChooseOption):
                self.log_signal.emit(f"⚠️ {os.path.basename(session_file)} | Требуется дополнительная опция")
            else:
                self.log_signal.emit(f"❌ {os.path.basename(session_file)} | Неизвестный ответ")
        except Exception:
            pass
    async def apply_delay(self, *args, **kwargs):
        await super().apply_delay()
    def get_reason_object(self, reason_key, *args, **kwargs):
        reasons_map = {
            "spam": InputReportReasonSpam(),
            "violence": InputReportReasonViolence(),
            "porn": InputReportReasonPornography(),
            "child_abuse": InputReportReasonChildAbuse(),
            "copyright": InputReportReasonCopyright(),
            "geo_irrelevant": InputReportReasonGeoIrrelevant(),
            "fake": InputReportReasonFake(),
            "illegal_drugs": InputReportReasonIllegalDrugs(),
            "personal_details": InputReportReasonPersonalDetails(),
            "other": InputReportReasonOther(),
        }
        return reasons_map.get(reason_key, InputReportReasonSpam())
class ComplaintsWindow(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, parent=None, *args):
        super().__init__(parent, *args)
        ThreadStopMixin.__init__(self)
        self.parent = parent
        self.session_folder = session_folder
        self.main_window = parent
        self.setWindowTitle("Отправка жалоб")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        main_layout = QHBoxLayout()
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси", self)
        self.use_proxy_txt_checkbox = QCheckBox("Использовать прокси из txt-файла", self)
        proxy_layout.addWidget(self.use_proxy_checkbox)
        proxy_layout.addWidget(self.use_proxy_txt_checkbox)
        left_layout.addLayout(proxy_layout)
        reason_layout = QHBoxLayout()
        reason_layout.addWidget(QLabel("Причина жалобы:"))
        self.reason_combo = QComboBox(self)
        self.reason_combo.setFixedWidth(200)
        self.reason_map = {
            "Спам": "spam",
            "Фейк": "fake",
            "Насилие": "violence",
            "Гео-нерелевантно": "geo_irrelevant",
            "Порнография": "porn",
            "Детская порнография": "child_abuse",
            "Авторские права": "copyright",
            "Личные данные": "personal_details",
            "Наркотики": "illegal_drugs",
            "Другое": "other",
        }
        for label in self.reason_map.keys():
            self.reason_combo.addItem(label)
        reason_layout.addWidget(self.reason_combo)
        reason_layout.addStretch()
        left_layout.addLayout(reason_layout)
        self.select_file_button = QPushButton("Выбрать файл с жалобами", self)
        self.select_file_button.clicked.connect(self.select_complaints_file)
        left_layout.addWidget(self.select_file_button)
        self.instructions_text = QTextEdit(self)
        self.instructions_text.setReadOnly(True)
        self.instructions_text.setPlainText(
            "Инструкции по формату жалоб:\nКаждая жалоба должна быть записана на отдельной строке.\n\nПример:\n\nПроблема с аккаунтом.\nСпам в чате.\nНарушение правил."
        )
        self.instructions_text.setMaximumHeight(100)
        left_layout.addWidget(self.instructions_text)
        left_layout.addWidget(QLabel("Ссылка на получателя:"))
        self.target_input = QLineEdit(self)
        self.target_input.setPlaceholderText("@username или ссылка")
        left_layout.addWidget(self.target_input)
        interval_layout = QHBoxLayout()
        self.min_interval_input = QLineEdit(self)
        self.max_interval_input = QLineEdit(self)
        self.min_interval_input.setPlaceholderText("Мин. (сек)")
        self.max_interval_input.setPlaceholderText("Макс. (сек)")
        interval_layout.addWidget(QLabel("Задержка:"))
        interval_layout.addWidget(self.min_interval_input)
        interval_layout.addWidget(self.max_interval_input)
        left_layout.addLayout(interval_layout)
        control_layout = QHBoxLayout()
        self.send_complaints_button = QPushButton("▶ Отправить жалобы", self)
        self.stop_button = QPushButton("⏹ Остановить процесс", self)
        self.send_complaints_button.clicked.connect(self.start_complaint_thread)
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.send_complaints_button)
        control_layout.addWidget(self.stop_button)
        left_layout.addLayout(control_layout)
        self.delay_label = QLabel("Текущая задержка: 0 секунд")
        left_layout.addWidget(self.delay_label)
        self.status_text = QTextEdit(self)
        self.status_text.setReadOnly(True)
        left_layout.addWidget(self.status_text)
        self.progress_widget = ProgressWidget(self)
        left_layout.addWidget(self.progress_widget)
        self.session_window = SessionWindow(session_folder, self)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(self.session_window, 1)
        self.setLayout(main_layout)
        self.complaints = []
        self.target_id = ""
        self.complaint_number = 1
        self.process_running = False
        self.total_sessions = 0
        self.processed_sessions = 0
        self.active_sessions = set()
        self.session_progress = {}
        self.total_operations = 0
        self.completed_operations = 0
        self.proxies_list = []
        self.proxy_txt_path = None
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
        cfg = load_config()
        self.proxy = load_proxy(cfg) if cfg else {}
        if hasattr(self.main_window, 'config_changed'):
            self.main_window.config_changed.connect(self.session_window.on_config_changed)
    def start_complaint_thread(self, *args):
        if not self.target_input.text().strip():
            self.status_text.append("⛔ Введите ID цели")
            return
        self.status_text.clear()
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions:
            self.update_status("⛔ Не выбрано ни одной сессии")
            return
        if not self.complaints:
            self.update_status("Сначала нужно загрузить текстовый файл с жалобами.")
            return
        selected_label = self.reason_combo.currentText()
        reason_key = self.reason_map.get(selected_label)
        if not reason_key:
            self.update_status("Ошибка: выберите причину жалобы!")
            return
        self.selected_reason = reason_key
        from ui.components import extract_username
        self.target_id = extract_username(self.target_input.text())
        if not self.target_id:
            self.update_status("Ошибка: ID получателя не указан!")
            return
        try:
            min_val = int(self.min_interval_input.text()) if self.min_interval_input.text().strip() else 0
            max_val = int(self.max_interval_input.text()) if self.max_interval_input.text().strip() else 0
            if min_val > max_val and max_val > 0:
                raise ValueError("Минимальная задержка должна быть меньше или равна максимальной.")
        except ValueError as e:
            self.update_status(f"Ошибка интервала: {str(e)}")
            return
        self.process_running = True
        self.send_complaints_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.update_status("Начинаем отправку жалоб...", append=False)
        use_proxy = self.use_proxy_checkbox.isChecked()
        use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
        config = None
        if use_proxy:
            config = load_config()
        threads = []
        n = min(len(selected_sessions), len(self.complaints))
        for idx in range(n):
            session_file = selected_sessions[idx]
            complaint = self.complaints[idx]
            proxy = None
            log_str = None
            if use_proxy_txt and self.proxies_list:
                proxy = load_proxy_from_list(idx, self.proxies_list)
                if proxy:
                    log_str = f"🌐 [{session_file}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}"
            elif use_proxy:
                proxy = load_proxy(config)
                if proxy:
                    log_str = f"🌐 [{session_file}] Используется прокси: {proxy.get('addr', 'не указан')}"
            else:
                log_str = f"ℹ️ [{session_file}] Прокси не используется"
            if log_str:
                self.update_status(log_str)
            thread = ComplaintThread(
                self.session_window.session_folder,
                session_file,
                complaint,
                self.target_id,
                use_proxy,
                min_val,
                max_val,
                self.session_window,
                self,
                proxy
            )
            thread.progress_signal.connect(self.update_progress)
            thread.error_signal.connect(self.handle_thread_error)
            thread.log_signal.connect(self.update_status)
            thread.delay_signal.connect(self.update_delay_label)
            threads.append(thread)
        self.total_sessions = len(threads)
        self.total_operations = len(threads)
        self.completed_operations = 0
        if min_val == 0 and max_val == 0:
            for thread in threads:
                self.thread_manager.start_thread(thread)
        else:
            self.start_threads_with_delay(threads, min_delay=min_val, max_delay=max_val)
        self.active_sessions = set(selected_sessions[:n])
        self.processed_sessions = 0
        self.session_progress.clear()
        for session in selected_sessions[:n]:
            self.session_progress[session] = 0
        self.update_progress(0, "")
    def on_sessions_updated(self, valid_sessions, *args):
        self.total_sessions = len(valid_sessions)
        self.update_progress(0, f"Доступно {self.total_sessions} сессий")
    def handle_thread_error(self, error_message, *args):
        self.update_status(f"Ошибка: {error_message}")
        QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(error_message))
    def get_interval(self, need_random=True, *args):
        try:
            min_val = int(self.min_interval_input.text()) if self.min_interval_input.text().strip() else 0
            max_val = int(self.max_interval_input.text()) if self.max_interval_input.text().strip() else 0
            if need_random and min_val is not None and max_val is not None:
                return random.randint(min_val, max_val)
            elif min_val is not None and max_val is not None:
                return (min_val + max_val) // 2
            return 0
        except ValueError as e:
            self.update_status(f"Ошибка: {str(e)}")
            return 0
    def select_complaints_file(self, *args):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл с жалобами", "", "Текстовые файлы (*.txt)")
        if file_path:
            self.load_complaints_file(file_path)
    def load_complaints_file(self, file_path, *args):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                complaints = file.read().strip().split('\n')
                self.complaints = [c.strip() for c in complaints if c.strip()]
            self.instructions_text.setPlainText(f"Загружено {len(self.complaints)} жалоб из файла {os.path.basename(file_path)}")
            self.update_status(f"Загружено {len(self.complaints)} жалоб из файла {os.path.basename(file_path)}")
        except Exception as e:
            self.update_status(f"Ошибка при загрузке файла: {str(e)}")
    def update_status(self, message: str, append=True, *args):
        if append:
            self.status_text.append(message)
        else:
            self.status_text.setText(message)
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())
    def update_progress(self, thread_progress: int, status_text: str, *args):
        if self.total_operations > 0:
            if thread_progress == 100:
                self.completed_operations += 1
            total_progress = (self.completed_operations / self.total_operations) * 100
            if self.completed_operations >= self.total_operations:
                self.progress_widget.update_progress(100, "Все жалобы отправлены")
                self.process_running = False
                self.send_complaints_button.setEnabled(True)
                self.stop_button.setEnabled(False)
            else:
                self.progress_widget.update_progress(int(total_progress), f"Отправлено {self.completed_operations} из {self.total_operations}")
    def update_delay_label(self, delay, *args):
        # delay приходит как от потока (apply_delay), так и от DelayedThreadStarter (между потоками)
        self.delay_label.setText(f"Текущая задержка: {delay} секунд")
    def get_reason_object(self, reason_key, *args):
        reasons_map = {
            "spam": InputReportReasonSpam(),
            "violence": InputReportReasonViolence(),
            "porn": InputReportReasonPornography(),
            "child_abuse": InputReportReasonChildAbuse(),
            "copyright": InputReportReasonCopyright(),
            "geo_irrelevant": InputReportReasonGeoIrrelevant(),
            "fake": InputReportReasonFake(),
            "illegal_drugs": InputReportReasonIllegalDrugs(),
            "personal_details": InputReportReasonPersonalDetails(),
            "other": InputReportReasonOther(),
        }
        return reasons_map.get(reason_key, InputReportReasonSpam())
    def stop_process(self, *args, **kwargs):
        self.stop_all_operations()
        self.process_running = False
        self.send_complaints_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.update_status("Процесс остановлен.")
        self.progress_widget.update_progress(100, "Процесс остановлен")
        self.complaints = []
        self.active_sessions = set()
        self.session_progress.clear()
    def on_use_proxy_txt_toggled(self, checked, *args, **kwargs):
        if checked:
            from PyQt6.QtWidgets import QFileDialog
            file_path, _ = QFileDialog.getOpenFileName(self, "Выберите txt-файл с прокси", "", "Text Files (*.txt)")
            if file_path:
                self.proxy_txt_path = file_path
                self.proxies_list = parse_proxies_from_txt(file_path)
                self.update_status(f"✅ Загружено прокси из файла: {len(self.proxies_list)}")
            else:
                self.use_proxy_txt_checkbox.setChecked(False)
        else:
            self.proxy_txt_path = None
            self.proxies_list = []
