import os
import asyncio
import logging
import ssl
from enum import Enum, auto
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from functools import wraps
from PyQt6.QtCore import pyqtSignal, QObject
from aiogram import Bot
import aiohttp
from ui.proxy_utils import load_proxy_from_list
from ui.loader import load_proxy
class AiogramErrorType(Enum):
    FLOOD_WAIT = auto()
    UNAUTHORIZED = auto()
    SSL_ERROR = auto()
    BAD_GATEWAY = auto()
    CONNECTION = auto()
    BLOCKED_BY_USER = auto()
    CHAT_NOT_FOUND = auto()
    USER_DEACTIVATED = auto()
    OTHER = auto()
@dataclass
class AiogramError:
    type: AiogramErrorType
    message: str
    wait_time: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
class AiogramCustomError(Exception):
    def __init__(self, error_type: AiogramErrorType, message: str, wait_time: Optional[int] = None, user_id: Optional[str] = None, username: Optional[str] = None):
        self.error_type = error_type
        self.message = message
        self.wait_time = wait_time
        self.user_id = user_id
        self.username = username
        super().__init__(message)
class AiogramErrorHandler:
    @staticmethod
    def classify_error(error: Exception, user_id: Optional[str] = None, username: Optional[str] = None) -> AiogramError:
        error_text = str(error).lower()
        wait_time = None
        if 'flood' in error_text or 'too many requests' in error_text:
            error_type = AiogramErrorType.FLOOD_WAIT
        elif 'unauthorized' in error_text:
            error_type = AiogramErrorType.UNAUTHORIZED
        elif 'ssl' in error_text or 'certificate' in error_text or 'handshake' in error_text:
            error_type = AiogramErrorType.SSL_ERROR
        elif 'bad gateway' in error_text:
            error_type = AiogramErrorType.BAD_GATEWAY
        elif 'connection' in error_text or 'timeout' in error_text or 'clientoserror' in error_text:
            error_type = AiogramErrorType.CONNECTION
        elif 'forbidden: bot was blocked by the user' in error_text:
            error_type = AiogramErrorType.BLOCKED_BY_USER
        elif 'chat not found' in error_text:
            error_type = AiogramErrorType.CHAT_NOT_FOUND
        elif 'forbidden: user is deactivated' in error_text:
            error_type = AiogramErrorType.USER_DEACTIVATED
        else:
            error_type = AiogramErrorType.OTHER
        return AiogramError(type=error_type, message=str(error), wait_time=wait_time, user_id=user_id, username=username)
    @staticmethod
    def format_error_message(token: str, error: AiogramError) -> str:
        base_name = error.username or token[:10] + '...'
        user_part = f" для {error.user_id}" if error.user_id else ""
        if error.type == AiogramErrorType.FLOOD_WAIT:
            return f"⏳ {base_name}{user_part} | FloodWait: ждите {error.wait_time or '?'} сек"
        elif error.type == AiogramErrorType.UNAUTHORIZED:
            return f"❌ {base_name} | Неавторизован"
        elif error.type == AiogramErrorType.SSL_ERROR:
            return f"❌ {base_name} | SSL ошибка"
        elif error.type == AiogramErrorType.BAD_GATEWAY:
            return f"❌ {base_name} | Bad Gateway"
        elif error.type == AiogramErrorType.CONNECTION:
            if error.message and 'application data after close notify' in error.message.lower():
                return f"❌ {base_name} | Проблема с SSL-соединением с Telegram. Попробуйте позже или смените сеть/прокси."
            return f"❌ {base_name} | Ошибка соединения с Telegram"
        elif error.type == AiogramErrorType.BLOCKED_BY_USER:
            return f"{base_name}: пользователь{user_part} заблокировал бота"
        elif error.type == AiogramErrorType.CHAT_NOT_FOUND:
            return f"{base_name}: чат{user_part} не найден"
        elif error.type == AiogramErrorType.USER_DEACTIVATED:
            return f"{base_name}: пользователь{user_part} деактивирован"
        else:
            if error.message and 'application data after close notify' in error.message.lower():
                return f"❌ {base_name} | Проблема с SSL-соединением с Telegram. Попробуйте позже или смените сеть/прокси."
            return f"❌ {base_name}{user_part} | {error.message}"
