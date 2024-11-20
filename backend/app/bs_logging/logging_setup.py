import logging

def setup_logging(log_level="INFO"):
    """Set up logging configuration with the specified log level."""
    level = getattr(logging, log_level.upper())
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger(__name__)