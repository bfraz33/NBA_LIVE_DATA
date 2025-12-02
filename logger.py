import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "nfl_ticker.log"
LOG_MAX_BYTES = 5 * 1024 * 1024 
LOG_BACKUP_COUNT = 3  # Keep up to 3 rotated logs

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Don't re-add handlers if logger already has them
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # File handler (with rotation)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)

    # Console handler (for live viewing)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger