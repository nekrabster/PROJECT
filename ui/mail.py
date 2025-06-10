import asyncio
from email.mime.text import MIMEText
import aiosmtplib
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QListWidget, QMessageBox, QProgressBar, QSplitter, QWidget, QFrame
from PyQt6.QtCore import Qt, QThread, pyqtSignal
class MailSenderThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal()
    def __init__(self, accounts, recipients, subject, body):
        super().__init__()
        self.accounts = accounts
        self.recipients = recipients
        self.subject = subject
        self.body = body
    def run(self, *args):
        asyncio.run(self.async_send())
    async def async_send(self, *args):
        total = len(self.recipients)
        for i, recipient in enumerate(self.recipients):
            acc = self.accounts[i % len(self.accounts)]
            smtp_host, smtp_port, login, password = acc
            message = MIMEText(self.body)
            message["From"] = login
            message["To"] = recipient
            message["Subject"] = self.subject
            try:
                await aiosmtplib.send(
                    message,
                    hostname=smtp_host,
                    port=int(smtp_port),
                    start_tls=True,
                    username=login,
                    password=password,
                )
                self.log_signal.emit(f"✅ {login} → {recipient} — отправлено")
            except Exception as e:
                error_msg = str(e)
                if "Username and Password not accepted" in error_msg and "gmail" in smtp_host.lower():
                    self.log_signal.emit(f"❌ {login} → {recipient} — ошибка аутентификации Gmail")
                    self.log_signal.emit("⚠️ Для Gmail требуется пароль приложения:")
                    self.log_signal.emit("1. Включите двухфакторную аутентификацию в настройках безопасности Google")
                    self.log_signal.emit("2. Создайте пароль приложения: Google Аккаунт → Безопасность → Пароли приложений")
                    self.log_signal.emit("3. Используйте созданный 16-значный код вместо обычного пароля")
                    self.log_signal.emit(f"4. Подробнее: https://support.google.com/mail/?p=BadCredentials")
                else:
                    self.log_signal.emit(f"❌ {login} → {recipient} — ошибка: {e}")
            self.progress_signal.emit(i + 1, total)
            await asyncio.sleep(0.5)
        self.finished_signal.emit()
class MailWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Работа с почтой")
        self.setMinimumSize(700, 500)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        content_container = QSplitter(Qt.Orientation.Horizontal)
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        files_group = QFrame()
        files_group.setFrameShape(QFrame.Shape.StyledPanel)
        files_layout = QVBoxLayout(files_group)
        self.accounts_btn = QPushButton("📂 Загрузить аккаунты почты", self)
        self.accounts_btn.setToolTip("Выберите CSV или TXT файл с настройками почтовых аккаунтов\nФормат: smtp_host,smtp_port,login,password")
        self.accounts_btn.clicked.connect(self.load_accounts)
        files_layout.addWidget(self.accounts_btn)
        self.accounts_info = QLabel("Аккаунты не загружены", self)
        self.accounts_info.setStyleSheet("color: #888;")
        files_layout.addWidget(self.accounts_info)
        files_layout.addSpacing(10)
        self.recipients_btn = QPushButton("📂 Загрузить получателей", self)
        self.recipients_btn.setToolTip("Выберите TXT файл со списком email-адресов (один на строку)")
        self.recipients_btn.clicked.connect(self.load_recipients)
        files_layout.addWidget(self.recipients_btn)
        self.recipients_info = QLabel("Получатели не загружены", self)
        self.recipients_info.setStyleSheet("color: #888;")
        files_layout.addWidget(self.recipients_info)
        settings_layout.addWidget(files_group)
        message_group = QFrame()
        message_group.setFrameShape(QFrame.Shape.StyledPanel)
        message_layout = QVBoxLayout(message_group)
        message_layout.addWidget(QLabel("<b>Тема письма:</b>"))
        self.subject_edit = QTextEdit(self)
        self.subject_edit.setPlaceholderText("Введите тему письма...")
        self.subject_edit.setFixedHeight(40)
        message_layout.addWidget(self.subject_edit)
        message_layout.addWidget(QLabel("<b>Текст сообщения:</b>"))
        self.message_edit = QTextEdit(self)
        self.message_edit.setPlaceholderText("Введите текст сообщения, которое будет отправлено всем получателям...")
        message_layout.addWidget(self.message_edit)
        settings_layout.addWidget(message_group)
        self.send_btn = QPushButton("✉️ Начать рассылку", self)
        self.send_btn.setToolTip("Запустить массовую отправку писем")
        self.send_btn.setFixedHeight(50)
        self.send_btn.clicked.connect(self.start_sending)
        settings_layout.addWidget(self.send_btn)
        content_container.addWidget(settings_widget)
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.setContentsMargins(10, 10, 10, 10)
        logs_layout.addWidget(QLabel("<b>Прогресс отправки:</b>"))
        self.progress = QProgressBar(self)
        self.progress.setValue(0)
        logs_layout.addWidget(self.progress)
        logs_layout.addWidget(QLabel("<b>Лог событий:</b>"))
        self.log_list = QListWidget(self)
        self.log_list.setAlternatingRowColors(True)
        logs_layout.addWidget(self.log_list)
        content_container.addWidget(logs_widget)
        content_container.setSizes([300, 400])
        main_layout.addWidget(content_container)
        self.accounts = []
        self.recipients = []
        self.sender_thread = None
    def load_accounts(self, *args):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл с аккаунтами", "", "Файлы данных (*.csv *.txt)")
        if path:
            try:
                with open(path, encoding='utf-8') as f:
                    self.accounts = [line.strip().split(',') for line in f if line.strip()]
                self.accounts_info.setText(f"✅ Загружено аккаунтов: {len(self.accounts)}")
                self.accounts_info.setStyleSheet("color: green;")
                self.log_list.addItem(f"Загружено аккаунтов: {len(self.accounts)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки аккаунтов: {e}")
    def load_recipients(self, *args):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите TXT с получателями", "", "Text Files (*.txt)")
        if path:
            try:
                with open(path, encoding='utf-8') as f:
                    self.recipients = [line.strip() for line in f if line.strip()]
                self.recipients_info.setText(f"✅ Загружено получателей: {len(self.recipients)}")
                self.recipients_info.setStyleSheet("color: green;")
                self.log_list.addItem(f"Загружено получателей: {len(self.recipients)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки получателей: {e}")
    def start_sending(self, *args):
        if not self.accounts or not self.recipients:
            QMessageBox.warning(self, "Внимание", "Загрузите аккаунты и получателей!")
            return
        subject = self.subject_edit.toPlainText().strip() or "Без темы"
        body = self.message_edit.toPlainText().strip()
        if not body:
            QMessageBox.warning(self, "Внимание", "Введите текст сообщения!")
            return
        self.log_list.addItem("🚀 Запуск массовой рассылки...")
        self.progress.setValue(0)
        self.send_btn.setEnabled(False)
        self.sender_thread = MailSenderThread(self.accounts, self.recipients, subject, body)
        self.sender_thread.log_signal.connect(self.log_list.addItem)
        self.sender_thread.progress_signal.connect(self.update_progress)
        self.sender_thread.finished_signal.connect(self.sending_finished)
        self.sender_thread.start()
    def update_progress(self, current, total, *args):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        percent = int(current / total * 100)
        self.progress.setFormat(f"{percent}% ({current}/{total})")
        self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
    def sending_finished(self, *args):
        self.send_btn.setEnabled(True)
        QMessageBox.information(self, "Готово", "Массовая рассылка завершена!")
