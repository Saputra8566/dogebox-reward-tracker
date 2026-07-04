"""Structured logging setup.

Logs go to both stdout (captured by PM2) and a rotating file so history
survives restarts. Call :func:`setup_logging` exactly once at start-up.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure the root logger with console + rotating file handlers."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "dogebox-reward-tracker.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    return logging.getLogger("dogebox")


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced child logger (e.g. ``get_logger(__name__)``)."""
    return logging.getLogger(f"dogebox.{name}")
