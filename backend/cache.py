"""
缓存模块

支持两种缓存策略：
1. 内存缓存（默认）：基于 dict + TTL，适合单实例部署和开发调试
2. Redis 缓存（可选）：适合分布式/Serverless 多实例场景

通过环境变量 CACHE_TYPE 切换。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import threading
from typing import Any, Optional

from config import settings

logger = logging.getLogger("resume-api")


class MemoryCache:
    """基于内存的简单 TTL 缓存，线程安全。"""

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expire_at, value = entry
            if time.monotonic() > expire_at:
                del self._store[key]
                return None
            logger.info(f"内存缓存命中: {key}")
            return value

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)
            logger.debug(f"内存缓存写入: {key} (TTL={ttl}s)")

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)


class RedisCache:
    """基于 Redis 的缓存实现。"""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client: Any = None

    @property
    def client(self):
        """懒初始化 Redis 客户端。"""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self._redis_url, decode_responses=True)
                # 验证连接
                self._client.ping()
                logger.info(f"Redis 连接成功: {self._redis_url}")
            except ImportError:
                raise RuntimeError("redis 包未安装，请执行 pip install redis")
            except Exception as e:
                logger.error(f"Redis 连接失败 ({self._redis_url}): {e}")
                raise
        return self._client

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            if value is None:
                return None
            logger.info(f"Redis 缓存命中: {key}")
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.warning(f"Redis 缓存 JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"Redis 读取失败: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        try:
            data = json.dumps(value, ensure_ascii=False, default=str)
            self.client.setex(key, ttl, data)
            logger.info(f"Redis 缓存写入: {key} (TTL={ttl}s)")
        except Exception as e:
            logger.error(f"Redis 写入失败: {e}")

    def delete(self, key: str) -> None:
        try:
            self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis 删除失败: {e}")


class CacheManager:
    """
    统一缓存管理器。

    根据配置自动选择内存或 Redis 存储后端。
    """

    def __init__(self):
        if settings.cache_type == "redis":
            try:
                self._backend = RedisCache(settings.redis_url)
            except Exception:
                logger.warning("Redis 初始化失败，回退到内存缓存")
                self._backend = MemoryCache()
        else:
            self._backend = MemoryCache()

    @staticmethod
    def make_key(prefix: str, *parts: str) -> str:
        raw = ":".join([prefix] + list(parts))
        return raw

    @staticmethod
    def content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def get(self, key: str) -> Optional[Any]:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or settings.cache_ttl
        self._backend.set(key, value, ttl)

    def delete(self, key: str) -> None:
        self._backend.delete(key)


# 全局缓存实例
cache = CacheManager()
