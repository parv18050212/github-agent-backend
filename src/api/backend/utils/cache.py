"""
Redis Cache Utility
Provides caching for API responses using Upstash Redis
"""
import os
import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
import redis
from datetime import timedelta


class RedisCache:
    """Redis cache client for API caching"""
    
    _instance: Optional['RedisCache'] = None
    _client: Optional[redis.Redis] = None
    
    # Cache TTL settings (in seconds)
    TTL_SHORT = 30          # 30 seconds - for frequently changing data
    TTL_MEDIUM = 300        # 5 minutes - for moderately changing data
    TTL_LONG = 3600         # 1 hour - for stable data
    TTL_VERY_LONG = 86400   # 24 hours - for rarely changing data
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        redis_url = os.getenv("REDIS_URL")
        
        if not redis_url:
            print("⚠️  REDIS_URL not set - caching disabled")
            return
        
        try:
            self._client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=1,
                socket_connect_timeout=1
            )
            # Test connection
            self._client.ping()
            print("✅ Redis cache connected")
        except Exception as e:
            # Retry with TLS if using standard redis://
            if redis_url.startswith("redis://"):
                print(f"⚠️  Standard Redis connection failed ({e}). Retrying with TLS...")
                try:
                    tls_url = redis_url.replace("redis://", "rediss://")
                    self._client = redis.from_url(
                        tls_url,
                        decode_responses=True,
                        socket_timeout=1,
                        socket_connect_timeout=1,
                        ssl_cert_reqs=None  # Allow self-signed/cloud certs
                    )
                    self._client.ping()
                    print("✅ Redis cache connected (via TLS upgrade)")
                    return
                except Exception as tls_e:
                     print(f"❌ Redis TLS upgrade also failed: {tls_e}")
            
            print(f"⚠️  Redis connection failed: {e} - caching disabled")
            self._client = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        return self._client
    
    @property
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except:
            return False
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from prefix and arguments"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"hackeval:{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._client:
            return None
        
        try:
            data = self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"⚠️  Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = TTL_MEDIUM) -> bool:
        """Set value in cache with TTL"""
        if not self._client:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            self._client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            print(f"⚠️  Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self._client:
            return False
        
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            print(f"⚠️  Cache delete error: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self._client:
            return 0
        
        try:
            keys = self._client.keys(f"hackeval:{pattern}*")
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            print(f"⚠️  Cache delete pattern error: {e}")
            return 0
    
    def invalidate_project(self, project_id: str):
        """Invalidate all cache entries for a project"""
        self.delete_pattern(f"project:{project_id}")
        self.delete_pattern("projects:")
        self.delete_pattern("leaderboard:")
        self.delete_pattern("stats:")
    
    def invalidate_all(self):
        """Clear all cache entries"""
        self.delete_pattern("")


# Global cache instance
cache = RedisCache()


def cached(prefix: str, ttl: int = RedisCache.TTL_MEDIUM):
    """
    Decorator to cache function results
    
    Usage:
        @cached("projects", ttl=300)
        def get_projects():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Skip cache if disabled
            if not cache.is_connected:
                return await func(*args, **kwargs)
            
            # Generate cache key
            key = cache._make_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Skip cache if disabled
            if not cache.is_connected:
                return func(*args, **kwargs)
            
            # Generate cache key
            key = cache._make_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
