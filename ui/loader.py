import os
import json
import logging
import aiofiles
from typing import List
def load_config(filepath='config.txt', *args):
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return {k: v for line in file if '=' in line and line.strip() for k, v in [line.strip().split('=', 1)]}
    except Exception:
        logging.warning(f'{filepath} отсутствует или пустой')
        return {}
def load_proxy(config: dict, *args):
    try:
        proxy_type = config['PROXY_TYPE']
        addr = config['PROXY_IP']
        port = int(config['PROXY_PORT'])
    except (KeyError, ValueError, TypeError):
        return None
    return {'proxy_type': proxy_type, 'addr': addr, 'port': port, 'username': config.get('PROXY_LOGIN'), 'password': config.get('PROXY_PASSWORD')}
def get_session_files(session_folder: str) -> List[str]:
    if not os.path.exists(session_folder) or not os.path.isdir(session_folder):
        return []
    session_files = []
    for root, dirs, files in os.walk(session_folder):
        for file in files:
            if file.endswith('.session') and (not file.endswith('.journal')):
                rel_path = os.path.relpath(os.path.join(root, file), session_folder)
                session_files.append(rel_path)
    return session_files
def get_session_config(session_file: str, *args):
    json_file = session_file.replace('.session', '.json')
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        api_id = int(config.get('api_id') or config.get('app_id', 0))
        api_hash = config.get('api_hash') or config.get('app_hash', '')
        if not api_id or not api_hash:
            raise ValueError('api_id или api_hash отсутствуют.')
        return (api_id, api_hash, config.get('device'), config.get('app_version'), config.get('system_version'))
    except Exception as e:
        logging.error(f'Ошибка загрузки {json_file}: {e}')
        return (None, None, None, None, None)
async def load_file_async(filepath: str, *args):
    try:
        async with aiofiles.open(filepath, mode='r', encoding='utf-8') as f:
            return await f.read()
    except Exception as e:
        logging.error(f'Ошибка при асинхронной загрузке файла {filepath}: {e}')
        return None
