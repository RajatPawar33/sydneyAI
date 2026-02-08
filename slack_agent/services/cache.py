import json
from typing import Any, Optional

import redis.asyncio as aioredis
from config.settings import settings


class CacheService:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        self.redis = await aioredis.from_url(
            f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
            password=settings.redis_password,
            decode_responses=True,
        )

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None

        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        if not self.redis:
            return

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        await self.redis.set(key, value, ex=expire)

    async def delete(self, key: str):
        if self.redis:
            await self.redis.delete(key)

    async def exists(self, key: str) -> bool:
        if not self.redis:
            return False
        return await self.redis.exists(key) > 0

    # rate limiting
    async def check_rate_limit(self, user_id: str) -> bool:
        key = f"rate_limit:{user_id}"
        count = await self.redis.incr(key)

        if count == 1:
            await self.redis.expire(key, settings.rate_limit_window)

        return count <= settings.rate_limit_per_user

    # user context caching
    async def cache_user_context(self, user_id: str, context: dict, expire: int = 1800):
        key = f"user_context:{user_id}"
        await self.set(key, context, expire)

    async def get_user_context(self, user_id: str) -> Optional[dict]:
        key = f"user_context:{user_id}"
        return await self.get(key)


cache_service = CacheService()
