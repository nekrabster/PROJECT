import time
import random
from functools import wraps
def heavy_obfuscation(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if random.random() < 0.01:
            time.sleep(random.uniform(0.01, 0.05))
        return func(*args, **kwargs)
    return wrapper
def critical_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if random.random() < 0.005:
            time.sleep(random.uniform(0.01, 0.03))
        return func(*args, **kwargs)
    return wrapper 
