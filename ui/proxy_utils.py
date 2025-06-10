import re
from typing import List, Dict
def parse_proxy_string(proxy_str: str) -> Dict[str, str]:
    proxy_str = proxy_str.strip()
    result = {'type': '', 'ip': '', 'port': '', 'login': '', 'password': ''}
    pattern1 = re.compile(r'^(?P<type>\w+):\/\/(?:(?P<login>[^:@\s]+)(?::(?P<password>[^@\s]+))?@)?(?P<ip>[\w\.-]+):(?P<port>\d+)$')
    pattern2 = re.compile(r'^(?P<type>\w+):\/\/(?P<ip>[\w\.-]+):(?P<port>\d+)@(?P<login>[^:]+):(?P<password>.+)$')
    pattern_proto3 = re.compile(r'^(?P<type>\w+):\/\/(?P<ip>[\w\.-]+):(?P<port>\d+):(?P<login>[^:]+):(?P<password>.+)$')
    pattern3 = re.compile(r'^(?P<ip>[\w\.-]+):(?P<port>\d+):(?P<login>[^:]+):(?P<password>.+)$')
    pattern4 = re.compile(r'^(?P<ip>[\d\.]+):(?P<port>\d+)@(?P<login>[^:]+):(?P<password>.+)$')
    pattern5 = re.compile(r'^(?P<ip>[\d\.]+):(?P<port>\d+)$')
    pattern6 = re.compile(r'^(?P<login>[^:@\s]+):(?P<password>[^@\s]+)@(?P<ip>[\w\.-]+):(?P<port>\d+)$')
    m = pattern1.match(proxy_str) or pattern2.match(proxy_str)
    if m:
        d = m.groupdict()
        result['type'] = d.get('type', '').lower()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        result['login'] = d.get('login', '') or ''
        result['password'] = d.get('password', '') or ''
        return result
    m = pattern_proto3.match(proxy_str)
    if m:
        d = m.groupdict()
        result['type'] = d.get('type', '').lower()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        result['login'] = d.get('login', '')
        result['password'] = d.get('password', '')
        return result
    m = pattern3.match(proxy_str)
    if m:
        d = m.groupdict()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        result['login'] = d.get('login', '')
        result['password'] = d.get('password', '')
        return result
    m = pattern4.match(proxy_str)
    if m:
        d = m.groupdict()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        result['login'] = d.get('login', '')
        result['password'] = d.get('password', '')
        return result
    m = pattern6.match(proxy_str)
    if m:
        d = m.groupdict()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        result['login'] = d.get('login', '')
        result['password'] = d.get('password', '')
        return result
    m = pattern5.match(proxy_str)
    if m:
        d = m.groupdict()
        result['ip'] = d.get('ip', '')
        result['port'] = d.get('port', '')
        return result
    if '://' in proxy_str:
        proto, rest = proxy_str.split('://', 1)
        result['type'] = proto.lower()
        try:
            if ':' in rest:
                ip, port = rest.split(':', 1)
                result['ip'] = ip
                result['port'] = port
            else:
                result['ip'] = rest
                result['port'] = ''
        except ValueError:
            result['ip'] = rest
            result['port'] = ''
        return result
    return result
def parse_proxies_from_txt(path: str) -> List[dict]:
    proxies = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                proxy = parse_proxy_string(line)
                if proxy.get('ip') and proxy.get('port'):
                    proxies.append(proxy)
    except Exception as e:
        print(f"Ошибка чтения файла прокси: {e}")
    return proxies
def load_proxy_from_list(index: int, proxies_list: List[dict]) -> dict:
    if not proxies_list:
        return None
    if index < len(proxies_list):
        return proxies_list[index]
    return proxies_list[-1] if proxies_list else None
