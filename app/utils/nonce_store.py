"""
Redis-backed Nonce Storage for Replay Protection.
Supports in-memory fallback for development.
"""
import redis
import logging
import os
import time

class NonceStore:
    def __init__(self, redis_url=None, default_ttl=300):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.client = None
        self._local_cache = set() # Fallback for dev/testing only
        self._local_timestamps = {} 

    def _get_client(self):
        if self.client:
            return self.client
            
        # Try to get from config if not provided explicitly
        if not self.redis_url:
            self.redis_url = os.getenv('RATELIMIT_STORAGE_URI', 'redis://localhost:6379/2')
            
        if self.redis_url and self.redis_url.startswith('redis://'):
            try:
                self.client = redis.from_url(self.redis_url)
            except Exception as e:
                logging.getLogger('app').warning(f"Failed to connect to Redis for NonceStore, falling back to memory: {e}")
                self.client = None
        
        return self.client

    def check_and_set(self, nonce, ttl=None):
        """
        Checks if nonce has been used. If not, marks it as used.
        Returns:
            True if nonce is fresh (allowed)
            False if nonce is reused (replay attack)
        """
        if not nonce:
            return True 
            
        ttl = ttl or self.default_ttl
        client = self._get_client()
        
        if client:
            key = f"nonce:{nonce}"
            try:
                # set(name, value, ex=ttl, nx=True) returns True if set, None if not set
                is_set = client.set(key, 1, ex=ttl, nx=True)
                return bool(is_set)
            except Exception as e:
                logging.getLogger('error').error(f"Redis error in check_and_set: {e}")
                # If Redis fails, we should technically fail securely (block), 
                # but depending on policy, might fallback. 
                # Given this is security control, we return False (block access) to be safe.
                return False
        else:
            # Memory fallback
            now = time.time()
            self._cleanup_local_cache(now, ttl)
            
            if nonce in self._local_cache:
                return False
                
            self._local_cache.add(nonce)
            self._local_timestamps[nonce] = now
            return True

    def _cleanup_local_cache(self, now, ttl):
        # Basic cleanup for memory leak prevention in dev
        expired = [n for n, t in self._local_timestamps.items() if now - t > ttl]
        for n in expired:
            self._local_cache.discard(n)
            self._local_timestamps.pop(n, None)

# Global instance
nonce_store = NonceStore()
