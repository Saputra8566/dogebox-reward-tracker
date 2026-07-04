"""Telegram command handler registration (all commands are DM-only)."""

from telegram.ext import Application

from bot.commands.common import register_common_handlers
from bot.commands.graphs import register_graph_handlers
from bot.commands.reports import register_report_handlers
from bot.commands.wallets import register_wallet_handlers


def register_all_handlers(application: Application) -> None:
    """Register every command handler on the application."""
    register_common_handlers(application)
    register_wallet_handlers(application)
    register_report_handlers(application)
    register_graph_handlers(application)


__all__ = ["register_all_handlers"]
