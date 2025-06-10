import asyncio, logging, os, random, re
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import User
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QGroupBox, QLabel,
    QLineEdit, QPushButton, QTextEdit, QSizePolicy, QHBoxLayout,
    QTabWidget, QFileDialog
)
from ui.okak import ErrorReportDialog
from ui.loader import load_config, load_proxy
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import (
    TelegramConnection
)
from ui.proxy_utils import parse_proxies_from_txt, load_proxy_from_list
from telethon.tl.functions.messages import ImportChatInviteRequest
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.mate import distributor, TaskType
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
async def unblock_user(client, user_id):
    try:
        await client(UnblockRequest(id=user_id))
    except Exception as e:
        print(f"Error while unblocking: {e}")
class SubscriptionProcess(BaseThread):
    task_done_signal = pyqtSignal(str)
    def __init__(self, parent, action, session_folder, session_file, bot_urls, proxy=None, *args):
        super().__init__(session_file=session_file, parent=parent)
        self.parent = parent
        self.action = action
        self.session_folder = session_folder
        self.session_file = session_file
        self.bot_urls = bot_urls
        self.proxy = proxy
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.emit_log)
    async def process(self, *args):
        if not self.running:
            self.task_done_signal.emit(self.session_file)
            return
        try:
            if self.action == "subscribe":
                await self._subscribe_or_unsubscribe(subscribe=True)
            else:
                await self._subscribe_or_unsubscribe(subscribe=False)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.emit_error(f"Ошибка: {str(e)}")
        finally:
            self.task_done_signal.emit(self.session_file)
    async def _subscribe_or_unsubscribe(self, subscribe=True):
        if not self.running:
            self.task_done_signal.emit(self.session_file)
            return
        success, me = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy), proxy=self.proxy)
        if not success or not me:
            self.task_done_signal.emit(self.session_file)
            return
        try:
            for i, bot_url in enumerate(self.bot_urls):
                if not self.running:
                    self.task_done_signal.emit(self.session_file)
                    return
                if i > 0:
                    await self.apply_delay()
                    if not self.running:
                        self.task_done_signal.emit(self.session_file)
                        return
                try:
                    if subscribe:
                        await self._handle_subscribe(bot_url)
                    else:
                        await self._handle_unsubscribe(bot_url)
                    self.task_done_signal.emit(self.session_file)
                except Exception as e:
                    self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка: {str(e)}")
                    self.task_done_signal.emit(self.session_file)
                if not self.running:
                    self.task_done_signal.emit(self.session_file)
                    break
        finally:
            if hasattr(self.connection, 'client') and self.connection.client:
                await self.connection.disconnect()
    async def _handle_subscribe(self, bot_url):
        if is_private_invite(bot_url):
            hash_part = extract_invite_hash(bot_url)
            if not hash_part:
                self.emit_log(f"❌ {os.path.basename(self.session_file)} | Недействительная приватная ссылка: {bot_url}")
                return
            try:
                updates = await self.connection.client(ImportChatInviteRequest(hash_part))
                chat_id = updates.chats[0].id if hasattr(updates, 'chats') and updates.chats else None
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Вступили по приватной ссылке: {bot_url}")
                if self.parent.send_messages_checkbox.isChecked() and chat_id:
                    message = TaskWidget.generate_random_message()
                    await self.connection.client.send_message(chat_id, message)
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Отправлено сообщение в чат: {message}")
            except Exception as e:
                self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка приватной ссылки: {str(e)}")
        elif bot_url.endswith("bot"):
            try:
                await self.connection.client.send_message(bot_url, '/start')
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Отправлен /start боту {bot_url}")
                if self.parent.send_messages_checkbox.isChecked():
                    message = TaskWidget.generate_random_message()
                    await self.connection.client.send_message(bot_url, message)
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Отправлено сообщение боту {bot_url}: {message}")
            except Exception as e:
                self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка отправки /start: {str(e)}")
        else:
            try:
                entity = await self.connection.client.get_entity(bot_url)
                await self.connection.client(JoinChannelRequest(bot_url))
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Подписан на {bot_url}")
                if self.parent.send_messages_checkbox.isChecked():
                    message = TaskWidget.generate_random_message()
                    await self.connection.client.send_message(bot_url, message)
                    self.emit_log(f"✅ {os.path.basename(self.session_file)} | Отправлено сообщение в {bot_url}: {message}")
            except Exception as e:
                self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка подписки: {str(e)}")
    async def _handle_unsubscribe(self, bot_url):
        try:
            entity = await self.connection.client.get_entity(bot_url)
            if isinstance(entity, User) and entity.bot:
                await self.connection.client(BlockRequest(id=bot_url))
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Заблокирован бот {bot_url}")
                await self.connection.client.delete_dialog(bot_url)
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Удален диалог с ботом {bot_url}")
            else:
                await self.connection.client.delete_dialog(bot_url)
                self.emit_log(f"✅ {os.path.basename(self.session_file)} | Удален диалог с {bot_url}")
        except Exception as e:
            self.emit_log(f"❌ {os.path.basename(self.session_file)} | Ошибка отписки: {str(e)}")
