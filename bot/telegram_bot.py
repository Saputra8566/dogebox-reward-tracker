"""Build and wire the Telegram :class:`Application` (multi-user).

Constructs the database, repositories and services once and stores them in
``application.bot_data`` so every handler and the scheduler share the same
instances. An ``AIORateLimiter`` is attached so the bot stays within Telegram's
flood limits when many users are active.
"""

from __future__ import annotations

from telegram.ext import AIORateLimiter, Application, ApplicationBuilder

from bot.commands import register_all_handlers
from database.db import Database
from database.repositories import RewardCacheRepository, WalletRepository
from services.report_service import ReportService
from services.reward_lookup import EpochLookupService
from services.scheduler import register_daily_job
from utils.config import Config
from utils.logging_config import get_logger

logger = get_logger(__name__)


def build_application(config: Config, database: Database) -> Application:
    """Construct the fully-wired Telegram application."""
    wallet_repo = WalletRepository(database)
    cache_repo = RewardCacheRepository(database)
    lookup = EpochLookupService(config, cache_repo)
    report_service = ReportService(wallet_repo, cache_repo, lookup)

    application = (
        ApplicationBuilder()
        .token(config.telegram_bot_token)
        .rate_limiter(AIORateLimiter())
        .build()
    )

    application.bot_data.update(
        {
            "config": config,
            "db": database,
            "wallet_repo": wallet_repo,
            "cache_repo": cache_repo,
            "lookup": lookup,
            "report_service": report_service,
        }
    )

    register_all_handlers(application)
    register_daily_job(application, config)

    logger.info("Telegram application built and handlers registered")
    return application
