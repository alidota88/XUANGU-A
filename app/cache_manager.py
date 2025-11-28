import os
import json
from datetime import datetime

CACHE_DIR = "/app/cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def load_cache(name):
    path = os.path.join(CACHE_DIR, name)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(name, data):
    path = os.path.join(CACHE_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
