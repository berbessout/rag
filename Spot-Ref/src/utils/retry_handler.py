import time
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type, Union
from threading import Lock
from collections import defaultdict
import os

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter to control API calls per service."""
    
    def __init__(self):
        self._locks = defaultdict(Lock)
        self._last_call = defaultdict(float)
        self._call_counts = defaultdict(int)
        self._reset_times = defaultdict(float)
    
    def wait_if_needed(self, service: str, max_calls_per_minute: int = 60):
        """Wait if rate limit would be exceeded."""
        with self._locks[service]:
            current_time = time.time()
            
            # Reset counter if a minute has passed
            if current_time - self._reset_times[service] >= 60:
                self._call_counts[service] = 0
                self._reset_times[service] = current_time
            
            # Check if we're at the limit
            if self._call_counts[service] >= max_calls_per_minute:
                wait_time = 60 - (current_time - self._reset_times[service])
                if wait_time > 0:
                    logger.info(f"Rate limit reached for {service}, waiting {wait_time:.2f} seconds")
                    time.sleep(wait_time)
                    self._call_counts[service] = 0
                    self._reset_times[service] = time.time()
            
            self._call_counts[service] += 1
            self._last_call[service] = current_time

# Global rate limiter instance
rate_limiter = RateLimiter()

def retry_with_backoff(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    rate_limit_service: Optional[str] = None,
    rate_limit_per_minute: int = 60
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Exception types to catch and retry
        rate_limit_service: Name of service for rate limiting
        rate_limit_per_minute: Max calls per minute for rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    # Apply rate limiting if specified
                    if rate_limit_service:
                        rate_limiter.wait_if_needed(rate_limit_service, rate_limit_per_minute)
                    
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Log success after retries
                    if attempt > 0:
                        logger.info(f"Function {func.__name__} succeeded after {attempt} retries")
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries. Last error: {e}")
                        raise e
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                    
                except Exception as e:
                    # Don't retry unexpected exceptions
                    logger.error(f"Function {func.__name__} failed with unexpected error: {e}")
                    raise e
            
            # This shouldn't be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator

def get_retry_config_from_env() -> Dict[str, Any]:
    """Get retry configuration from environment variables."""
    return {
        'max_retries': int(os.getenv('RETRY_MAX_ATTEMPTS', '3')),
        'backoff_factor': float(os.getenv('RETRY_BACKOFF_FACTOR', '2.0')),
        'initial_delay': float(os.getenv('RETRY_INITIAL_DELAY', '1.0')),
        'max_delay': float(os.getenv('RETRY_MAX_DELAY', '60.0')),
        'openai_rate_limit': int(os.getenv('API_RATE_LIMIT_OPENAI', '10')),
        'sharepoint_rate_limit': int(os.getenv('API_RATE_LIMIT_SP', '50'))
    }

# Pre-configured decorators for common use cases
def retry_openai_call(func: Callable) -> Callable:
    """Retry decorator specifically for OpenAI API calls."""
    config = get_retry_config_from_env()
    return retry_with_backoff(
        max_retries=config['max_retries'],
        backoff_factor=config['backoff_factor'],
        initial_delay=config['initial_delay'],
        max_delay=config['max_delay'],
        exceptions=(Exception,),  # OpenAI exceptions
        rate_limit_service='openai',
        rate_limit_per_minute=config['openai_rate_limit']
    )(func)

def retry_sharepoint_call(func: Callable) -> Callable:
    """Retry decorator specifically for SharePoint API calls."""
    config = get_retry_config_from_env()
    return retry_with_backoff(
        max_retries=config['max_retries'],
        backoff_factor=config['backoff_factor'],
        initial_delay=config['initial_delay'],
        max_delay=config['max_delay'],
        exceptions=(Exception,),  # SharePoint exceptions
        rate_limit_service='sharepoint',
        rate_limit_per_minute=config['sharepoint_rate_limit']
    )(func)

def retry_file_operation(func: Callable) -> Callable:
    """Retry decorator for file operations without rate limiting."""
    def decorator_wrapper(*args, **kwargs):
        config = get_retry_config_from_env()
        max_retries = config['max_retries']
        backoff_factor = config['backoff_factor']
        initial_delay = config['initial_delay']
        max_delay = config['max_delay']
        
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Function {func.__name__} succeeded after {attempt} retries")
                return result
                
            except (IOError, OSError, FileNotFoundError) as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"Function {func.__name__} failed after {max_retries} retries. Last error: {e}")
                    raise e
                
                logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.info(f"Retrying in {delay:.2f} seconds...")
                
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
                
            except Exception as e:
                # Don't retry unexpected exceptions
                logger.error(f"Function {func.__name__} failed with unexpected error: {e}")
                raise e
        
        raise last_exception
    
    return decorator_wrapper 