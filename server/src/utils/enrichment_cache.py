"""
Caching system for API enrichment results
Reduces redundant API calls and improves performance
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger


class EnrichmentCache:
    """
    In-memory cache for API enrichment results with TTL support
    Cache key is based on title + authors to identify duplicate references
    """
    
    def __init__(self, ttl_hours: int = 24, max_size: int = 10000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_hours = ttl_hours
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        
    def _generate_cache_key(self, title: str, authors: list) -> str:
        """
        Generate a unique cache key from title and authors
        """
        # Normalize: lowercase, remove extra spaces
        title_clean = ' '.join(title.lower().split()) if title else ""
        
        # Sort and join author names for consistency
        authors_clean = []
        for author in authors:
            if isinstance(author, str):
                authors_clean.append(' '.join(author.lower().split()))
            elif isinstance(author, dict):
                name = author.get('full_name') or f"{author.get('surname', '')} {author.get('given_name', '')}".strip()
                authors_clean.append(' '.join(name.lower().split()))
        
        authors_str = '|'.join(sorted(authors_clean))
        
        # Create hash of title + authors
        key_str = f"{title_clean}::{authors_str}"
        cache_key = hashlib.md5(key_str.encode()).hexdigest()
        
        return cache_key
    
    def get(self, title: str, authors: list) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached enrichment result
        """
        if not title:
            return None
            
        cache_key = self._generate_cache_key(title, authors)
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            
            # Check if entry has expired
            if datetime.now() < entry['expires_at']:
                self.hits += 1
                logger.debug(f"✅ Cache HIT for: {title[:50]}... (key: {cache_key[:8]})")
                return entry['data']
            else:
                # Expired entry
                del self.cache[cache_key]
                logger.debug(f"⏰ Cache EXPIRED for: {title[:50]}...")
        
        self.misses += 1
        logger.debug(f"❌ Cache MISS for: {title[:50]}... (key: {cache_key[:8]})")
        return None
    
    def set(self, title: str, authors: list, enrichment_data: Dict[str, Any]):
        """
        Store enrichment result in cache
        """
        if not title:
            return
        
        # Check cache size limit
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        cache_key = self._generate_cache_key(title, authors)
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)
        
        self.cache[cache_key] = {
            'data': enrichment_data,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
        
        logger.debug(f"💾 Cached enrichment for: {title[:50]}... (key: {cache_key[:8]})")
    
    def _evict_oldest(self):
        """
        Remove oldest cache entries when max size is reached
        """
        # Sort by created_at and remove oldest 10%
        sorted_entries = sorted(
            self.cache.items(),
            key=lambda x: x[1]['created_at']
        )
        
        num_to_remove = max(1, len(sorted_entries) // 10)
        
        for i in range(num_to_remove):
            key = sorted_entries[i][0]
            del self.cache[key]
        
        logger.info(f"🧹 Evicted {num_to_remove} oldest cache entries")
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("🗑️ Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "ttl_hours": self.ttl_hours
        }
    
    def cleanup_expired(self):
        """
        Remove all expired entries
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now >= entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


# Global cache instance
enrichment_cache = EnrichmentCache(ttl_hours=24, max_size=10000)


