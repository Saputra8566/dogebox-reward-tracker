"""Reporting commands: /report daily and /report weekly (per-user, DM-only)."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from bot.formatting import format_daily_report, format_weekly_report
from services.report_service import ReportService
from utils.logging_config import get_logger

logger = get_logger(__name__)

_WEEKLY_EPOCHS = 7


def _report_service(context: ContextTypes.DEFAULT_TYPE) -> ReportService:
    return context.application.bot_data["report_service"]


async def _no_wallets(update: Update) -> None:
    await update.message.reply_text(
        "📭 You are not monitoring any wallets yet. Add one with /add first."
    )


async def _report_daily(update: Update, service: ReportService, uid: str) -> None:
    report = await service.daily_report(uid)
    if report is None:
        if not await service.addresses(uid):
            await _no_wallets(update)
        else:
            await update.message.reply_text(
                "🔍 No epoch data was found for the recent dates. "
                "OpenForge may be temporarily unavailable — try again later."
            )
        return
    await update.message.reply_text(
        format_daily_report(report), parse_mode=ParseMode.HTML
    )


async def _report_weekly(update: Update, service: ReportService, uid: str) -> None:
    report = await service.weekly_report(uid, _WEEKLY_EPOCHS)
    if report is None:
        if not await service.addresses(uid):
            await _no_wallets(update)
        else:
            await update.message.reply_text(
                "🔍 No epoch data was found for the recent dates. Try again later."
            )
        return
    await update.message.reply_text(
        format_weekly_report(report, span_label=str(_WEEKLY_EPOCHS)),
        parse_mode=ParseMode.HTML,
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/report daily`` and ``/report weekly``."""
    uid = str(update.effective_user.id)
    arg = (context.args[0].lower() if context.args else "daily")
    logger.info("/report %s user=%s", arg, uid)

    await update.effective_chat.send_action(ChatAction.TYPING)
    service = _report_service(context)

    if arg == "weekly":
        await _report_weekly(update, service, uid)
    elif arg == "daily":
        await _report_daily(update, service, uid)
    else:
        await update.message.reply_text(
            "Usage: <code>/report daily</code> or <code>/report weekly</code>",
            parse_mode=ParseMode.HTML,
        )


def register_report_handlers(application: Application) -> None:
    """Register the /report command (private chats only)."""
    application.add_handler(
        CommandHandler("report", report_command, filters=filters.ChatType.PRIVATE)
    )
