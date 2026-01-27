import time
from typing import Any, Dict, Optional


class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Any] = {}
        self._exp: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        exp = self._exp.get(key)
        if exp is None or exp < now:
            self._store.pop(key, None)
            self._exp.pop(key, None)
            return None
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._exp[key] = time.time() + self.ttl_seconds
