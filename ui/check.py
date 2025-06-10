import asyncio
import os
import sys
import time
from PyQt6.QtWidgets import ( QFileDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit, QWidget, QGroupBox, QListWidget
)
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QTimer
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from ui.okak import ErrorReportDialog
from ui.progress import ProgressWidget
from ui.thread_base import ThreadStopMixin, BaseThread
from ui.bots_win import BotTokenWindow
from ui.appchuy import AiogramBotConnection
class UserCheckThread(BaseThread):
    error_signal = pyqtSignal(str)
    update_stats_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str)
    check_completed_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, str, int)
    def __init__(self, token, user_ids, *args):
        super().__init__(session_file=token)
        self.token = token
        self.user_ids = user_ids
        self.bot_username = "unknown"
        self.unique_bot_key = None
        self.checking_active = True
        self.mutex = QMutex()
        self._stop_event = None
        self.batch_size = 20
        self.delay_between_requests = 0.3
        self.delay_between_batches = 2.0
        self.max_concurrent_requests = 5
        self.start_time = None
        self.processed_users = 0
        self.bot_manager = AiogramBotConnection(token)
        self.bot_manager.log_signal.connect(self.log_signal.emit)
        self.bot_manager.error_signal.connect(lambda t, e: self.log_signal.emit(f"{t}: {e.message}"))
    def safe_emit(self, signal, *args):
        with QMutexLocker(self.mutex):
            signal.emit(*args)
    def stop(self, *args):
        self.checking_active = False
        if self._stop_event is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.call_soon_threadsafe(self._stop_event.set)
            except Exception:
                pass
    async def process(self):
        self._stop_event = asyncio.Event()
        try:
            await self.check_users()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка в потоке проверки {self.token}: {str(e)}")
        finally:
            self.safe_emit(self.check_completed_signal, self.token)
    async def load_bot_info(self, bot=None, *args):
        if bot is None:
            bot = await self.bot_manager.connect()
        bot_info = await bot.get_me()
        self.bot_username = bot_info.username or "Без имени"
        self.unique_bot_key = f"{self.bot_username} ({self.token[:6]})"
        return self.bot_username, bot_info.id
    async def check_users(self, *args):
        try:
            self.start_time = time.time()
            self.processed_users = 0
            bot = await self.bot_manager.connect()
            self.bot_username, bot_id = await self.load_bot_info(bot)
            self.safe_emit(self.log_signal, f"✅ Бот {self.bot_username} начал проверку пользователей")
            stats = {
                "alive": 0,
                "dead": 0,
                "missing": 0,
                "languages": {},
                "rtl_in_name": 0,
                "premium": 0,
                "bot_username": self.unique_bot_key or self.bot_username
            }
            semaphore = asyncio.Semaphore(self.max_concurrent_requests)
            async def process_user(uid):
                if not self.checking_active:
                    return
                async with semaphore:
                    try:
                        await asyncio.sleep(self.delay_between_requests)
                        try:
                            user_info = await bot.get_me()
                            my_id = user_info.id
                            user_chat = await bot.get_chat(uid)
                            if hasattr(user_chat, "username") and user_chat.username:
                                try:
                                    chat_member = await bot.get_chat_member(user_chat.id, uid)
                                    user = chat_member.user
                                    stats["alive"] += 1
                                    if hasattr(user, "language_code") and user.language_code:
                                        lang = user.language_code
                                        stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                                    if hasattr(user, "is_premium") and user.is_premium:
                                        stats["premium"] += 1
                                    full_name = (getattr(user, "first_name", "") or "") + (getattr(user, "last_name", "") or "")
                                    if any(c in "אבגדהוזחטיכלמנסעפצקרשת" for c in full_name):
                                        stats["rtl_in_name"] += 1
                                    self.safe_emit(self.update_stats_signal, stats)
                                    return
                                except Exception as e:
                                    pass
                            if hasattr(user_chat, "language_code") and user_chat.language_code:
                                lang = user_chat.language_code
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                            if hasattr(user_chat, "is_premium") and user_chat.is_premium:
                                stats["premium"] += 1
                            stats["alive"] += 1
                            self.safe_emit(self.update_stats_signal, stats)
                            return
                        except Exception as api_error:
                            pass
                        chat = await bot.get_chat(uid)
                        stats["alive"] += 1
                        user_data_found = False
                        if hasattr(chat, "user") and chat.user:
                            user = chat.user
                            if hasattr(user, "language_code") and user.language_code:
                                lang = user.language_code
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                                user_data_found = True
                            if hasattr(user, "is_premium") and user.is_premium:
                                stats["premium"] += 1
                        elif hasattr(chat, "from_user") and chat.from_user:
                            from_user = chat.from_user
                            if hasattr(from_user, "language_code") and from_user.language_code:
                                lang = from_user.language_code
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                                user_data_found = True
                            if hasattr(from_user, "is_premium") and from_user.is_premium:
                                stats["premium"] += 1
                        elif hasattr(chat, "language_code") and chat.language_code:
                            lang = chat.language_code
                            stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                            user_data_found = True
                        if not user_data_found:
                            first_name = getattr(chat, "first_name", "") or ""
                            last_name = getattr(chat, "last_name", "") or ""
                            russian_alphabet = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                            if any(c.lower() in russian_alphabet for c in first_name + last_name):
                                lang = "ru"
                                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                        if hasattr(chat, "is_premium") and chat.is_premium:
                            stats["premium"] += 1
                        full_name = (getattr(chat, "first_name", "") or "") + (getattr(chat, "last_name", "") or "")
                        if any(c in "אבגדהוזחטיכלמנסעפצקרשת" for c in full_name):
                            stats["rtl_in_name"] += 1
                        self.safe_emit(self.update_stats_signal, stats)
                    except TelegramForbiddenError:
                        stats["dead"] += 1
                        self.safe_emit(self.update_stats_signal, stats)
                    except TelegramRetryAfter as e:
                        self.safe_emit(self.log_signal, f"⚠️ FloodWait для {self.bot_username}: ожидание {e.retry_after} секунд")
                        await asyncio.sleep(e.retry_after + 1)
                        return await process_user(uid)
                    except Exception as e:
                        self.safe_emit(self.log_signal, f"Ошибка для user_id {uid}: {e}")
                        stats["missing"] += 1
                        self.safe_emit(self.update_stats_signal, stats)
            processed = 0
            total_users = len(self.user_ids)
            last_update_percent = 0
            for i in range(0, total_users, self.batch_size):
                if not self.checking_active:
                    break
                batch = self.user_ids[i:i+self.batch_size]
                tasks = [process_user(uid) for uid in batch]
                await asyncio.gather(*tasks)
                processed += len(batch)
                self.processed_users = processed
                progress_percent = int(processed / total_users * 100)
                elapsed_time = time.time() - self.start_time
                if processed > 0 and elapsed_time > 0:
                    avg_time_per_user = elapsed_time / processed
                    remaining_users = total_users - processed
                    estimated_time_left = int(avg_time_per_user * remaining_users)
                    remaining_batches = (total_users - processed) // self.batch_size
                    estimated_time_left += int(remaining_batches * self.delay_between_batches)
                else:
                    estimated_time_left = 0
                if estimated_time_left > 0:
                    minutes, seconds = divmod(estimated_time_left, 60)
                    hours, minutes = divmod(minutes, 60)
                    time_left_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    status_text = f"Бот {self.bot_username}: {processed}/{total_users} ({progress_percent}%) - осталось {time_left_str}"
                else:
                    status_text = f"Бот {self.bot_username}: {processed}/{total_users} ({progress_percent}%)"
                percent_change = progress_percent - last_update_percent
                if percent_change >= 5 or progress_percent == 100:
                    self.safe_emit(self.progress_signal, progress_percent, status_text, estimated_time_left)
                    self.safe_emit(self.update_stats_signal, stats)
                    last_update_percent = progress_percent
                if self.checking_active and i + self.batch_size < total_users:
                    if self.delay_between_batches > 1:
                        pass
                    await asyncio.sleep(self.delay_between_batches)
            self.safe_emit(self.update_stats_signal, stats)
            self.safe_emit(self.progress_signal, 100, f"Бот {self.bot_username}: проверка завершена!", 0)
            self.safe_emit(self.log_signal,
                f"✅ Бот {self.bot_username} завершил проверку {len(self.user_ids)} пользователей")
        except Exception as e:
            self.safe_emit(self.error_signal, f"Ошибка при проверке пользователей для бота {self.bot_username}: {e}")
        finally:
            if self.bot_manager:
                try:
                    await self.bot_manager.disconnect()
                except Exception:
                    pass
