import time
from threading import Lock
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Manages rate limiting for API usage."""
    REQUESTS_PER_SECOND = 1

    def __init__(self, tokens_per_minute=500_000, tokens_per_month=1_000_000_000):
        self.TOKENS_PER_MINUTE = tokens_per_minute
        self.TOKENS_PER_MONTH = tokens_per_month
        self.token_lock = Lock()
        self.current_minute_tokens = 0
        self.monthly_tokens = 0
        self.minute_start_time = time.time()
        self.last_request_time = time.time()

    def check(self, tokens_used: int):
        """Ensures the request complies with rate limits."""
        with self.token_lock:
            now = time.time()

            # Enforce request rate
            time_since_last_request = now - self.last_request_time
            if time_since_last_request < 1 / self.REQUESTS_PER_SECOND:
                time.sleep((1 / self.REQUESTS_PER_SECOND) - time_since_last_request)

            # Reset minute-based counters if needed
            if now - self.minute_start_time >= 60:
                self.current_minute_tokens = 0
                self.minute_start_time = now

            # Check minute token limits
            if self.current_minute_tokens + tokens_used > self.TOKENS_PER_MINUTE:
                logger.warning("Minute token limit reached. Pausing...")
                time.sleep(60 - (now - self.minute_start_time))
                self.current_minute_tokens = 0

            # Check monthly token limits
            self.current_minute_tokens += tokens_used
            self.monthly_tokens += tokens_used
            if self.monthly_tokens > self.TOKENS_PER_MONTH:
                logger.error("Monthly token limit exceeded!")
                raise RuntimeError("Monthly token limit exceeded!")

            self.last_request_time = time.time()