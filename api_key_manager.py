# api_key_manager.py - Google API Key Rotation & Failover Manager

import os
import time
import logging
from typing import List, Optional, Dict
from threading import Lock
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GoogleAPIKeyManager:
    """
    Manages multiple Google API keys with automatic rotation and failover.
    
    Features:
    - Round-robin key rotation (luân phiên)
    - Automatic failover on errors (rate limit, quota exceeded, invalid key)
    - Retry logic with exponential backoff
    - Temporary key blacklisting (auto-recovery after cooldown)
    - Thread-safe operations
    - Usage statistics and monitoring
    """
    
    def __init__(
        self, 
        api_keys: Optional[List[str]] = None,
        max_retries_per_key: int = 3,
        cooldown_minutes: int = 5
    ):
        """
        Initialize API Key Manager.
        
        Args:
            api_keys: List of Google API keys. If None, reads from GOOGLE_API_KEY env var
            max_retries_per_key: Maximum retry attempts per key before switching
            cooldown_minutes: Minutes to wait before re-trying a failed key
        """
        # Load API keys
        if api_keys is None:
            api_keys = self._load_keys_from_env()
        
        if not api_keys:
            raise ValueError(
                "No API keys provided. Set GOOGLE_API_KEY environment variable.\n"
                "Single key: GOOGLE_API_KEY=your_key\n"
                "Multiple keys: GOOGLE_API_KEY=key1,key2,key3"
            )
        
        self.api_keys = api_keys
        self.current_index = 0
        self.max_retries_per_key = max_retries_per_key
        self.cooldown_minutes = cooldown_minutes
        
        # Track key status
        self.key_stats: Dict[str, Dict] = {}
        self.failed_keys: Dict[str, datetime] = {}  # key -> failure_time
        
        # Thread safety
        self.lock = Lock()
        
        # Initialize stats for each key
        for key in self.api_keys:
            key_id = self._get_key_id(key)
            self.key_stats[key_id] = {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'last_used': None,
                'last_error': None
            }
        
        logger.info(f"✅ API Key Manager initialized with {len(self.api_keys)} key(s)")
    
    def _load_keys_from_env(self) -> List[str]:
        """
        Load API keys from GOOGLE_API_KEY environment variable.
        Supports single key or comma-separated multiple keys.
        """
        env_value = os.getenv('GOOGLE_API_KEY', '').strip()
        
        if not env_value or env_value == 'your_google_api_key_here':
            return []
        
        # Split by comma and clean whitespace
        keys = [key.strip() for key in env_value.split(',') if key.strip()]
        
        logger.info(f"📋 Loaded {len(keys)} API key(s) from environment")
        return keys
    
    def _get_key_id(self, key: str) -> str:
        """
        Get shortened key identifier for logging (first 8 chars).
        """
        return key[:8] + "..." if len(key) > 8 else key
    
    def _is_key_available(self, key: str) -> bool:
        """
        Check if a key is available (not in cooldown period).
        """
        if key not in self.failed_keys:
            return True
        
        # Check if cooldown period has passed
        failure_time = self.failed_keys[key]
        cooldown_end = failure_time + timedelta(minutes=self.cooldown_minutes)
        
        if datetime.now() >= cooldown_end:
            # Cooldown period passed, remove from failed list
            del self.failed_keys[key]
            key_id = self._get_key_id(key)
            logger.info(f"🔄 Key {key_id} recovered from cooldown")
            return True
        
        return False
    
    def get_current_key(self) -> str:
        """
        Get current API key (thread-safe).
        Returns the next available key in rotation.
        """
        with self.lock:
            attempts = 0
            max_attempts = len(self.api_keys)
            
            while attempts < max_attempts:
                key = self.api_keys[self.current_index]
                
                if self._is_key_available(key):
                    key_id = self._get_key_id(key)
                    logger.debug(f"🔑 Using key {key_id} (index {self.current_index})")
                    return key
                
                # Key not available, try next
                self.current_index = (self.current_index + 1) % len(self.api_keys)
                attempts += 1
            
            # All keys are in cooldown - return current anyway (will trigger retry logic)
            logger.warning("⚠️ All keys in cooldown, using current key anyway")
            return self.api_keys[self.current_index]
    
    def rotate_key(self, reason: str = "manual rotation") -> str:
        """
        Manually rotate to next key (thread-safe).
        Returns the new current key.
        """
        with self.lock:
            old_key = self.api_keys[self.current_index]
            old_key_id = self._get_key_id(old_key)
            
            self.current_index = (self.current_index + 1) % len(self.api_keys)
            
            new_key = self.api_keys[self.current_index]
            new_key_id = self._get_key_id(new_key)
            
            logger.info(f"🔄 Rotated key: {old_key_id} → {new_key_id} (reason: {reason})")
            return new_key
    
    def mark_key_failed(self, key: str, error: Exception):
        """
        Mark a key as failed and put it in cooldown (thread-safe).
        """
        with self.lock:
            key_id = self._get_key_id(key)
            self.failed_keys[key] = datetime.now()
            
            # Update stats
            if key_id in self.key_stats:
                self.key_stats[key_id]['failed_requests'] += 1
                self.key_stats[key_id]['last_error'] = str(error)
            
            cooldown_end = datetime.now() + timedelta(minutes=self.cooldown_minutes)
            logger.warning(
                f"❌ Key {key_id} marked as failed: {str(error)}\n"
                f"   Cooldown until: {cooldown_end.strftime('%H:%M:%S')}"
            )
    
    def record_success(self, key: str):
        """
        Record successful API call (thread-safe).
        """
        with self.lock:
            key_id = self._get_key_id(key)
            
            if key_id in self.key_stats:
                self.key_stats[key_id]['total_requests'] += 1
                self.key_stats[key_id]['successful_requests'] += 1
                self.key_stats[key_id]['last_used'] = datetime.now()
    
    def record_failure(self, key: str, error: Exception):
        """
        Record failed API call (thread-safe).
        """
        with self.lock:
            key_id = self._get_key_id(key)
            
            if key_id in self.key_stats:
                self.key_stats[key_id]['total_requests'] += 1
                self.key_stats[key_id]['failed_requests'] += 1
                self.key_stats[key_id]['last_error'] = str(error)
    
    def should_retry_with_new_key(self, error: Exception) -> bool:
        """
        Determine if error warrants switching to a new key.
        
        Returns True for:
        - Rate limit errors (429)
        - Quota exceeded errors (429)
        - Invalid API key errors (403, 401)
        - Service unavailable (503)
        """
        error_str = str(error).lower()
        
        # Rate limit / Quota errors
        if any(kw in error_str for kw in [
            'rate limit', 'quota', '429', 'too many requests',
            'resource exhausted', 'limit exceeded'
        ]):
            logger.warning(f"⚠️ Rate limit/Quota error detected: {error}")
            return True
        
        # Authentication errors
        if any(kw in error_str for kw in [
            'invalid api key', 'unauthorized', '401', '403',
            'permission denied', 'api key not valid'
        ]):
            logger.error(f"🔒 Authentication error detected: {error}")
            return True
        
        # Service errors
        if any(kw in error_str for kw in [
            'service unavailable', '503', 'temporarily unavailable',
            'server error', '500', '502', '504'
        ]):
            logger.warning(f"⚠️ Service error detected: {error}")
            return True
        
        # Other errors - don't switch key
        return False
    
    async def execute_with_retry(
        self, 
        async_func, 
        *args, 
        **kwargs
    ):
        """
        Execute an async function with automatic retry and key rotation.
        
        Usage:
            result = await manager.execute_with_retry(
                some_async_function, 
                arg1, arg2, 
                kwarg1=value1
            )
        """
        attempts = 0
        max_total_attempts = len(self.api_keys) * self.max_retries_per_key
        last_error = None
        
        while attempts < max_total_attempts:
            current_key = self.get_current_key()
            
            try:
                # Execute function with current key
                result = await async_func(*args, api_key=current_key, **kwargs)
                
                # Success! Record and return
                self.record_success(current_key)
                return result
                
            except Exception as e:
                attempts += 1
                last_error = e
                
                # Record failure
                self.record_failure(current_key, e)
                
                # Check if we should switch key
                if self.should_retry_with_new_key(e):
                    # Mark key as failed (cooldown)
                    self.mark_key_failed(current_key, e)
                    
                    # Rotate to next key
                    self.rotate_key(reason=f"error: {str(e)[:50]}")
                    
                    # Small delay before retry
                    await asyncio.sleep(0.5)
                else:
                    # Error not related to API key - raise immediately
                    logger.error(f"❌ Non-recoverable error: {e}")
                    raise
        
        # All attempts failed
        logger.error(f"❌ All retry attempts exhausted ({max_total_attempts} attempts)")
        raise last_error
    
    def get_statistics(self) -> Dict:
        """
        Get usage statistics for all keys.
        """
        with self.lock:
            stats = {
                'total_keys': len(self.api_keys),
                'active_keys': len([k for k in self.api_keys if self._is_key_available(k)]),
                'failed_keys': len(self.failed_keys),
                'current_key_index': self.current_index,
                'key_details': {}
            }
            
            for key in self.api_keys:
                key_id = self._get_key_id(key)
                key_data = self.key_stats.get(key_id, {})
                
                stats['key_details'][key_id] = {
                    'status': 'available' if self._is_key_available(key) else 'cooldown',
                    'total_requests': key_data.get('total_requests', 0),
                    'successful_requests': key_data.get('successful_requests', 0),
                    'failed_requests': key_data.get('failed_requests', 0),
                    'success_rate': (
                        f"{(key_data.get('successful_requests', 0) / key_data.get('total_requests', 1) * 100):.1f}%"
                        if key_data.get('total_requests', 0) > 0 else "N/A"
                    ),
                    'last_used': key_data.get('last_used').strftime('%Y-%m-%d %H:%M:%S') 
                                 if key_data.get('last_used') else 'Never',
                    'last_error': key_data.get('last_error', 'None')
                }
            
            return stats
    
    def print_statistics(self):
        """
        Print formatted statistics to console.
        """
        stats = self.get_statistics()
        
        print("\n" + "="*80)
        print("📊 GOOGLE API KEY MANAGER - STATISTICS")
        print("="*80)
        print(f"Total Keys: {stats['total_keys']}")
        print(f"Active Keys: {stats['active_keys']}")
        print(f"Keys in Cooldown: {stats['failed_keys']}")
        print(f"Current Key Index: {stats['current_key_index']}")
        print("\n" + "-"*80)
        print("KEY DETAILS:")
        print("-"*80)
        
        for key_id, details in stats['key_details'].items():
            print(f"\n🔑 Key: {key_id}")
            print(f"   Status: {'✅ ' + details['status'] if details['status'] == 'available' else '❌ ' + details['status']}")
            print(f"   Total Requests: {details['total_requests']}")
            print(f"   Successful: {details['successful_requests']}")
            print(f"   Failed: {details['failed_requests']}")
            print(f"   Success Rate: {details['success_rate']}")
            print(f"   Last Used: {details['last_used']}")
            if details['last_error'] != 'None':
                print(f"   Last Error: {details['last_error'][:60]}...")
        
        print("\n" + "="*80 + "\n")


# Global manager instance (singleton pattern)
_global_manager: Optional[GoogleAPIKeyManager] = None


def get_api_key_manager() -> GoogleAPIKeyManager:
    """
    Get or create global API key manager instance (singleton).
    """
    global _global_manager
    
    if _global_manager is None:
        _global_manager = GoogleAPIKeyManager()
    
    return _global_manager


def reset_api_key_manager():
    """
    Reset global manager (useful for testing or re-initialization).
    """
    global _global_manager
    _global_manager = None


# For convenience - import asyncio if needed
try:
    import asyncio
except ImportError:
    logger.warning("asyncio not available - execute_with_retry will not work")
