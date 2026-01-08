#Importing
import logging
from logging.handlers import RotatingFileHandler

#Logging configuration
LOG_FILE = "NBA_ticker.log"
LOG_MAX_BYTES = 5 * 1024 * 1024 
LOG_BACKUP_COUNT = 5 # Rotating the last 10 recent logs renames a new log after 5 MB

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Don't re-add handlers if logger already has them
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Writing to NBA ticker log and rotating
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)

    # live log viewing
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger