import time
import random
from functools import wraps
def heavy_obfuscation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if random.random() < 0.05:
            time.sleep(random.uniform(0.1, 0.3))
        return func(*args, **kwargs)
    return wrapper
def critical_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if random.random() < 0.05:
            time.sleep(random.uniform(0.1, 0.2))
        return func(*args, **kwargs)
    return wrapper 