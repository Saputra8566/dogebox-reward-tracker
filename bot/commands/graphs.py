"""Graph commands: /graph weekly | weekly2 | weekly3 | monthly (per-user, DM-only)."""

from __future__ import annotations

from telegram import InputFile, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from charts.chart_generator import generate_reward_chart
from services.report_service import ReportService
from utils.logging_config import get_logger

logger = get_logger(__name__)

# span keyword -> (number of epochs, human title)
_SPANS: dict[str, tuple[int, str]] = {
    "weekly": (7, "CYS Rewards — Last 7 Epochs"),
    "weekly2": (14, "CYS Rewards — Last 14 Epochs"),
    "weekly3": (21, "CYS Rewards — Last 21 Epochs"),
    "monthly": (28, "CYS Rewards — Last 28 Epochs"),
}


def _report_service(context: ContextTypes.DEFAULT_TYPE) -> ReportService:
    return context.application.bot_data["report_service"]


async def graph_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/graph <span>`` and render a black & white chart."""
    uid = str(update.effective_user.id)
    span = (context.args[0].lower() if context.args else "weekly")
    logger.info("/graph %s user=%s", span, uid)

    if span not in _SPANS:
        await update.message.reply_text(
            "Usage: <code>/graph weekly | weekly2 | weekly3 | monthly</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    count, title = _SPANS[span]
    service = _report_service(context)

    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
    report = await service.weekly_report(uid, count)

    if report is None:
        if not await service.addresses(uid):
            await update.message.reply_text(
                "📭 You are not monitoring any wallets yet. Add one with /add first."
            )
        else:
            await update.message.reply_text(
                "🔍 No epoch data was found to plot. Try again later."
            )
        return

    png = generate_reward_chart(title, report.epoch_dates, report.daily_totals)
    caption = (
        f"{title}\n"
        f"Total: {report.total:.2f} CYS · Avg: {report.average:.2f} CYS"
    )
    # Wrap in InputFile with an explicit .png filename so Telegram recognizes it
    # as an image (raw bytes upload as application/octet-stream and are rejected).
    photo = InputFile(png, filename=f"cys_{span}.png")
    await update.message.reply_photo(photo=photo, caption=caption)


def register_graph_handlers(application: Application) -> None:
    """Register the /graph command (private chats only)."""
    application.add_handler(
        CommandHandler("graph", graph_command, filters=filters.ChatType.PRIVATE)
    )