class TaskWidget(QWidget, ThreadStopMixin):
    def __init__(self, session_folder, main_window, task_name, *args):
        super().__init__(*args)
        ThreadStopMixin.__init__(self)
        self.main_window = main_window
        self.session_folder = session_folder
        self.task_name = task_name
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
        self.distribute_tasks_checkbox = QCheckBox("Распределить задачи между сессиями (новый)")
        left_layout.addWidget(self.distribute_tasks_checkbox)
        url_controls = QHBoxLayout()
        self.import_urls_button = QPushButton("Импорт из файла", self)
        self.clear_url_button = QPushButton("Очистить", self)
        self.import_urls_button.clicked.connect(self.import_urls_from_file)
        self.clear_url_button.clicked.connect(self.clear_url_input)
        url_controls.addWidget(self.import_urls_button)
        url_controls.addWidget(self.clear_url_button)
        left_layout.addLayout(url_controls)
        self.url_input = QTextEdit(self)
        self.url_input.setPlaceholderText("Введите ссылки на ботов или каналы (каждая с новой строки)")
        self.url_input.setMinimumHeight(120)
        self.url_input.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.url_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.url_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        left_layout.addWidget(self.url_input)
        delay_layout = QHBoxLayout()
        self.min_delay_input = QLineEdit(self)
        self.max_delay_input = QLineEdit(self)
        self.min_delay_input.setPlaceholderText("Мин. (сек)")
        self.max_delay_input.setPlaceholderText("Макс. (сек)")
        delay_layout.addWidget(QLabel("Задержка:"))
        delay_layout.addWidget(self.min_delay_input)
        delay_layout.addWidget(self.max_delay_input)
        left_layout.addLayout(delay_layout)
        self.send_messages_checkbox = QCheckBox("Отправлять сообщения")
        self.send_messages_checkbox.setChecked(True)
        left_layout.addWidget(self.send_messages_checkbox)
        control_layout = QHBoxLayout()
        self.subscribe_button = QPushButton("▶ Подписаться", self)
        self.unsubscribe_button = QPushButton("▶ Отписаться", self)
        self.finish_button = QPushButton("⏹ Завершить", self)
        self.subscribe_button.clicked.connect(self.start_subscription)
        self.unsubscribe_button.clicked.connect(self.start_unsubscription)
        self.finish_button.clicked.connect(self.stop_process)
        control_layout.addWidget(self.subscribe_button)
        control_layout.addWidget(self.unsubscribe_button)
        control_layout.addWidget(self.finish_button)
        left_layout.addLayout(control_layout)
        self.delay_label = QLabel("Текущая задержка: 0 сек", self)
        left_layout.addWidget(self.delay_label)
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        left_layout.addWidget(self.log_area)
        self.progress_widget = ProgressWidget(self)
        left_layout.addWidget(self.progress_widget)
        self.session_window = SessionWindow(session_folder, self)
        self.session_window.sessions_updated.connect(self.on_sessions_updated)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addWidget(self.session_window, 1)
        self.setLayout(main_layout)
        self.bot_urls = []
        self.proxies_list = []
        self.proxy_txt_path = None
        self.use_proxy_txt_checkbox.toggled.connect(self.on_use_proxy_txt_toggled)
        self.distribute_tasks_checkbox.toggled.connect(self.on_distribute_tasks_toggled)
        self.new_distribution_active = False
        self.total_threads = 0
        self.completed_threads = 0
    def on_sessions_updated(self, valid_sessions, *args):
        self.subscribe_button.setEnabled(bool(valid_sessions))
        self.unsubscribe_button.setEnabled(bool(valid_sessions))
    def show_error_dialog(self, error_message, *args):
        QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(None, error_text=error_message))
    def clean_telegram_link(self, value, *args):
        value = value.strip()
        if value.startswith('@'):
            value = value[1:]
        value = re.sub(r'^https?://t\.me/(s/)?', '', value)
        if value.startswith('+') or re.match(r'^[a-zA-Z0-9_-]{16,}$', value):
            return value
        return value.lower()
    def on_use_proxy_txt_toggled(self, checked, *args):
        if checked:
            file_path, _ = QFileDialog.getOpenFileName(self, "Выберите txt-файл с прокси", "", "Text Files (*.txt)")
            if file_path:
                self.proxy_txt_path = file_path
                self.proxies_list = parse_proxies_from_txt(file_path)
                self.append_log(f"✅ Загружено прокси из файла: {len(self.proxies_list)}")
            else:
                self.use_proxy_txt_checkbox.setChecked(False)
        else:
            self.proxy_txt_path = None
            self.proxies_list = []
    def on_distribute_tasks_toggled(self, checked):
        self.new_distribution_active = checked
        selected_sessions = self.session_window.get_selected_sessions()
        self.subscribe_button.setEnabled(bool(selected_sessions))
        self.unsubscribe_button.setEnabled(bool(selected_sessions))
    async def start_processes_async(self, action, *args):
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions:
            self.append_log("Ошибка: не выбраны сессии.")
            return
        input_text = self.url_input.toPlainText().strip()
        if not input_text:
            self.append_log(f"Ошибка: не введены ссылки для {action}.")
            return
        lines = [line.strip() for line in input_text.split('\n')]
        raw_urls = []
        for line in lines:
            if not line:
                continue
            if ',' in line:
                urls_in_line = [url.strip() for url in line.split(',') if url.strip()]
                raw_urls.extend(urls_in_line)
            else:
                raw_urls.append(line)
        self.bot_urls = [self.clean_telegram_link(url) for url in raw_urls if url.strip()]
        if not self.bot_urls:
            self.append_log(f"Ошибка: не введены корректные ссылки для {action}.")
            return
        self.append_log(f"Найдено {len(self.bot_urls)} ссылок для обработки:")
        for i, url in enumerate(self.bot_urls, 1):
            self.append_log(f"{i}. {url}")
        self.new_distribution_active = self.distribute_tasks_checkbox.isChecked()
        if self.new_distribution_active:
            distributor.set_sessions(selected_sessions)
            distributor.set_items(self.bot_urls, TaskType.SUBSCRIBE)
            self.append_log("INFO: Новое распределение: ссылки на ботов/каналы разделены между сессиями.")
        use_proxy = self.use_proxy_checkbox.isChecked()
        use_proxy_txt = self.use_proxy_txt_checkbox.isChecked()
        threads = []
        self.proxies_list = self.proxies_list or []
        for idx, session_file in enumerate(selected_sessions):
            proxy = None
            if use_proxy_txt and self.proxies_list:
                proxy = load_proxy_from_list(idx, self.proxies_list)
                if proxy:
                    self.append_log(f"🌐 [{session_file}] Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}")
            elif use_proxy:
                config = load_config()
                proxy = load_proxy(config)
                if proxy:
                    self.append_log(f"🌐 [{session_file}] Используется прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.append_log(f"ℹ️ [{session_file}] Прокси не используется")
            urls_for_thread = self.bot_urls
            if self.new_distribution_active:
                urls_for_thread = distributor.get_session_items(session_file)
            if not urls_for_thread:
                continue
            thread = self.create_subscription_process(action, session_file, proxy)
            thread.task_done_signal.connect(self.on_task_done)
            thread.delay_signal.connect(self.update_delay_label, Qt.ConnectionType.QueuedConnection)
            threads.append(thread)
        self.total_threads = len(threads)
        self.completed_threads = 0
        self.progress_widget.update_progress(0, f"Выполняется задача для {self.total_threads} сессий...")
        min_delay, max_delay = self.get_delay_range()
        if min_delay is not None and max_delay is not None and min_delay > 0 and max_delay > 0:
            self.append_log("Запуск потоков последовательно с задержкой...")
            self.start_threads_with_delay(threads, min_delay, max_delay)
        else:
            self.append_log("Запуск потоков параллельно...")
            for thread in threads:
                self.thread_manager.start_thread(thread)
    def create_subscription_process(self, action, session_file, proxy=None, *args):
        urls_for_thread = self.bot_urls
        if self.new_distribution_active:
            urls_for_thread = distributor.get_session_items(session_file)
            self.append_log(f"DEBUG: Сессия {session_file} получила {len(urls_for_thread)} ссылок от нового распределителя.")
        thread = SubscriptionProcess(
            self,
            action,
            self.session_window.session_folder,
            session_file,
            urls_for_thread,
            proxy
        )
        thread.log_signal.connect(self.append_log)
        thread.error_signal.connect(self.show_error_dialog)
        thread.done_signal.connect(lambda: self._on_thread_finished(thread))
        min_delay, max_delay = self.get_delay_range()
        thread.set_delay_range(min_delay if min_delay is not None else 0, max_delay if max_delay is not None else 0)
        thread.delay_signal.connect(self.update_delay_label, Qt.ConnectionType.QueuedConnection)
        return thread
    def _on_thread_finished(self, thread, *args):
        pass
    def on_task_done(self, session_file, *args):
        if not hasattr(self, '_already_done'):
            self._already_done = set()
        if session_file in self._already_done:
            return
        self._already_done.add(session_file)
        self.completed_threads += 1
        percent = int((self.completed_threads / self.total_threads) * 100) if self.total_threads else 100
        self.progress_widget.update_progress(percent, f"Выполнено {self.completed_threads} из {self.total_threads} сессий")
        if self.completed_threads >= self.total_threads:
            self.append_log("✅ Все задачи завершены.")
            self.progress_widget.update_progress(100, "Задача завершена.")
            self.subscribe_button.setEnabled(True)
            self.unsubscribe_button.setEnabled(True)
    def start_subscription(self, *args):
        self.subscribe_button.setEnabled(False)
        self.unsubscribe_button.setEnabled(False)
        self.log_area.clear()
        self.append_log("Начинаем процесс подписки...")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.start_processes_async("subscribe"))
        else:
            loop.run_until_complete(self.start_processes_async("subscribe"))
    def start_unsubscription(self, *args):
        self.subscribe_button.setEnabled(False)
        self.unsubscribe_button.setEnabled(False)
        self.log_area.clear()
        self.append_log("Начинаем процесс отписки...")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.start_processes_async("unsubscribe"))
        else:
            loop.run_until_complete(self.start_processes_async("unsubscribe"))
    def append_log(self, message, *args):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
    @staticmethod
    def generate_random_message(*args):
        templates = [
            "Привет! Подскажите, где найти {} для {}?",
            "Здравствуйте, есть ли возможность подключить {} через {}?",
            "Интересует, как работает {} в связке с {}?",
            "Можно ли использовать {} вместе с {}?",
            "Добрый день! Хочу узнать про {} для {}.",
            "Как получить {} через {}?",
            "Сколько стоит {} и будет ли оно работать на {}?",
            "Планирую использовать {}. Подойдет ли оно для {}?",
            "Есть ли акция на {} через {}?",
            "Где можно активировать {} с помощью {}?",
            "Хочу заказать {}. Посоветуйте, если есть через {}.",
            "А как быстро оформить {} через {}?",
            "Подскажите, поддерживает ли {} работу с {}?",
            "Какие условия подписки на {} для {}?",
            "Можно ли подключить {} к {} без лишних затрат?",
            "Ищу лучшее предложение на {} для {}.",
            "Что лучше выбрать: {} или {}?",
            "Как настроить {} для работы с {}?",
            "Можно оплатить {} через {}?",
            "Будет ли скидка на {} если использовать {}?",
            "Как быстрее получить {} через {}?",
            "У кого-то есть опыт с {} через {}?",
            "Насколько стабильно работает {} в {}?",
            "Какие плюсы и минусы у {} при использовании {}?",
            "Хочу протестировать {} на {}. Есть советы?"
        ]
        words = [
            "музыка", "бот", "функция", "подписка", "сервис", "реклама",
            "чат", "интеграция", "премиум", "доступ", "программа", "аккаунт",
            "интернет", "платформа", "мобильное приложение", "API", "рассылка",
            "веб-интерфейс", "подключение", "сессия", "канал", "группа", "профиль", "авторизация"
        ]
        random.shuffle(words)
        return random.choice(templates).format(random.choice(words), random.choice(words))
    def stop_process(self, *args):
        self.stop_all_operations()
        self.subscribe_button.setEnabled(True)
        self.unsubscribe_button.setEnabled(True)
        self.append_log("Процесс остановлен.")
        self.progress_widget.update_progress(100, "Процесс остановлен")
        self.bot_urls = []
    def clear_url_input(self, *args):
        self.url_input.clear()
    def import_urls_from_file(self, *args):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл со ссылками",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                urls = file.read()
                current_text = self.url_input.toPlainText()
                if current_text and not current_text.endswith('\n'):
                    self.url_input.setPlainText(current_text + '\n' + urls)
                else:
                    self.url_input.setPlainText(current_text + urls)
            self.append_log(f"✅ Ссылки импортированы из файла: {file_path}")
        except Exception as e:
            self.append_log(f"❌ Ошибка при импорте ссылок из файла: {str(e)}")
    def update_delay_label(self, delay, *args):
        self.delay_label.setText(f"Текущая задержка: {delay} сек")
    def get_delay_range(self, *args):
        try:
            min_delay = int(self.min_delay_input.text()) if self.min_delay_input.text().strip() else 0
            max_delay = int(self.max_delay_input.text()) if self.max_delay_input.text().strip() else 0
            return min_delay, max_delay
        except ValueError as e:
            self.append_log(str(e))
            return None, None