class TokenLoaderThread(QThread):
    tokens_loaded = pyqtSignal(dict)
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    def __init__(self, file_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path
        self._running = True
    def stop(self, *args):
        self._running = False
    def run(self, *args):
        asyncio.run(self.async_load_tokens())
    async def async_load_tokens(self):
        tokens = {}
        try:
            with open(self.file_path, "r") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                self.log_signal.emit("Файл с токенами пуст.")
                self.tokens_loaded.emit(tokens)
                return
            async def get_bot_info(token):
                if not self._running:
                    return None
                try:
                    bot = Bot(token=token)
                    info = await bot.get_me()
                    await bot.session.close()
                    return (token, info.username or "Без имени", info.id)
                except Exception as e:
                    self.log_signal.emit(f"Ошибка при загрузке токена {token}: {e}")
                    return None
            tasks = [get_bot_info(token) for token in lines]
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    token, username, bot_id = res
                    tokens[token] = (username, bot_id)
            self.tokens_loaded.emit(tokens)
            self.log_signal.emit("Файл с токенами загружен.")
        except Exception as e:
            self.error_signal.emit(f"Ошибка при загрузке токенов: {e}")
class UserFolderLoaderThread(QThread):
    users_loaded = pyqtSignal(dict, dict)
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    def __init__(self, folder_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.folder_path = folder_path
        self._running = True
    def stop(self, *args):
        self._running = False
    def run(self, *args):
        asyncio.run(self.async_load_users())
    async def async_load_users(self):
        from aiogram import Bot
        tokens = {}
        users = {}
        try:
            file_names = os.listdir(self.folder_path)
            if not file_names:
                self.log_signal.emit("Папка с пользователями пуста.")
                self.users_loaded.emit(tokens, users)
                return
            async def process_file(file_name):
                if not self._running:
                    return None
                file_path = os.path.join(self.folder_path, file_name)
                if not os.path.isfile(file_path):
                    return None
                try:
                    with open(file_path, "r") as f:
                        lines = f.read().splitlines()
                        if not lines:
                            return None
                        token = lines[0]
                        user_ids = [int(line) for line in lines[1:] if line.isdigit()]
                        if not user_ids:
                            return None
                        try:
                            bot = Bot(token=token)
                            info = await bot.get_me()
                            await bot.session.close()
                            return (token, info.username or "Без имени", info.id, user_ids)
                        except Exception as e:
                            self.log_signal.emit(f"Ошибка при загрузке токена из файла {file_name}: {e}")
                            return None
                except Exception as e:
                    self.log_signal.emit(f"Ошибка при чтении файла {file_path}: {e}")
                    return None
            tasks = [process_file(file_name) for file_name in file_names]
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    token, username, bot_id, user_ids = res
                    tokens[token] = (username, bot_id)
                    users[token] = user_ids
            self.users_loaded.emit(tokens, users)
            self.log_signal.emit("Папка с пользователями загружена.")
        except Exception as e:
            self.error_signal.emit(f"Ошибка при обработке папки: {e}")
class CheckWindow(QWidget, ThreadStopMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ThreadStopMixin.__init__(self)
        if args and hasattr(args[0], 'config_changed'):
            self.main_window = args[0]
            self.main_window.config_changed.connect(self.on_config_changed)
        self.current_bot_username = ""
        self.checking_active = False
        self._error_log_path = os.path.join(os.getcwd(), 'check_error.log')
        self.setWindowTitle("Проверка пользователей")
        self.setMinimumSize(600, 500)
        main_layout = QHBoxLayout(self)
        left_groupbox = QGroupBox("")
        left_layout = QVBoxLayout(left_groupbox)
        left_layout.setContentsMargins(10, 10, 10, 10)
        self.progress_widget = ProgressWidget()
        left_layout.addWidget(self.progress_widget)
        load_layout = QHBoxLayout()
        self.users_button = QPushButton("📁 Загрузить папку с юзерами")
        self.users_button.clicked.connect(self.load_users_folder)
        load_layout.addWidget(self.users_button)
        left_layout.addLayout(load_layout)
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("▶ Начать проверку")
        self.start_button.clicked.connect(self.start_check)
        button_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.clicked.connect(self.stop_check)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        left_layout.addLayout(button_layout)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output, stretch=1)
        left_layout.addWidget(QLabel("📊 Статистика проверки:"))
        self.stats_list = QListWidget()
        left_layout.addWidget(self.stats_list, stretch=1)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("✓ Выберите ботов:"))
        self.bot_token_window = BotTokenWindow(token_folder_path=self.parent().bot_token_folder if self.parent() else self.bot_token_folder)
        self.bot_token_window.tokens_updated.connect(self.on_bots_win_tokens_updated)
        self.bot_token_window.files_updated.connect(self.on_bots_win_files_updated)
        right_layout.addWidget(self.bot_token_window)
        main_layout.addWidget(left_groupbox, 3)
        main_layout.addLayout(right_layout, 1)
        self.tokens = {}
        self.users = {}
        self.bot_stats = {}
        self.total_threads = 0
        self.completed_threads = 0
        self.total_users_to_process = 0
        self.total_users_processed = 0
        self.estimated_time_left = 0
        self.selected_tokens = []
        self.progress_widget.update_progress(0, "Готов к работе")
    async def load_bot_info(self, bot=None, *args):
        if bot is None:
            bot = await self.bot_manager.connect()
        bot_info = await bot.get_me()
        self.bot_username = bot_info.username or "Без имени"
        self.unique_bot_key = f"{self.bot_username} ({self.token[:6]})"
        return self.bot_username, bot_info.id
    def load_users_folder(self, *args):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку с пользователями")
        if not folder:
            return
        self.users.clear()
        self.user_folder_loader_thread = UserFolderLoaderThread(folder)
        self.user_folder_loader_thread.users_loaded.connect(self.on_users_loaded)
        self.user_folder_loader_thread.log_signal.connect(self.log_output.append)
        self.user_folder_loader_thread.error_signal.connect(self.log_output.append)
        self.user_folder_loader_thread.start()
    def on_users_loaded(self, tokens, users):
        self.tokens = tokens
        self.users = users
    def start_check(self, *args):
        if self.checking_active:
            self.log_output.append("⛔ Проверка уже запущена")
            return
        selected_tokens = getattr(self, "selected_tokens", [])
        if not selected_tokens:
            self.log_output.append("⛔ Выберите хотя бы одного бота через окно управления токенами")
            return
        self.log_output.clear()
        self.log_output.append(f"Выбрано токенов: {len(selected_tokens)}")
        self.log_output.append("✅ Начинаем проверку пользователей...")
        self.stats_list.clear()
        self.bot_stats.clear()
        self.checking_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.total_users_to_process = 0
        self.total_users_processed = 0
        self.estimated_time_left = 0
        for token in selected_tokens:
            user_ids = self.users.get(token, [])
            self.total_users_to_process += len(user_ids)
        self.progress_widget.update_progress(0, f"Начинаем проверку {self.total_users_to_process} пользователей")
        threads = []
        for token in selected_tokens:
            user_ids = self.users.get(token, [])
            if not user_ids:
                self.log_output.append(f"❌ Нет пользователей для токена {token}.")
                continue
            thread = UserCheckThread(token, user_ids)
            thread.log_signal.connect(self.log_message)
            thread.error_signal.connect(self.handle_thread_error)
            thread.update_stats_signal.connect(self.update_thread_stats)
            thread.check_completed_signal.connect(self._on_thread_finished)
            thread.progress_signal.connect(self.update_thread_progress)
            threads.append(thread)
        self.total_threads = len(threads)
        self.completed_threads = 0
        self.completed_tokens = set()
        self.check_threads = threads
        for thread in threads:
            self.thread_manager.start_thread(thread)
        self.log_output.append(f"Запущено потоков проверки: {len(threads)}")
    def update_thread_stats(self, stats, *args):
        bot_username = stats.get("bot_username", "unknown")
        self.bot_stats[bot_username] = stats
        self.update_results()
    def update_results(self, *args):
        self.stats_list.clear()
        total_alive = 0
        total_dead = 0
        total_missing = 0
        total_premium = 0
        total_rtl = 0
        all_languages = {}
        for bot_username, stats in self.bot_stats.items():
            alive = stats.get("alive", 0)
            dead = stats.get("dead", 0)
            missing = stats.get("missing", 0)
            premium = stats.get("premium", 0)
            rtl_in_name = stats.get("rtl_in_name", 0)
            languages = stats.get("languages", {})
            total_alive += alive
            total_dead += dead
            total_missing += missing
            total_premium += premium
            total_rtl += rtl_in_name
            for lang, count in languages.items():
                all_languages[lang] = all_languages.get(lang, 0) + count
            if alive > 0:
                ru_users = languages.get("ru", 0)
                ru_percentage = (ru_users / alive * 100) if alive > 0 else 0
                other_percentage = 100 - ru_percentage
                formatted_stats = (
                    f"✅ Результаты проверки: @{bot_username}\n\n"
                    f"Пользователи:\n"
                    f"- живы: {alive}\n"
                    f"- мертвы: {dead}\n"
                    f"- отсутствуют: {missing}\n\n"
                    f"Языки:\n"
                    f"🇷🇺 RU: {ru_percentage:.1f} %\n"
                    f"🏳️ Прочие: {other_percentage:.1f} %\n\n"
                    f"Наличие RTL в имени: {rtl_in_name}\n"
                    f"Наличие premium: {premium}\n"
                    f"———"
                )
                self.stats_list.addItem(formatted_stats)
        if len(self.bot_stats) > 1:
            ru_users = all_languages.get("ru", 0)
            ru_percentage = (ru_users / total_alive * 100) if total_alive > 0 else 0
            other_percentage = 100 - ru_percentage
            total_stats = (
                f"✅ ОБЩАЯ СТАТИСТИКА ПО ВСЕМ БОТАМ\n\n"
                f"Пользователи:\n"
                f"- живы: {total_alive}\n"
                f"- мертвы: {total_dead}\n"
                f"- отсутствуют: {total_missing}\n\n"
                f"Языки:\n"
                f"🇷🇺 RU: {ru_percentage:.1f} %\n"
                f"🏳️ Прочие: {other_percentage:.1f} %\n\n"
                f"Наличие RTL в имени: {total_rtl}\n"
                f"Наличие premium: {total_premium}\n"
                f"———"
            )
            self.stats_list.insertItem(0, total_stats)
    def stop_check(self, *args):
        if not self.checking_active:
            return
        self.stop_all_operations()
        self.checking_active = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_widget.update_progress(100, "Проверка остановлена")
        self.log_output.append("⏳ Остановка проверки...")
    def _on_thread_finished(self, token, *args):
        if not isinstance(token, str): 
            return
        if not hasattr(self, 'completed_tokens'):
            self.completed_tokens = set()
        if token in self.completed_tokens:
            return        
        self.completed_tokens.add(token)
        self.completed_threads += 1
        self.log_output.append(f"✅ Проверка завершена для токена: {token} ({self.completed_threads}/{self.total_threads})")
        if self.completed_threads >= self.total_threads:
            self.checking_active = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.progress_widget.update_progress(100, "Проверка завершена")
            self.log_output.append("🏁✅ Все проверки завершены.")
        else:
            current_progress = int((self.completed_threads / self.total_threads) * 100) if self.total_threads > 0 else 0
            self.progress_widget.update_progress(current_progress, f"Завершено {self.completed_threads} из {self.total_threads} потоков")
    def log_message(self, message, *args):
        self.log_output.append(message)
    def handle_thread_error(self, error_message, *args):
        try:
            with open(self._error_log_path, 'a', encoding='utf-8') as f:
                f.write((error_message or '(traceback пустой)') + '\n')
        except Exception:
            pass
        QTimer.singleShot(5000, lambda: ErrorReportDialog.send_error_report(self._error_log_path))
    def on_config_changed(self, config, *args):
        pass
    def update_thread_progress(self, progress, status, time_left, *args, **kwargs):
        parts = status.split(":")
        if len(parts) > 0:
            bot_name = parts[0].replace("Бот ", "").strip()
            for thread in self.check_threads:
                if thread.bot_username == bot_name:
                    self.total_users_processed = 0
                    active_threads = 0
                    for t in self.check_threads:
                        if t.isRunning():
                            active_threads += 1
                            self.total_users_processed += t.processed_users
                    if self.total_users_to_process > 0:
                        overall_progress = int((self.total_users_processed / self.total_users_to_process) * 100)
                    else:
                        overall_progress = 0
                    max_time_left = time_left
                    for t in self.check_threads:
                        if t.isRunning():
                            thread_time_left = time_left
                            if thread_time_left > max_time_left:
                                max_time_left = thread_time_left
                    if max_time_left > 0:
                        minutes, seconds = divmod(max_time_left, 60)
                        hours, minutes = divmod(minutes, 60)
                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        status_text = f"Обработано {self.total_users_processed}/{self.total_users_to_process} • Осталось {time_str}"
                    else:
                        status_text = f"Обработано {self.total_users_processed}/{self.total_users_to_process} • Завершается..."
                    self.progress_widget.update_progress(overall_progress, status_text)
                    break
    def on_bots_win_tokens_updated(self, tokens, *args, **kwargs):
        self.selected_tokens = tokens
        self.tokens = {t: self.bot_token_window.token_usernames.get(t, t) for t in tokens}
    def on_bots_win_files_updated(self, files, *args, **kwargs):
        pass
