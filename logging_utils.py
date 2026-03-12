import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict


def setup_logging_from_config(config: Dict[str, Any], logger_name: str = "icecast_checker") -> logging.Logger:
    """
    Создаёт и настраивает логгер по данным из config["logging"].
    Используется и в icecast_checker, и в custom_checker.
    """
    log_config = (config or {}).get("logging", {})

    log_file_template = log_config.get("log_file", "icecast_check.log")
    log_level = log_config.get("log_level", "INFO")
    max_size = log_config.get("max_file_size", 10 * 1024 * 1024)
    backup_count = log_config.get("backup_count", 5)

    now = datetime.now()
    log_file = log_file_template.format(
        YYYY=now.strftime("%Y"),
        MM=now.strftime("%m"),
        DD=now.strftime("%d"),
    )

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Чтобы при повторных вызовах не плодить хендлеры
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding="utf-8",
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

