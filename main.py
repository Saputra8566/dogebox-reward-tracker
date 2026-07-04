#!/usr/bin/env python3
"""DogeBox Reward Tracker — entry point.

Loads configuration, initializes logging and the database, builds the
multi-user Telegram bot (with the daily scheduler) and starts long-polling.

Run directly:  python3 main.py
Run under PM2: pm2 start ecosystem.config.js
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when launched from any cwd (e.g. PM2).
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.telegram_bot import build_application  # noqa: E402
from database.db import Database  # noqa: E402
from utils.config import Config, ConfigError  # noqa: E402
from utils.logging_config import setup_logging  # noqa: E402


def main() -> int:
    """Program entry point. Returns a process exit code."""
    try:
        config = Config.load()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    logger = setup_logging(config.log_dir, config.log_level)
    logger.info("Starting DogeBox Reward Tracker")
    logger.info(
        "Timezone=%s | Merkle=%s | DB=%s",
        config.timezone,
        config.merkle_base_url,
        config.database_path,
    )

    database = Database(config.database_path)
    database.initialize()

    application = build_application(config, database)

    try:
        application.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested")
    finally:
        database.close()
        logger.info("DogeBox Reward Tracker stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
