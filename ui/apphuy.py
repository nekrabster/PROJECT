import os
import json
import logging
import asyncio
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, Any, Tuple, List, Callable
from dataclasses import dataclass
from functools import wraps
import re

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, UsernameOccupiedError
)
from telethon.tl.types import User
from PyQt6.QtCore import pyqtSignal, QObject
from ui.loader import (
    get_session_config as loader_get_session_config,
    load_proxy,
)
from telethon.tl.functions.account import UpdateProfileRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from ui.proxy_utils import load_proxy_from_list

class TelegramErrorType(Enum):
    FLOOD_WAIT = auto()
    USER_BLOCKED = auto()
    USER_DEACTIVATED = auto()
    USER_DELETED = auto()
    CHAT_DEACTIVATED = auto()
    AUTH_ERROR = auto()
    SPAM_BLOCK = auto()
    PEER_FLOOD = auto()
    OTHER = auto()
@dataclass
class TelegramError:
    type: TelegramErrorType
    message: str
    wait_time: Optional[int] = None
    details: Optional[Dict[str, Any]] = None
class TelegramCustomError(Exception):
    def __init__(self, error_type: TelegramErrorType, message: str, wait_time: Optional[int] = None):
        self.error_type = error_type
        self.message = message
        self.wait_time = wait_time
        super().__init__(message)
class TelegramErrorHandler:
    @staticmethod
    def classify_error(error: Exception, *args) -> TelegramError:
        error_text = str(error).lower()
        wait_time = None
        if isinstance(error, FloodWaitError):
            error_type = TelegramErrorType.FLOOD_WAIT
            wait_time = error.seconds
        elif "peer_flood" in error_text:
            error_type = TelegramErrorType.PEER_FLOOD
        elif "user is blocked" in error_text:
            error_type = TelegramErrorType.USER_BLOCKED
        elif "user is deactivated" in error_text:
            error_type = TelegramErrorType.USER_DEACTIVATED
        elif "user is deleted" in error_text:
            error_type = TelegramErrorType.USER_DELETED
        elif "chat is deactivated" in error_text:
            error_type = TelegramErrorType.CHAT_DEACTIVATED
        elif "auth_key" in error_text:
            error_type = TelegramErrorType.AUTH_ERROR
        elif "spam" in error_text:
            error_type = TelegramErrorType.SPAM_BLOCK
        else:
            error_type = TelegramErrorType.OTHER
        return TelegramError(
            type=error_type,
            message=str(error),
            wait_time=wait_time
        )
    @staticmethod
    def format_error_message(session_file: str, error: TelegramError, *args) -> str:
        base_name = os.path.basename(session_file)
        if error.type == TelegramErrorType.FLOOD_WAIT:
            return f"⏳ {base_name} | Ограничение: ждите {error.wait_time} сек"
        elif error.type == TelegramErrorType.USER_BLOCKED:
            return f"❌ {base_name} | Пользователь заблокирован"
        elif error.type == TelegramErrorType.USER_DEACTIVATED:
            return f"❌ {base_name} | Пользователь деактивирован"
        elif error.type == TelegramErrorType.USER_DELETED:
            return f"❌ {base_name} | Пользователь удален"
        elif error.type == TelegramErrorType.CHAT_DEACTIVATED:
            return f"❌ {base_name} | Чат деактивирован"
        elif error.type == TelegramErrorType.AUTH_ERROR:
            return f"❌ {base_name} | Ошибка авторизации"
        elif error.type == TelegramErrorType.SPAM_BLOCK:
            return f"❌ {base_name} | Обнаружен спам блок"
        elif error.type == TelegramErrorType.PEER_FLOOD:
            return f"❌ {base_name} | Слишком много запросов к пользователям"
        else:
            return f"❌ {base_name} | {error.message}"
