import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger rotatorio que escribe en logs/app.log
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Ya está configurado, no duplicar handlers
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,   # 2 MB
        backupCount=5,        # guarda hasta 5 ficheros de backup
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s — %(name)s — %(levelname)s — %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger
