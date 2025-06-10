import os
import json
import asyncio
import re
from typing import Dict, List, Any
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QTextEdit, QLabel, QStatusBar, QHBoxLayout, QCheckBox, QGroupBox, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from .apphuy import TelegramConnection, select_proxy
from .loader import load_config
from .session_win import SessionWindow
from ui.thread_base import BaseThread, ThreadStopMixin
from telethon import functions
class SearchThread(BaseThread):
    update_results = pyqtSignal(str, str)
    def __init__(self, parent, session_folder, session_file, query, proxy=None):
        super().__init__(session_file=session_file, parent=parent)
        self.parent = parent
        self.session_folder = session_folder
        self.session_file = session_file
        self.query = query
        self.proxy = proxy
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.emit_log)
    async def process(self, *args):
        if not self.running:
            return
        success, me = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy), proxy=self.proxy)
        if not success or not me:
            return
        try:
            client = self.connection.get_client()
            if not client or not await self.connection.check_authorization():
                return
            normalized_query = self.query.strip()
            if not normalized_query:
                return
            search_result = await client(functions.contacts.SearchRequest(
                q=normalized_query,
                limit=100
            ))
            users_dict = {user.id: user for user in getattr(search_result, 'users', [])}
            chats_dict = {chat.id: chat for chat in getattr(search_result, 'chats', [])}
            formatted_results = []
            if hasattr(search_result, 'results'):
                for result in search_result.results:
                    formatted_line = self.format_result(result, users_dict, chats_dict)
                    if formatted_line:
                        formatted_results.append(formatted_line)
            else:
                for chat in getattr(search_result, 'chats', []):
                    title = getattr(chat, 'title', "")
                    username = getattr(chat, 'username', None)
                    members_count = getattr(chat, 'participants_count', 0) or 0
                    formatted_line = f"{title}"
                    if username:
                        formatted_line += f"\n@{username}"
                        if members_count > 0:
                            formatted_line += f" – {members_count} members"
                    formatted_results.append(formatted_line)
                for user in getattr(search_result, 'users', []):
                    first_name = getattr(user, 'first_name', '')
                    last_name = getattr(user, 'last_name', '')
                    name = f"{first_name} {last_name}".strip()
                    username = getattr(user, 'username', None)
                    is_bot = getattr(user, 'bot', False)
                    bot_indicator = " 🤖" if is_bot else ""
                    formatted_line = f"{name}"
                    if username:
                        formatted_line += f"\n@{username}{bot_indicator}"
                    formatted_results.append(formatted_line)
            numbered_results = [f"{i+1}. {line}" for i, line in enumerate(formatted_results)]
            if numbered_results:
                country_code, country_name = self.parent.get_country_by_phone(self.session_file)
                results_text = f"[{self.query}]\n{country_name}\n\n" + "\n\n".join(numbered_results)
                self.update_results.emit(self.session_file, results_text)
        finally:
            if hasattr(self.connection, 'client') and self.connection.client:
                await self.connection.disconnect()
    def format_result(self, result, users_dict, chats_dict):
        if hasattr(result, 'user_id') and result.user_id in users_dict:
            user = users_dict[result.user_id]
            first_name = getattr(user, 'first_name', '')
            last_name = getattr(user, 'last_name', '')
            name = f"{first_name} {last_name}".strip()
            username = getattr(user, 'username', None)
            is_bot = getattr(user, 'bot', False)
            bot_indicator = " 🤖" if is_bot else ""
            formatted_line = f"{name}"
            if username:
                formatted_line += f"\n@{username}{bot_indicator}"
            return formatted_line.replace(" None", "")
        elif hasattr(result, 'chat_id') and result.chat_id in chats_dict:
            chat = chats_dict[result.chat_id]
            title = getattr(chat, 'title', "")
            username = getattr(chat, 'username', None)
            members_count = getattr(chat, 'participants_count', 0) or 0
            formatted_line = f"{title}"
            if username:
                formatted_line += f"\n@{username}"
                if members_count > 0:
                    formatted_line += f" – {members_count} members"
            return formatted_line.replace(" None", "")
        elif hasattr(result, 'channel_id') and result.channel_id in chats_dict:
            chat = chats_dict[result.channel_id]
            title = getattr(chat, 'title', "")
            username = getattr(chat, 'username', None)
            members_count = getattr(chat, 'participants_count', 0) or 0
            formatted_line = f"{title}"
            if username:
                formatted_line += f"\n@{username}"
                if members_count > 0:
                    formatted_line += f" – {members_count} members"
            return formatted_line.replace(" None", "")
        return None