def handle_telegram_errors(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            error = TelegramErrorHandler.classify_error(e)
            session_file = next((arg for arg in args if isinstance(arg, str) and arg.endswith('.session')),
                              getattr(self, 'session_file', 'Unknown'))
            error_msg = TelegramErrorHandler.format_error_message(session_file, error)
            if hasattr(self, 'log_signal'):
                self.log_signal.emit(error_msg)
            if hasattr(self, 'error_signal'):
                self.error_signal.emit(session_file, error)
            if hasattr(self, 'flood_wait_signal') and error.type == TelegramErrorType.FLOOD_WAIT:
                self.flood_wait_signal.emit(session_file, error.wait_time or 0)
            logger = logging.getLogger(self.__class__.__name__)
            logger.error(f"Telegram API error: {error_msg}", exc_info=e)
            raise TelegramCustomError(error.type, error_msg, error.wait_time)
    return wrapper
class ProfileManager:
    def __init__(self, connection: 'TelegramConnection'):
        self.connection = connection
        self._logger = logging.getLogger(self.__class__.__name__)
    @handle_telegram_errors
    async def update_names(self, first_name: Optional[str] = None, last_name: Optional[str] = None, *args) -> bool:
        if not first_name and not last_name:
            return False
        await self.connection.client(UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name
        ))
        return True
    @handle_telegram_errors
    async def update_username(self, username: str, *args) -> bool:
        """Обновляет username пользователя"""
        try:
            await self.connection.client(UpdateUsernameRequest(username=username))
            return True
        except UsernameOccupiedError:
            self._logger.warning(f"Username {username} занят")
            return False
    @handle_telegram_errors
    async def update_avatar(self, image_path: str, *args) -> bool:
        """Обновляет аватар пользователя"""
        if not os.path.exists(image_path):
            return False
        try:
            file = await self.connection.client.upload_file(image_path)
            await self.connection.client(UploadProfilePhotoRequest(file=file))
            return True
        except Exception as e:
            self._logger.error(f"Ошибка обновления аватара: {e}")
            return False

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
def proxy_dict_to_tuple(proxy):
    if not proxy:
        return None
    proxy_type = proxy.get('proxy_type') or proxy.get('type') or 'socks5'
    ip = proxy.get('addr') or proxy.get('ip')
    port = int(proxy.get('port'))
    login = proxy.get('username') or proxy.get('login')
    password = proxy.get('password')
    if login and password:
        return (proxy_type, ip, port, login, password)
    else:
        return (proxy_type, ip, port)
