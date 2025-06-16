import os, asyncio, json, logging, time
from typing import Dict, List, Set, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QPushButton, 
    QTextEdit, QHBoxLayout, QCheckBox, QMessageBox,
    QGroupBox, QWidget, QComboBox
)
from PyQt6.QtCore import pyqtSignal

from ui.thread_base import ThreadStopMixin, BaseThread
from ui.session_win import SessionWindow
from ui.progress import ProgressWidget
from ui.apphuy import TelegramConnection
from ui.okak import ErrorReportDialog
from telethon import functions
class BotTransferThread(BaseThread):
    task_done_signal = pyqtSignal(str, bool)
    transfer_result_signal = pyqtSignal(str, bool, str)
    def __init__(self, parent, session_folder, session_file, bot_token, bot_username, target_username, proxy=None):
        super().__init__(session_file=session_file, parent=parent)
        self.parent = parent
        self.session_folder = session_folder
        self.session_file = session_file
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.target_username = target_username
        self.proxy = proxy
        self.connection = TelegramConnection(self.session_folder)
        self.connection.log_signal.connect(self.emit_log)
        self.connection.error_signal.connect(self.emit_error)
        self.connection.flood_wait_signal.connect(lambda s, t: self.emit_log(f"⏳ {os.path.basename(s)} | Flood wait {t} сек."))
        self.debug_mode = False
    def emit_error(self, session_file, error, *args):
        error_message = f"Ошибка: {error.message}"
        self.emit_log(f"❌ {os.path.basename(session_file)} | {error_message}")
        self.transfer_result_signal.emit(self.bot_username, False, error_message)
    def _get_button_type(self, button, *args):
        if hasattr(button, 'data'):
            return "callback", button.data
        elif hasattr(button, 'url'):
            return "url", button.url
        elif hasattr(button, 'text'):
            return "text", button.text
        else:
            return "unknown", None    
    async def process(self, *args):
        if not self.running:
            self.task_done_signal.emit(self.session_file, False)
            return
        success, me = await self.connection.connect(self.session_file, use_proxy=bool(self.proxy), proxy=self.proxy)
        if not success or not me:
            self.transfer_result_signal.emit(self.bot_username, False, "Не удалось подключиться к сессии")
            self.task_done_signal.emit(self.session_file, False)
            return            
        try:
            result = await self._process_bot_transfer()
            self.task_done_signal.emit(self.session_file, result)
        except Exception as e:
            self.emit_log(f"❌ Ошибка при передаче бота @{self.bot_username}: {str(e)}")
            self.transfer_result_signal.emit(self.bot_username, False, f"Ошибка: {str(e)}")
            self.task_done_signal.emit(self.session_file, False)
        finally:
            if hasattr(self.connection, 'client') and self.connection.client:
                await self.connection.disconnect()
    async def _wait_for_botfather_event(self, bf, expected_buttons=None, expected_text=None, timeout=60, poll_interval=2, *args):
        start_time = time.time()
        if isinstance(expected_buttons, str):
            expected_buttons = [expected_buttons]
        if isinstance(expected_text, str):
            expected_text = [expected_text]
        while time.time() - start_time < timeout:
            async for message in self.connection.client.iter_messages(bf, limit=5):
                if expected_text:
                    for phrase in expected_text:
                        if message.text and phrase.lower() in message.text.lower():
                            return message
                if expected_buttons and hasattr(message, 'reply_markup') and message.reply_markup and hasattr(message.reply_markup, 'rows'):
                    for row in message.reply_markup.rows:
                        for button in row.buttons:
                            button_text = getattr(button, 'text', '')
                            for expected in expected_buttons:
                                if expected.lower() in button_text.lower():
                                    return message
                if message.text and (
                    'oops!' in message.text.lower() or
                    'flood' in message.text.lower() or
                    'error' in message.text.lower() or
                    'ошибка' in message.text.lower()
                ):
                    return message
            await asyncio.sleep(poll_interval)
        return None
    async def _process_bot_transfer(self, *args):
        try:
            bf = await self.connection.client.get_entity('BotFather')
            if not bf:
                self.emit_log(f"❌ Не удалось найти BotFather")
                self.transfer_result_signal.emit(self.bot_username, False, "Не удалось найти BotFather")
                return False
            self.emit_log(f"🤖 Отправляем команду /mybots в BotFather")
            await self.connection.client.send_message(bf, "/mybots")
            msg = await self._wait_for_botfather_event(bf, expected_buttons=self.bot_username, timeout=30)
            if not msg:
                self.emit_log(f"❌ Не получили список ботов от BotFather")
                self.transfer_result_signal.emit(self.bot_username, False, "BotFather не вернул список ботов")
                return False
            self.emit_log(f"🔍 Ищем и нажимаем на бота @{self.bot_username}")
            found = False
            for row in msg.reply_markup.rows:
                for button in row.buttons:
                    if self.bot_username.replace('@','').lower() in button.text.lower():
                        await self._press_button(bf, msg, button, button.text)
                        found = True
                        break
                if found:
                    break
            if not found:
                self.emit_log(f"❌ Не нашли бота @{self.bot_username} в списке")
                self.transfer_result_signal.emit(self.bot_username, False, "Бот не найден в списке BotFather")
                return False
            msg = await self._wait_for_botfather_event(bf, expected_buttons=["Transfer ownership", "Передать права"], timeout=30)
            if not msg:
                self.emit_log(f"❌ Не получили меню управления ботом")
                self.transfer_result_signal.emit(self.bot_username, False, "BotFather не вернул меню управления ботом")
                return False
            self.emit_log(f"🔍 Нажимаем Transfer Ownership")
            pressed = False
            for row in msg.reply_markup.rows:
                for button in row.buttons:
                    if "transfer" in button.text.lower() or "передать" in button.text.lower():
                        await self._press_button(bf, msg, button, button.text)
                        pressed = True
                        break
                if pressed:
                    break
            if not pressed:
                self.emit_log(f"❌ Не нашли кнопку Transfer Ownership")
                self.transfer_result_signal.emit(self.bot_username, False, "Кнопка Transfer Ownership не найдена")
                return False
            msg = await self._wait_for_botfather_event(bf, expected_buttons=["Choose recipient", "Выбрать получателя"], timeout=30)
            if not msg:
                self.emit_log(f"❌ Не получили меню выбора получателя")
                self.transfer_result_signal.emit(self.bot_username, False, "BotFather не вернул меню выбора получателя")
                return False
            self.emit_log(f"🔍 Нажимаем Choose recipient")
            pressed = False
            for row in msg.reply_markup.rows:
                for button in row.buttons:
                    if "choose" in button.text.lower() or "выбрать" in button.text.lower():
                        await self._press_button(bf, msg, button, button.text)
                        pressed = True
                        break
                if pressed:
                    break
            if not pressed:
                self.emit_log(f"❌ Не нашли кнопку Choose recipient")
                self.transfer_result_signal.emit(self.bot_username, False, "Кнопка Choose recipient не найдена")
                return False
            msg = await self._wait_for_botfather_event(bf, expected_text=["please share the new owner's contact", "укажите контакт нового владельца", "username"], timeout=30)
            if not msg:
                self.emit_log(f"❌ Не получили запрос на username нового владельца")
                self.transfer_result_signal.emit(self.bot_username, False, "BotFather не запросил username нового владельца")
                return False
            target_username = self.target_username
            if not target_username.startswith('@'):
                target_username = '@' + target_username
            self.emit_log(f"🤖 Отправляем username нового владельца: {target_username}")
            await self.connection.client.send_message(bf, target_username)
            msg = await self._wait_for_botfather_event(bf, expected_buttons=["yes", "sure", "proceed", "да", "подтверждаю"], expected_text=["you are about to transfer", "вы собираетесь передать"], timeout=30)
            if not msg:
                self.emit_log(f"❌ Не получили подтверждение передачи")
                self.transfer_result_signal.emit(self.bot_username, False, "BotFather не прислал подтверждение передачи")
                return False
            self.emit_log(f"🔍 Нажимаем YES, I am sure, proceed")
            pressed = False
            for row in msg.reply_markup.rows:
                for button in row.buttons:
                    if "yes" in button.text.lower() or "sure" in button.text.lower() or "proceed" in button.text.lower() or "да" in button.text.lower():
                        await self._press_button(bf, msg, button, button.text)
                        pressed = True
                        break
                if pressed:
                    break
            if not pressed:
                self.emit_log(f"❌ Не нашли кнопку подтверждения передачи")
                self.transfer_result_signal.emit(self.bot_username, False, "Кнопка подтверждения передачи не найдена")
                return False
            msg = await self._wait_for_botfather_event(bf, expected_text=["enter your password", "введите пароль", "two-step verification", "двухэтапная"], timeout=15)
            if msg:
                self.emit_log(f"🔑 Вводим пароль 2FA")
                twofa = await self._get_2fa_password()
                if not twofa:
                    self.emit_log(f"❌ Не удалось получить пароль 2FA")
                    self.transfer_result_signal.emit(self.bot_username, False, "Не удалось получить пароль 2FA")
                    return False
                await self.connection.client.send_message(bf, twofa)
            msg = await self._wait_for_botfather_event(bf, expected_text=["success", "успешно", "transferred", "передан"], timeout=30)
            if msg:
                self.emit_log(f"✅ Бот @{self.bot_username} успешно передан пользователю {self.target_username}")
                self.transfer_result_signal.emit(self.bot_username, True, f"Бот успешно передан пользователю {self.target_username}")
                return True
            else:
                msg = await self._wait_for_botfather_event(bf, expected_text=["oops", "ошибка", "error"], timeout=5)
                if msg:
                    self.emit_log(f"❌ Ошибка при передаче бота: {msg.text}")
                    self.transfer_result_signal.emit(self.bot_username, False, f"Ошибка: {msg.text}")
                    return False
                self.emit_log(f"❌ Не удалось подтвердить успешную передачу бота")
                self.transfer_result_signal.emit(self.bot_username, False, f"Не удалось подтвердить успешную передачу бота")
                return False
        except Exception as e:
            self.emit_log(f"❌ Ошибка при передаче бота: {str(e)}")
            self.transfer_result_signal.emit(self.bot_username, False, f"Ошибка: {str(e)}")
            return False
    async def _get_2fa_password(self, *args):
        try:
            json_path = os.path.join(self.session_folder, os.path.basename(self.session_file).replace('.session', '.json'))
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    twofa = data.get('twoFA', '')
                    if twofa:
                        return twofa
            
            self.emit_log(f"⚠️ Пароль 2FA не найден в JSON файле")
            return None
        except Exception as e:
            self.emit_log(f"❌ Ошибка при получении пароля 2FA: {str(e)}")
            return None
    async def _press_button(self, peer, message, button, button_text, *args):
        button_type, button_value = self._get_button_type(button)
        if self.debug_mode:
            self.emit_log(f"🔍 Тип кнопки: {button_type}, Значение: {button_value}")
            if hasattr(button, '__dict__'):
                self.emit_log(f"🔍 Атрибуты кнопки: {str(button.__dict__)}")
        if button_type == "callback" and hasattr(button, 'data') and button.data:
            try:
                await self.connection.client(functions.messages.GetBotCallbackAnswerRequest(
                    peer=peer,
                    msg_id=message.id,
                    data=button.data
                ))
                self.emit_log(f"✅ Нажата inline-кнопка: {button_text}")
                return True
            except Exception as e:
                self.emit_log(f"❌ Ошибка при нажатии inline-кнопки: {str(e)}")
                return False
        if button_type == "text" and button_text:
            try:
                await self.connection.client.send_message(peer, button_text)
                self.emit_log(f"✅ Отправлен текст обычной кнопки: {button_text}")
                return True
            except Exception as e:
                self.emit_log(f"❌ Ошибка при отправке текста кнопки: {str(e)}")
                return False
        if button_type == "url" and hasattr(button, 'url'):
            self.emit_log(f"ℹ️ URL-кнопка: {button.url}")
            return False
        self.emit_log(f"⚠️ Неизвестный тип кнопки, не отправляем ничего: {button_text}")
        return False
