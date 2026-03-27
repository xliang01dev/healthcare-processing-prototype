# Swap backing implementation to Redis without changing service code.


class CacheService:
    def __init__(self) -> None:
        self._store: dict = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value) -> None:
        self._store[key] = value
