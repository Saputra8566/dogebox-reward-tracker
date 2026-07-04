"""Daily scheduler built on python-telegram-bot's JobQueue (multi-user).

The job is (re)registered every time the process starts, so it survives
restarts (PM2 restart, crash recovery, redeploy). Reward history is persisted
in SQLite, so a restart never loses data.

Each day the job:
    1. Warms the shared reward cache for every monitored address (one pass).
    2. Sends each user their own daily report.
One user's failure never stops the others.
"""

from __future__ import annotations

import asyncio

import pytz
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from bot.formatting import format_daily_report
from database.repositories import WalletRepository
from services.report_service import ReportService
from services.reward_lookup import EpochLookupService
from utils.config import Config
from utils.logging_config import get_logger

logger = get_logger(__name__)

_JOB_NAME = "daily-reward-sync"


async def _daily_sync_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue callback: warm the cache, then push per-user daily reports."""
    app = context.application
    lookup: EpochLookupService = app.bot_data["lookup"]
    report_service: ReportService = app.bot_data["report_service"]
    wallet_repo: WalletRepository = app.bot_data["wallet_repo"]

    logger.info("Running scheduled daily reward sync")
    try:
        addresses = await asyncio.to_thread(wallet_repo.all_distinct_addresses)
        if not addresses:
            logger.info("Daily sync skipped: no wallets monitored")
            return

        # One fetch warms the shared cache (latest epochs) for everyone.
        await lookup.sync_latest(addresses)

        user_ids = await asyncio.to_thread(wallet_repo.all_user_ids)
        sent = 0
        for user_id in user_ids:
            try:
                report = await report_service.daily_report(user_id)
                if report is None:
                    continue
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=format_daily_report(report),
                    parse_mode=ParseMode.HTML,
                )
                sent += 1
            except Exception:  # noqa: BLE001 - isolate per-user failures
                logger.exception("Daily push failed for user %s", user_id)
        logger.info("Daily reports pushed to %d/%d users", sent, len(user_ids))
    except Exception:  # noqa: BLE001 - never let the scheduler die
        logger.exception("Daily reward sync failed")


def register_daily_job(application: Application, config: Config) -> None:
    """Register (or replace) the daily reward-sync job on the JobQueue."""
    job_queue = application.job_queue
    if job_queue is None:  # pragma: no cover - requires the [job-queue] extra
        logger.error(
            "JobQueue unavailable. Install 'python-telegram-bot[job-queue]' "
            "to enable the daily scheduler."
        )
        return

    for job in job_queue.get_jobs_by_name(_JOB_NAME):
        job.schedule_removal()

    run_time = config.daily_report_time.replace(tzinfo=pytz.timezone(config.timezone))
    job_queue.run_daily(_daily_sync_job, time=run_time, name=_JOB_NAME)
    logger.info(
        "Scheduled daily sync at %s %s",
        config.daily_report_time.strftime("%H:%M"),
        config.timezone,
    )
