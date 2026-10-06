import logging
from logging.handlers import RotatingFileHandler

LOG_FILE_MAX_BYTES = 2 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 4


def setup_logging():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                "app.log",
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
            ),
            logging.StreamHandler()
        ],
        force=True
    )