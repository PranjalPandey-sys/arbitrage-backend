"""Helper utilities for the arbitrage detection system."""

import re
import asyncio
from typing import List, Optional, Union, Any
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # Remove special characters that might interfere with matching
    cleaned = re.sub(r'[^\w\s\-.]', ' ', cleaned)
    
    return cleaned


def extract_numeric_value(text: str) -> Optional[float]:
    """Extract first numeric value from text."""
    if not text:
        return None
    
    # Find decimal numbers
    pattern = r'[-+]?\d*\.?\d+'
    match = re.search(pattern, str(text))
    
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    
    return None


def is_valid_odds(odds: Union[str, float, int]) -> bool:
    """Check if odds value is valid."""
    try:
        odds_value = float(odds)
        return 1.01 <= odds_value <= 1000.0
    except (ValueError, TypeError):
        return False


def normalize_url(url: str, base_url: str = "") -> str:
    """Normalize and validate URL."""
    if not url:
        return ""
    
    # If relative URL, make it absolute
    if url.startswith('/') and base_url:
        url = urljoin(base_url, url)
    
    # Basic URL validation
    try:
        parsed = urlparse(url)
        if parsed.scheme in ('http', 'https') and parsed.netloc:
            return url
    except:
        pass
    
    return ""


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format currency amount for display."""
    if currency == "USD":
        return f"${amount:.2f}"
    elif currency == "EUR":
        return f"€{amount:.2f}"
    elif currency == "GBP":
        return f"£{amount:.2f}"
    else:
        return f"{amount:.2f} {currency}"


def calculate_implied_probability(odds: float) -> Optional[float]:
    """Calculate implied probability from decimal odds."""
    if odds <= 1.0:
        return None
    
    try:
        probability = 1.0 / odds
        return round(probability * 100, 2)  # Return as percentage
    except (ZeroDivisionError, TypeError):
        return None


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format value as percentage."""
    return f"{value:.{decimal_places}f}%"


def time_until_event(event_time: Optional[datetime]) -> Optional[str]:
    """Get human-readable time until event."""
    if not event_time:
        return None
    
    now = datetime.now()
    delta = event_time - now
    
    if delta.total_seconds() < 0:
        return "Event started"
    
    if delta.days > 0:
        return f"{delta.days}d {delta.seconds // 3600}h"
    elif delta.seconds >= 3600:
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    elif delta.seconds >= 60:
        minutes = delta.seconds // 60
        return f"{minutes}m"
    else:
        return "Starting soon"


def validate_email(email: str) -> bool:
    """Validate email address format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    return sanitized or "untitled"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parse duration string like '1h30m' or '90m' into timedelta."""
    if not duration_str:
        return None
    
    # Pattern for hours and minutes
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?'
    match = re.match(pattern, duration_str.lower().strip())
    
    if match:
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        
        if hours > 0 or minutes > 0:
            return timedelta(hours=hours, minutes=minutes)
    
    return None


def format_duration(td: timedelta) -> str:
    """Format timedelta as human-readable duration."""
    total_seconds = int(td.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"


def batch_items(items: List[Any], batch_size: int) -> List[List[Any]]:
    """Split items into batches of specified size."""
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i + batch_size])
    return batches


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Perform safe division with default value for zero denominator."""
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ZeroDivisionError):
        return default


def round_to_nearest(value: float, nearest: float = 0.01) -> float:
    """Round value to nearest specified increment."""
    return round(value / nearest) * nearest


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp value between min and max bounds."""
    return max(min_value, min(value, max_value))


def retry_async(max_attempts: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """Decorator for retrying async functions with exponential backoff."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    
            raise last_exception
        return wrapper
    return decorator


def deep_get(dictionary: dict, keys: str, default=None):
    """Get nested dictionary value using dot notation."""
    keys = keys.split('.')
    for key in keys:
        if isinstance(dictionary, dict) and key in dictionary:
            dictionary = dictionary[key]
        else:
            return default
    return dictionary


def merge_dicts(*dicts: dict) -> dict:
    """Merge multiple dictionaries, with later ones taking precedence."""
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0
    
    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        now = datetime.now().timestamp()
        time_since_last = now - self.last_called
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_called = datetime.now().timestamp()


def detect_language(text: str) -> str:
    """Basic language detection (simplified implementation)."""
    if not text:
        return "unknown"
    
    # Very basic detection based on common words
    english_words = {"the", "and", "is", "in", "to", "of", "a", "that", "it", "with"}
    spanish_words = {"el", "de", "que", "y", "en", "un", "es", "se", "no", "te"}
    
    words = set(text.lower().split()[:10])  # Check first 10 words
    
    english_matches = len(words.intersection(english_words))
    spanish_matches = len(words.intersection(spanish_words))
    
    if english_matches > spanish_matches:
        return "en"
    elif spanish_matches > 0:
        return "es"
    else:
        return "unknown"


def generate_hash(text: str, length: int = 8) -> str:
    """Generate short hash from text."""
    import hashlib
    
    hash_object = hashlib.md5(text.encode())
    return hash_object.hexdigest()[:length]