def handle_aiogram_errors(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            user_id = kwargs.get('user_id') or getattr(self, 'last_user_id', None)
            username = getattr(self, 'username', None)
            error = AiogramErrorHandler.classify_error(e, user_id=user_id, username=username)
            token = getattr(self, 'token', 'Unknown')
            error_msg = AiogramErrorHandler.format_error_message(token, error)
            logger = logging.getLogger(self.__class__.__name__)
            logger.error(f"Aiogram API error in {func.__name__} for bot {token[:10]}...: {error_msg}", exc_info=True)
            if hasattr(self, 'log_signal'):
                self.log_signal.emit(error_msg)
            if hasattr(self, 'error_signal'):
                self.error_signal.emit(token, error)
            if hasattr(self, 'flood_wait_signal') and error.type == AiogramErrorType.FLOOD_WAIT:
                self.flood_wait_signal.emit(token, error.wait_time or 0)
            raise AiogramCustomError(error.type, error_msg, error.wait_time, user_id=user_id, username=username) from e
    return wrapper
class AiogramBotConnection(QObject):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, AiogramError)
    flood_wait_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str)
    def __init__(self, token: str, proxy: Optional[dict] = None, username: Optional[str] = None):
        super().__init__()
        self.token = token
        self.proxy = proxy
        self.bot = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = None
        self._connector = None
        self._running = False
        self._reconnect_attempts = 3
        self._reconnect_delay = 5
        self.username = username
        self.last_user_id = None
    @handle_aiogram_errors
    async def connect(self, *args):
        if self.bot:
            await self.disconnect()
        ssl_context = ssl.create_default_context()
        self._connector = aiohttp.TCPConnector(ssl=ssl_context)
        proxy_url = None
        if self.proxy:
            scheme = self.proxy.get('type', 'socks5')
            ip = self.proxy.get('ip')
            port = self.proxy.get('port')
            login = self.proxy.get('login', '')
            password = self.proxy.get('password', '')
            if login and password:
                proxy_url = f"{scheme}://{login}:{password}@{ip}:{port}"
            else:
                proxy_url = f"{scheme}://{ip}:{port}"
        self.bot = Bot(token=self.token, proxy=proxy_url, connector=self._connector)
        self._running = True
        try:
            info = await self.bot.get_me()
            self.username = info.username or self.token[:10] + '...'
        except Exception:
            self.username = self.token[:10] + '...'
        self.log_signal.emit(f"✅ Бот {self.username} подключен")
        return self.bot
    @handle_aiogram_errors
    async def disconnect(self, *args):
        if self.bot:
            try:
                await self.bot.session.close()
                self.log_signal.emit(f"⏹️ Бот {self.username} отключен")
            except Exception as e:
                self._logger.error(f"Ошибка при отключении: {str(e)}")
        self._running = False
    @handle_aiogram_errors
    async def reconnect(self, *args):
        for attempt in range(self._reconnect_attempts):
            try:
                await self.disconnect()
                await asyncio.sleep(self._reconnect_delay)
                await self.connect()
                self.log_signal.emit(f"🔄 Переподключение успешно для {self.username}...")
                return True
            except Exception as e:
                self.log_signal.emit(f"⚠️ Ошибка переподключения ({attempt+1}): {e}")
                await asyncio.sleep(self._reconnect_delay)
        self.log_signal.emit(f"❌ Не удалось переподключить бота {self.username}...")
        return False
    @handle_aiogram_errors
    async def get_updates(self, offset=0, timeout=3, *args):
        if not self.bot:
            await self.connect()
        while True:
            try:
                updates = await self.bot.get_updates(offset=offset, timeout=timeout)
                return updates
            except Exception as e:
                error_text = str(e).lower()
                if "retry after" in error_text:
                    import re
                    match = re.search(r'retry after (\d+)', error_text)
                    wait_time = int(match.group(1)) if match else 5
                    self.log_signal.emit(f"⏳ Flood control: ждем {wait_time} сек")
                    await asyncio.sleep(wait_time)
                else:
                    raise
            await asyncio.sleep(1)
    @handle_aiogram_errors
    async def check_connection(self, *args):
        if not self.bot:
            await self.connect()
        try:
            await self.bot.get_me()
            return True
        except Exception as e:
            self.log_signal.emit(f"⚠️ Ошибка соединения: {e}")
            return await self.reconnect()
    @property
    def is_connected(self, *args) -> bool:
        return self.bot is not None
def select_proxy(index: int, use_proxy: bool, use_proxy_txt: bool, proxies_list: list, config: dict = None):
    proxy = None
    log_str = None
    if use_proxy_txt and proxies_list:
        proxy = load_proxy_from_list(index, proxies_list)
        if proxy:
            log_str = f"🌐 Используется прокси из txt: {proxy.get('ip', 'не указан')}:{proxy.get('port', '')}"
    elif use_proxy:
        proxy = load_proxy(config or {})
        if proxy:
            log_str = f"🌐 Используется прокси: {proxy.get('addr', 'не указан')}"
        else:
            log_str = "⚠️ Прокси включен, но не настроен в конфигурации"
    else:
        log_str = "ℹ️ Прокси не используется"
    return proxy, log_str