class BotTransferDialog(QDialog, ThreadStopMixin):
    def __init__(self, selected_tokens, selected_usernames, session_folder, parent=None):
        super().__init__(parent)
        ThreadStopMixin.__init__(self)        
        self.selected_tokens = selected_tokens
        self.selected_usernames = selected_usernames
        self.session_folder = session_folder
        self.completed_transfers = 0
        self.total_transfers = len(selected_tokens)
        self.running = False        
        self.logger = logging.getLogger('BotTransferDialog')
        self.logger.setLevel(logging.INFO)        
        self.setup_ui()
    def setup_ui(self, *args):
        self.setWindowTitle("Передача бота")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout()
        if len(self.selected_tokens) > 1:
            bot_selection_group = QGroupBox("Выберите бота для передачи")
            bot_selection_layout = QVBoxLayout()            
            self.bot_combo = QComboBox()
            for username in self.selected_usernames:
                self.bot_combo.addItem(f"@{username}")            
            bot_selection_layout.addWidget(self.bot_combo)
            bot_selection_group.setLayout(bot_selection_layout)
            left_panel.addWidget(bot_selection_group)
        target_group = QGroupBox("Укажите имя пользователя для передачи")
        target_layout = QVBoxLayout()
        self.target_username_input = QLineEdit()
        self.target_username_input.setPlaceholderText("Введите @username нового владельца (с @ или без)")
        self.target_username_input.setToolTip("Укажите имя пользователя в Telegram, которому будет передан бот.\n"
                                           "Можно вводить как с символом @ в начале, так и без него.\n"
                                           "Важно: пользователь должен ранее отправить сообщение боту.")
        target_layout.addWidget(self.target_username_input)
        target_group.setLayout(target_layout)
        left_panel.addWidget(target_group)
        proxy_layout = QHBoxLayout()
        self.use_proxy_checkbox = QCheckBox("Использовать прокси")
        proxy_layout.addWidget(self.use_proxy_checkbox)
        left_panel.addLayout(proxy_layout)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("▶ Начать передачу")
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        left_panel.addLayout(button_layout)
        self.progress_widget = ProgressWidget(self)
        left_panel.addWidget(self.progress_widget)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        left_panel.addWidget(self.log_area)
        self.session_window = SessionWindow(session_folder=self.session_folder, parent=self)
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        main_layout.addWidget(left_widget, 3)
        main_layout.addWidget(self.session_window, 1)
        self.start_button.clicked.connect(self.handle_start)
        self.stop_button.clicked.connect(self.handle_stop)
        if len(self.selected_tokens) == 1:
            self.log_area.append(f"🤖 Выбран бот для передачи: @{self.selected_usernames[0]}")
        else:
            self.log_area.append(f"🤖 Выбрано ботов для передачи: {len(self.selected_tokens)}")
            for username in self.selected_usernames:
                self.log_area.append(f"  • @{username}")
    def handle_start(self, *args):
        if self.running:
            self.log_area.append("⚠️ Процесс уже запущен")
            return            
        target_username = self.target_username_input.text().strip()
        if not target_username:
            QMessageBox.warning(self, "Предупреждение", "Укажите имя пользователя для передачи")
            return
        if not target_username.startswith('@'):
            target_username = '@' + target_username
        selected_sessions = self.session_window.get_selected_sessions()
        if not selected_sessions:
            QMessageBox.warning(self, "Предупреждение", "Выберите сессию для выполнения передачи")
            return            
        use_proxy = self.use_proxy_checkbox.isChecked()
        proxy = None
        if use_proxy:
            from ui.loader import load_config, load_proxy
            config = load_config()
            proxy = load_proxy(config)
            if proxy:
                self.log_area.append(f"🌐 Используем прокси: {proxy.get('addr', 'не указан')}")
            else:
                self.log_area.append("⚠️ Прокси включен, но не настроен в конфигурации")        
        self.running = True
        self.completed_transfers = 0
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.target_username_input.setEnabled(False)
        self.session_window.setEnabled(False)
        if hasattr(self, 'bot_combo'):
            self.bot_combo.setEnabled(False)
        threads = []
        if hasattr(self, 'bot_combo') and self.bot_combo:
            selected_bot_idx = self.bot_combo.currentIndex()
            if selected_bot_idx >= 0 and selected_bot_idx < len(self.selected_tokens):
                token = self.selected_tokens[selected_bot_idx]
                username = self.selected_usernames[selected_bot_idx]
                session_file = selected_sessions[0]
                thread = BotTransferThread(
                    self,
                    self.session_folder,
                    session_file,
                    token,
                    username,
                    target_username,
                    proxy
                )                
                thread.log_signal.connect(self.log)
                thread.task_done_signal.connect(self.on_task_done)
                thread.transfer_result_signal.connect(self.on_transfer_result)                
                threads.append(thread)
                self.total_transfers = 1
        else:
            for idx, (token, username) in enumerate(zip(self.selected_tokens, self.selected_usernames)):
                session_file = selected_sessions[0] if idx < len(selected_sessions) else selected_sessions[0]
                thread = BotTransferThread(
                    self,
                    self.session_folder,
                    session_file,
                    token,
                    username,
                    target_username,
                    proxy
                )                
                thread.log_signal.connect(self.log)
                thread.task_done_signal.connect(self.on_task_done)
                thread.transfer_result_signal.connect(self.on_transfer_result)                
                threads.append(thread)
        self.total_threads = len(threads)
        self.progress_widget.progress_bar.setValue(0)
        self.progress_widget.status_label.setText(f"Выполняется задача для {self.total_transfers} ботов...")        
        for thread in threads:
            self.thread_manager.start_thread(thread)
    def handle_stop(self, *args):
        if not self.running:
            return            
        self.running = False
        self.log_area.append("⏹️ Останавливаем процесс...")
        self.stop_all_operations()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.target_username_input.setEnabled(True)
        self.session_window.setEnabled(True)
        if hasattr(self, 'bot_combo'):
            self.bot_combo.setEnabled(True)
        self.progress_widget.update_progress(100, "Остановлено")
        self.log_area.append("✅ Все процессы остановлены")
    def log(self, message, *args):
        self.log_area.append(message)
    def on_task_done(self, session_file, success, *args):
        self.completed_transfers += 1
        progress = int((self.completed_transfers / self.total_transfers) * 100)
        self.progress_widget.progress_bar.setValue(progress)
        self.progress_widget.status_label.setText(f"Выполнено {self.completed_transfers} из {self.total_transfers}")        
        if self.completed_transfers >= self.total_transfers:
            self.running = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.target_username_input.setEnabled(True)
            self.session_window.setEnabled(True)
            if hasattr(self, 'bot_combo'):
                self.bot_combo.setEnabled(True)
            self.progress_widget.update_progress(100, "Все задачи завершены")
            self.log_area.append(f"✅ Все {self.total_transfers} задач обработаны")    
    def on_transfer_result(self, bot_username, success, message):
        if success:
            self.log_area.append(f"✅ @{bot_username}: {message}")
        else:
            self.log_area.append(f"❌ @{bot_username}: {message}")
            try:
                ErrorReportDialog.send_error_report(None, error_text=f"Bot Transfer Error: @{bot_username} - {message}")
            except Exception as e:
                self.logger.error(f"Не удалось отправить отчет об ошибке: {e}")
    def closeEvent(self, event, *args):
        self.running = False
        self.log_area.append("Ожидание завершения процессов перед закрытием...")
        self.stop_all_operations()
        event.accept() 