class SubscribeWindow(QWidget):
    def __init__(self, session_folder, main_window, *args):
        super().__init__(*args)
        self.main_window = main_window
        self.session_folder = session_folder
        self.setWindowTitle("Подписка/Отписка на ботов")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(900, 700)
        main_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 0; }
            QTabWidget::tab-bar { border: 0; }
        """)
        self.task1 = TaskWidget(session_folder, main_window, "Задача 1")
        self.task2 = TaskWidget(session_folder, main_window, "Задача 2")
        self.tab_widget.addTab(self.task1, "Задача 1")
        self.tab_widget.addTab(self.task2, "Задача 2")
        main_layout.addWidget(self.tab_widget)
        self.setLayout(main_layout)
        if hasattr(self.main_window, 'config_changed'):
            self.main_window.config_changed.connect(self.task1.session_window.on_config_changed)
            self.main_window.config_changed.connect(self.task2.session_window.on_config_changed)
def is_private_invite(link: str) -> bool:
    link = link.strip()

    return (
        link.startswith('+') or
        link.startswith('joinchat/') or
        't.me/+' in link or
        't.me/joinchat/' in link
    )
def extract_invite_hash(link: str) -> str | None:
    link = link.strip()
    m = re.match(r'(?:https?://)?t\.me/\+([a-zA-Z0-9_-]+)', link)
    if m:
        return m.group(1)
    m = re.match(r'(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_-]+)', link)
    if m:
        return m.group(1)
    m = re.match(r'^\+([a-zA-Z0-9_-]+)$', link)
    if m:
        return m.group(1)
    m = re.match(r'^joinchat/([a-zA-Z0-9_-]+)$', link)
    if m:
        return m.group(1)
    return None
