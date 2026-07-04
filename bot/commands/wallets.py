"""Wallet management commands: /add, /remove, /list (per-user, DM-only)."""

from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from bot.formatting import format_wallet_list
from database.db import DatabaseError
from database.repositories import WalletRepository
from utils.config import Config
from utils.logging_config import get_logger
from utils.validators import is_valid_address, normalize_address

logger = get_logger(__name__)


def _wallet_repo(context: ContextTypes.DEFAULT_TYPE) -> WalletRepository:
    return context.application.bot_data["wallet_repo"]


def _config(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.application.bot_data["config"]


def _uid(update: Update) -> str:
    return str(update.effective_user.id)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/add <address>``."""
    uid = _uid(update)
    logger.info("/add user=%s args=%s", uid, context.args)
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/add &lt;address&gt;</code>", parse_mode=ParseMode.HTML
        )
        return

    raw = context.args[0]
    label = " ".join(context.args[1:]) or None

    if not is_valid_address(raw):
        await update.message.reply_text(
            "❌ That does not look like a valid wallet address.\n"
            "Supported: EVM (<code>0x…</code>) or bech32 (<code>cysic1…</code>).",
            parse_mode=ParseMode.HTML,
        )
        return

    address = normalize_address(raw)
    repo = _wallet_repo(context)
    cap = _config(context).max_wallets_per_user

    if await asyncio.to_thread(repo.count, uid) >= cap:
        await update.message.reply_text(
            f"⚠️ You've reached the limit of {cap} wallets. "
            "Remove one with /remove first."
        )
        return

    try:
        await asyncio.to_thread(repo.add, uid, address, label)
    except ValueError:
        await update.message.reply_text("ℹ️ You're already monitoring that address.")
        return
    except DatabaseError:
        logger.exception("DB error adding wallet")
        await update.message.reply_text("⚠️ Database error. Could not add the address.")
        return

    await update.message.reply_text("✅ Address successfully added.")


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/remove <address>``."""
    uid = _uid(update)
    logger.info("/remove user=%s args=%s", uid, context.args)
    if not context.args:
        await update.message.reply_text(
            "Usage: <code>/remove &lt;address&gt;</code>", parse_mode=ParseMode.HTML
        )
        return

    address = normalize_address(context.args[0])
    repo = _wallet_repo(context)
    try:
        removed = await asyncio.to_thread(repo.remove, uid, address)
    except DatabaseError:
        logger.exception("DB error removing wallet")
        await update.message.reply_text("⚠️ Database error. Could not remove the address.")
        return

    if removed:
        await update.message.reply_text("🗑️ Address removed.")
    else:
        await update.message.reply_text("ℹ️ That address was not being monitored.")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ``/list``."""
    uid = _uid(update)
    logger.info("/list user=%s", uid)
    repo = _wallet_repo(context)
    try:
        wallets = await asyncio.to_thread(repo.list_all, uid)
    except DatabaseError:
        logger.exception("DB error listing wallets")
        await update.message.reply_text("⚠️ Database error. Could not list addresses.")
        return

    await update.message.reply_text(
        format_wallet_list(wallets), parse_mode=ParseMode.HTML
    )


def register_wallet_handlers(application: Application) -> None:
    """Register /add, /remove and /list (private chats only)."""
    dm = filters.ChatType.PRIVATE
    application.add_handler(CommandHandler("add", add_command, filters=dm))
    application.add_handler(CommandHandler("remove", remove_command, filters=dm))
    application.add_handler(CommandHandler("list", list_command, filters=dm))