class SearchWindow(QMainWindow, ThreadStopMixin):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        ThreadStopMixin.__init__(self)
        self.setWindowTitle("Поиск по сессиям")
        self.setMinimumSize(900, 600)
        if parent and hasattr(parent, 'config_changed'):
            self.main_window = parent
            self.main_window.config_changed.connect(self.on_config_changed)
        self.session_folder = self.get_search_path()
        os.makedirs(self.session_folder, exist_ok=True)
        self.init_ui()
        self.search_threads = []
        self.total_sessions = 0
        self.processed_sessions = 0
        self.process_running = False
        self.cached_selected_sessions = []
        selected_sessions = self.session_window.get_selected_sessions()
        if selected_sessions:
            self.search_button.setEnabled(True)
            self.update_session_stats(selected_sessions)
            self.prepare_results_areas(selected_sessions)
            self._initialized_results = True
            self.cached_selected_sessions = selected_sessions
    def get_search_path(self):
        config = load_config()
        return config.get('SESSION_FOLDER', os.path.dirname(os.path.abspath(__file__)))
    def init_ui(self, *args, **kwargs):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_layout.setContentsMargins(10, 10, 10, 10)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Введите поисковый запрос...")
        self.search_input.returnPressed.connect(self.handle_search_click)
        search_layout.addWidget(self.search_input)
        self.search_button = QPushButton("▶ Поиск")
        self.search_button.clicked.connect(self.handle_search_click)
        search_layout.addWidget(self.search_button)
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.clicked.connect(self.stop_search)
        search_layout.addWidget(self.stop_button)
        self.use_proxy_checkbox = QCheckBox("🌐 Использовать прокси")
        search_layout.addWidget(self.use_proxy_checkbox)
        left_layout.addLayout(search_layout)
        results_container = QWidget()
        self.results_layout = QVBoxLayout(results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_areas = {}
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(results_container)
        left_layout.addWidget(scroll_area, 1)
        left_layout.addWidget(QLabel("📋 Логи:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(100)
        font = self.log_area.font()
        font.setPointSize(9)
        self.log_area.setFont(font)
        left_layout.addWidget(self.log_area)
        self.session_window = SessionWindow(self.session_folder, self)
        self.session_window._default_selected = False
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(self.session_window, 1)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("✅ Готов к поиску")
    def update_status(self, message: str, *args, **kwargs):
        self.status_bar.showMessage(message)
    def on_sessions_updated(self, valid_sessions, *args):
        if not valid_sessions:
            self.search_button.setEnabled(False)
            self.update_status("Выберите сессии для поиска")
        else:
            self.search_button.setEnabled(True)
            self.update_session_stats(valid_sessions)
            self.cached_selected_sessions = valid_sessions.copy()
            if not self.process_running and not hasattr(self, '_initialized_results'):
                self.prepare_results_areas(valid_sessions)
                self._initialized_results = True
    def update_session_stats(self, sessions, *args, **kwargs):
        if not sessions:
            self.update_status("Нет выбранных сессий")
            return
        countries_count = {}
        for session in sessions:
            country_code, country_name = self.get_country_by_phone(session)
            key = country_name or "Неизвестная страна"
            if key in countries_count:
                countries_count[key] += 1
            else:
                countries_count[key] = 1
        stats = []
        for country, count in countries_count.items():
            stats.append(f"{country}: {count}")
        total = len(sessions)
        unique = len(countries_count)
        if unique == total:
            self.update_status(f"Выбрано {total} сессий из {unique} стран: " + ", ".join(stats))
        else:
            self.update_status(f"Выбрано {total} сессий из {unique} стран (будет использовано {unique}): " + ", ".join(stats))
    def handle_search_click(self, *args, **kwargs):
        asyncio.create_task(self.start_search())
    async def start_search(self, *args, **kwargs):
        if self.process_running:
            return
        query = self.search_input.text().strip()
        if not query:
            self.status_bar.showMessage("Введите поисковый запрос")
            return
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions and self.cached_selected_sessions:
            selected_sessions = self.cached_selected_sessions
        if not selected_sessions:
            self.status_bar.showMessage("Выберите хотя бы одну сессию")
            return
        self.update_session_stats(selected_sessions)
        self.clear_results()
        self.prepare_results_areas(selected_sessions)
        self.search_button.setEnabled(False)
        self.status_bar.showMessage("Выполняется поиск...")
        country_sessions = {}
        skipped_sessions = []
        for session_file in selected_sessions:
            country_code, country_name = self.get_country_by_phone(session_file)
            if country_code:
                if country_code not in country_sessions:
                    country_sessions[country_code] = session_file
                else:
                    skipped_sessions.append((session_file, country_name))
            else:
                unknown_key = f"unknown_{len(country_sessions)}"
                country_sessions[unknown_key] = session_file
        unique_sessions = list(country_sessions.values())
        self.total_sessions = len(unique_sessions)
        self.processed_sessions = 0
        self.process_running = True
        self.search_threads = []
        use_proxy = self.use_proxy_checkbox.isChecked()
        proxies_list = []
        use_proxy_txt = False
        config = load_config()
        for idx, session_file in enumerate(unique_sessions):
            proxy, _ = select_proxy(idx, use_proxy, use_proxy_txt, proxies_list, config)
            thread = SearchThread(self, self.session_window.session_folder, session_file, query, proxy)
            thread.update_results.connect(self.update_search_results)
            thread.log_signal.connect(self.append_log)
            thread.done_signal.connect(lambda: self.on_thread_finished(thread))
            self.search_threads.append(thread)
        for thread in self.search_threads:
            self.thread_manager.start_thread(thread)
    def stop_search(self, *args, **kwargs):
        self.stop_all_operations()
        self.search_button.setEnabled(True)
        self.update_status("Поиск остановлен")
        self.processed_sessions = 0
        self.total_sessions = 0
        self.process_running = False
    def on_thread_finished(self, thread, *args, **kwargs):
        if thread in self.search_threads:
            self.search_threads.remove(thread)
        self.processed_sessions += 1
        if self.total_sessions > 0:
            progress = (self.processed_sessions / self.total_sessions) * 100
            self.update_status(f"Обработано {self.processed_sessions} из {self.total_sessions} сессий ({int(progress)}%)")
        if not self.search_threads:
            self.process_running = False
            self.search_button.setEnabled(True)
            self.update_status("Поиск завершен")
            self.processed_sessions = 0
            self.total_sessions = 0
    def append_log(self, message, *args, **kwargs):
        self.log_area.append(message)
    def prepare_results_areas(self, session_files, saved_results=None, *args, **kwargs):
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if saved_results is None:
            saved_results = {}
            for country_code, text_area in self.results_areas.items():
                content = text_area.toPlainText()
                if content:
                    saved_results[country_code] = content
        self.results_areas.clear()
        countries = {}
        for session_file in session_files:
            country_code, country_name = self.get_country_by_phone(session_file)
            if country_code:
                countries[country_code] = country_name
        main_container = QWidget()
        grid_layout = QGridLayout(main_container)
        grid_layout.setSpacing(10)
        max_columns = 5
        for i, (country_code, country_name) in enumerate(countries.items()):
            row = i // max_columns
            col = i % max_columns
            country_container = QWidget()
            column_layout = QVBoxLayout(country_container)
            column_layout.setContentsMargins(5, 5, 5, 5)
            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(5)
            flag_widget = self.get_flag_label(country_code, size=16, show_code=False)
            header_layout.addWidget(flag_widget)
            country_label = QLabel(country_name)
            country_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            country_label.setStyleSheet("font-weight: bold;")
            header_layout.addWidget(country_label)
            header_layout.addStretch()
            column_layout.addWidget(header_widget)
            text_area = QTextEdit()
            text_area.setReadOnly(True)
            font = text_area.font()
            font.setPointSize(10)
            text_area.setFont(font)
            if country_code in saved_results:
                text_area.setText(saved_results[country_code])
            text_area.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            text_area.document().setDocumentMargin(5)
            text_area.setFrameShape(QTextEdit.Shape.Box)
            text_area.setMinimumWidth(200)
            text_area.setMinimumHeight(250)
            column_layout.addWidget(text_area)
            grid_layout.addWidget(country_container, row, col)
            self.results_areas[country_code] = text_area
        self.results_layout.addWidget(main_container)
    def update_search_results(self, session_name: str, results: str, *args, **kwargs):
        country_code, country_name = self.get_country_by_phone(session_name)
        session_basename = os.path.basename(session_name)
        session_info = f"\n[Сессия: {session_basename}]"
        results_with_session = results + session_info
        if country_code and country_code in self.results_areas:
            current_text = self.results_areas[country_code].toPlainText()
            if current_text:
                if session_basename in current_text:
                    pass
                else:
                    self.results_areas[country_code].append("\n---\n" + results_with_session)
            else:
                self.results_areas[country_code].setText(results_with_session)
        else:
            saved_results = {}
            for code, text_area in self.results_areas.items():
                content = text_area.toPlainText()
                if content:
                    saved_results[code] = content
            if country_code:
                saved_results[country_code] = results_with_session
            else:
                unknown_key = f"unknown_{len(saved_results)}"
                saved_results[unknown_key] = results_with_session
                country_code = unknown_key
                if not country_name:
                    country_name = "Неизвестная страна"
            selected_sessions = self.session_window.get_selected_sessions()
            countries = {}
            for session_file in selected_sessions:
                code, name = self.get_country_by_phone(session_file)
                if code:
                    countries[code] = name
            if country_code and country_code not in countries:
                countries[country_code] = country_name
            self.prepare_results_areas(selected_sessions, saved_results)
    def clear_results(self, *args, **kwargs):
        for text_area in self.results_areas.values():
            text_area.clear()
    def get_flag_label(self, country_code, size=16, show_code=True):
        if not country_code or country_code == "XX":
            country_code = "xx"
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flag_path = os.path.join("icons", f"{country_code.lower()}.png")
        if os.path.exists(flag_path):
            pixmap = QPixmap(flag_path)
            pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            flag_label = QLabel()
            flag_label.setPixmap(pixmap)
            flag_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(flag_label)
        if show_code:
            code_label = QLabel(country_code.upper())
            code_label.setStyleSheet("font-size: 10px;")
            code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(code_label)
        return widget
    def get_country_by_phone(self, session_file: str, *args) -> tuple:
        json_file = session_file.replace('.session', '.json')
        full_path = os.path.join(self.session_folder, json_file)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
                phone = session_data.get('phone', '')
                if phone:
                    phone = phone.lstrip('+')
                    codes = {
                        '1': ('us', "США"),
                        '7': ('ru', "Россия"),
                        '380': ('ua', "Украина"),
                        '49': ('de', "Германия"),
                        '44': ('gb', "Великобритания"),
                        '33': ('fr', "Франция"),
                        '39': ('it', "Италия"),
                        '34': ('es', "Испания"),
                        '31': ('nl', "Нидерланды"),
                        '48': ('pl', "Польша"),
                        '91': ('in', "Индия"),
                        '86': ('cn', "Китай"),
                        '81': ('jp', "Япония"),
                        '82': ('kr', "Южная Корея"),
                        '55': ('br', "Бразилия"),
                        '52': ('mx', "Мексика"),
                        '61': ('au', "Австралия"),
                        '64': ('nz', "Новая Зеландия"),
                        '27': ('za', "ЮАР"),
                        '20': ('eg', "Египет"),
                        '966': ('sa', "Саудовская Аравия"),
                        '971': ('ae', "ОАЭ"),
                        '90': ('tr', "Турция"),
                        '30': ('gr', "Греция"),
                        '46': ('se', "Швеция"),
                        '47': ('no', "Норвегия"),
                        '45': ('dk', "Дания"),
                        '358': ('fi', "Финляндия"),
                        '420': ('cz', "Чехия"),
                        '36': ('hu', "Венгрия"),
                        '43': ('at', "Австрия"),
                        '41': ('ch', "Швейцария"),
                        '32': ('be', "Бельгия"),
                        '351': ('pt', "Португалия"),
                        '353': ('ie', "Ирландия"),
                        '972': ('il', "Израиль"),
                        '375': ('by', "Беларусь"),
                        '381': ('rs', "Сербия"),
                        '40': ('ro', "Румыния"),
                        '359': ('bg', "Болгария"),
                        '372': ('ee', "Эстония"),
                        '371': ('lv', "Латвия"),
                        '370': ('lt', "Литва"),
                        '994': ('az', "Азербайджан"),
                        '374': ('am', "Армения"),
                        '995': ('ge', "Грузия"),
                        '998': ('uz', "Узбекистан"),
                        '996': ('kg', "Киргизия"),
                        '992': ('tj', "Таджикистан"),
                        '993': ('tm', "Туркменистан"),
                        '976': ('mn', "Монголия")
                    }
                    for code in sorted(codes.keys(), key=len, reverse=True):
                        if phone.startswith(code):
                            return codes[code]
                    code_match = re.match(r'^(\d{1,3})', phone)
                    if code_match:
                        code = code_match.group(1)
                        return (f"other_{code}", f"Страна с кодом +{code}")
        return (None, "Неизвестная страна")
    def on_config_changed(self, config: Dict[str, Any], *args):
        if 'SESSION_FOLDER' in config:
            old_folder = self.session_folder
            self.session_folder = config['SESSION_FOLDER']
            if hasattr(self, 'session_window'):
                self.session_window.update_session_folder(self.session_folder)
            else:
                self.session_window = SessionWindow(self.session_folder, self)
                self.session_window._default_selected = False
                self.session_window.sessions_updated.connect(self.on_sessions_updated)
                main_layout = self.centralWidget().layout()
                if main_layout:
                    main_layout.addWidget(self.session_window, 1)
