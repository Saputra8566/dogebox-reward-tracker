"""Application configuration loaded from environment variables / ``.env``.

The :class:`Config` dataclass is the single source of truth for runtime
settings. Load it once at start-up with :meth:`Config.load` and pass the
instance around rather than reading ``os.environ`` throughout the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of the ``utils`` package directory.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


def _resolve_path(value: str) -> Path:
    """Resolve *value* against the project root when it is relative."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path)


def _parse_time(value: str) -> time:
    """Parse an ``HH:MM`` string into a :class:`datetime.time`."""
    try:
        hour_str, minute_str = value.strip().split(":", 1)
        return time(hour=int(hour_str), minute=int(minute_str))
    except (ValueError, AttributeError) as exc:  # pragma: no cover - defensive
        raise ConfigError(
            f"DAILY_REPORT_TIME must look like 'HH:MM', got: {value!r}"
        ) from exc


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration for the bot."""

    telegram_bot_token: str
    telegram_chat_id: str | None
    database_path: Path
    timezone: str
    daily_report_time: time
    max_wallets_per_user: int
    merkle_base_url: str
    dashboard_base_url: str
    token_decimals: int
    epoch_lookback_days: int
    request_timeout: float
    log_level: str
    log_dir: Path

    @classmethod
    def load(cls, env_file: str | os.PathLike[str] | None = None) -> "Config":
        """Build a :class:`Config` from the environment."""
        if env_file is not None:
            load_dotenv(env_file)
        else:
            default_env = PROJECT_ROOT / ".env"
            load_dotenv(default_env if default_env.exists() else None)

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ConfigError(
                "TELEGRAM_BOT_TOKEN is required. Copy .env.example to .env "
                "and set your bot token."
            )

        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None

        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            database_path=_resolve_path(
                os.getenv("DATABASE_PATH", "database/dogebox.db")
            ),
            timezone=os.getenv("TIMEZONE", "Asia/Jakarta").strip(),
            daily_report_time=_parse_time(os.getenv("DAILY_REPORT_TIME", "07:30")),
            max_wallets_per_user=int(os.getenv("MAX_WALLETS_PER_USER", "20")),
            merkle_base_url=os.getenv(
                "MERKLE_BASE_URL", "https://merkle.openforge.one"
            ).rstrip("/"),
            dashboard_base_url=os.getenv(
                "DASHBOARD_BASE_URL", "https://dash.openforge.one"
            ).rstrip("/"),
            token_decimals=int(os.getenv("TOKEN_DECIMALS", "18")),
            epoch_lookback_days=int(os.getenv("EPOCH_LOOKBACK_DAYS", "14")),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT", "20")),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            log_dir=_resolve_path(os.getenv("LOG_DIR", "logs")),
        )
