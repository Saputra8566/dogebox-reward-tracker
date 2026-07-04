"""Common handlers: /start, /help, non-DM notice and the global error handler."""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from utils.logging_config import get_logger

logger = get_logger(__name__)

_HELP_TEXT = (
    "🐕 <b>DogeBox Reward Tracker</b>\n"
    "Track your Cysic (CYS) rewards on the OpenForge network.\n\n"
    "<b>Wallets</b>\n"
    "<code>/add &lt;address&gt;</code> — monitor a wallet\n"
    "<code>/remove &lt;address&gt;</code> — stop monitoring a wallet\n"
    "<code>/list</code> — show your monitored wallets\n\n"
    "<b>Reports</b>\n"
    "<code>/report daily</code> — today's epoch rewards\n"
    "<code>/report weekly</code> — last 7 epochs summary\n\n"
    "<b>Graphs</b> (black &amp; white PNG)\n"
    "<code>/graph weekly</code> — last 7 epochs\n"
    "<code>/graph weekly2</code> — last 14 epochs\n"
    "<code>/graph weekly3</code> — last 21 epochs\n"
    "<code>/graph monthly</code> — last 28 epochs\n\n"
    "Your wallet list is private to you. 🔒"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    logger.info("/start from user %s", update.effective_user.id)
    await update.message.reply_text(_HELP_TEXT, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help."""
    logger.info("/help from user %s", update.effective_user.id)
    await update.message.reply_text(_HELP_TEXT, parse_mode=ParseMode.HTML)


async def non_private_notice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Tell users in groups to DM the bot instead (it is DM-only)."""
    if update.effective_message:
        await update.effective_message.reply_text(
            "👋 Please talk to me in a private chat — open @"
            f"{context.bot.username} and press Start."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler: log the exception and inform the user."""
    logger.exception(
        "Unhandled exception while processing update", exc_info=context.error
    )
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Something went wrong while handling that. "
                "Please try again in a moment."
            )
        except TelegramError:
            logger.error("Failed to notify user of error")


def register_common_handlers(application: Application) -> None:
    """Register /start, /help, the group notice and the error handler."""
    private = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("start", start_command, filters=private))
    application.add_handler(CommandHandler("help", help_command, filters=private))
    # Any command sent in a group/supergroup gets a gentle DM nudge.
    application.add_handler(
        MessageHandler(
            filters.COMMAND & (filters.ChatType.GROUPS), non_private_notice
        )
    )
    application.add_error_handler(error_handler)


__all__ = ["register_common_handlers", "error_handler"]