class TelegramConnection(QObject):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, TelegramError)
    flood_wait_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str)
    def __init__(self, session_folder: str):
        super().__init__()
        self.session_folder = session_folder
        self.client = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self.error_handler = TelegramErrorHandler()
        self.profile = ProfileManager(self)
    async def connect(self, session_file: str, use_proxy: bool = False, proxy: dict = None, *args) -> Tuple[bool, Optional[User]]:
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
            session_path = os.path.join(self.session_folder, session_file)
            api_id, api_hash, device, app_version, system_version = loader_get_session_config(session_path)
            if not api_id or not api_hash:
                self.log_signal.emit(f"❌ Некорректная конфигурация: {session_file}")
                return False, None
            config = {
                'api_id': api_id,
                'api_hash': api_hash,
                'device': device or 'Unknown',
                'app_version': app_version or '1.0',
                'system_version': system_version or 'Unknown'
            }
            if proxy is None:
                proxy, log_str = select_proxy(0, use_proxy, False, [], config)
            if proxy is not None and isinstance(proxy, dict):
                proxy = proxy_dict_to_tuple(proxy)
            self.client = TelegramClient(
                session_path,
                config['api_id'],
                config['api_hash'],
                proxy=proxy,
                device_model=config['device'],
                app_version=config['app_version'],
                system_version=config['system_version']
            )
            try:
                await self.client.connect()
                if not await self.client.is_user_authorized():
                    self.log_signal.emit(f"❌ Ошибка авторизации: {session_file}")
                    return False, None
                me = await self.client.get_me()
                if not me:
                    self.log_signal.emit(f"❌ Ошибка авторизации: {session_file}")
                    return False, None
                return True, me
            except Exception as e:
                error = self.error_handler.classify_error(e)
                error_msg = self.error_handler.format_error_message(session_file, error)
                self.log_signal.emit(error_msg)
                self.error_signal.emit(session_file, error)
                if error.type == TelegramErrorType.FLOOD_WAIT and error.wait_time:
                    self.flood_wait_signal.emit(session_file, error.wait_time)
                return False, None
        except Exception as e:
            self.log_signal.emit(f"❌ Неизвестная ошибка: {str(e)}")
            self._logger.error(f"Ошибка подключения: {str(e)}", exc_info=e)
            return False, None
    async def disconnect(self, *args):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                self._logger.error(f"Ошибка при отключении: {str(e)}")
    async def update_session_info(self, session_file: str, me: User, spam_blocked: bool = False, spam_block_end_date: Optional[str] = None, *args) -> None:
        try:
            session_path = os.path.join(self.session_folder, session_file)
            json_path = session_path.replace('.session', '.json')
            current_data = {}
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        current_data = json.load(f)
                except json.JSONDecodeError:
                    self._logger.warning(f"Невалидный JSON файл: {json_path}")
            uses_app_prefix = 'app_id' in current_data or 'app_hash' in current_data
            id_key = 'app_id' if uses_app_prefix else 'api_id'
            hash_key = 'app_hash' if uses_app_prefix else 'api_hash'
            new_data = {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone,
                'is_premium': getattr(me, 'premium', False),
                'has_profile_pic': bool(me.photo),
                'lang_code': getattr(me, 'lang_code', None),
                'twoFA': current_data.get('twoFA', ''),
                'spamblock': spam_blocked,
                'spamblock_check_date': datetime.now().isoformat(),
                'last_update': datetime.now().isoformat()
            }
            if spam_block_end_date:
                new_data['spamblock_end_date'] = spam_block_end_date
            elif 'spamblock_end_date' in current_data:
                new_data['spamblock_end_date'] = current_data['spamblock_end_date']
            if id_key in current_data:
                new_data[id_key] = current_data[id_key]
            if hash_key in current_data:
                new_data[hash_key] = current_data[hash_key]
            if 'spam_count' in current_data:
                new_data['spam_count'] = current_data['spam_count']
                if spam_blocked and not current_data.get('spamblock', False):
                    new_data['spam_count'] += 1
            else:
                new_data['spam_count'] = 1 if spam_blocked else 0
            if not self._should_update_json(current_data, new_data):
                return
            current_data.update(new_data)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self._logger.error(f"Ошибка обновления JSON: {str(e)}", exc_info=e)
    def _should_update_json(self, current: Dict[str, Any], new: Dict[str, Any], *args) -> bool:
        relevant_fields = {'id', 'username', 'first_name', 'last_name', 'phone', 'is_premium', 'has_profile_pic', 'lang_code', 'spamblock', 'spam_count'}
        for field in relevant_fields:
            if field not in current or current[field] != new[field]:
                return True
        return False
    @property
    def is_connected(self) -> bool:
        return self.client and self.client.is_connected()
    async def check_authorization(self, *args) -> bool:
        if not self.is_connected:
            return False
        try:
            return await self.client.is_user_authorized()
        except Exception:
            return False
    def get_client(self, *args) -> Optional[TelegramClient]:
        return self.client if self.is_connected else None
    @handle_telegram_errors
    async def check_spam_block(self, *args) -> tuple[bool, str | None]:
        try:
            entity = await self.client.get_entity("SpamBot")
            await self.client.send_message(entity, "/start")
            await asyncio.sleep(2)
            async for message in self.client.iter_messages(entity, limit=1):
                text = message.message
                if "Ваш аккаунт свободен от каких-либо ограничений" in text:
                    return False, None
                if "Ваш аккаунт временно ограничен" in text:
                    match = re.search(r"Ограничения будут автоматически сняты ([^\.]+)\.", text)
                    if match:
                        end_date = match.group(1).strip()
                        return True, end_date
                    return True, None
            return False, None
        except Exception as e:
            return False, None
    @handle_telegram_errors
    async def check_premium(self, *args) -> Tuple[bool, Optional[float]]:
        try:
            me = await self.client.get_me()
            if not me:
                return False, None
            is_premium = getattr(me, 'premium', False)
            premium_expires = getattr(me, 'premium_expires_date', None)
            if premium_expires:
                return is_premium, premium_expires.timestamp()
            return is_premium, None
        except Exception as e:
            self._logger.error(f"Ошибка проверки премиум статуса: {e}")
            return False, None

