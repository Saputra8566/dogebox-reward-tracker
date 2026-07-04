"""Telegram message formatting (HTML parse mode)."""

from __future__ import annotations

from html import escape
from typing import List

from models.models import DailyReport, Wallet, WeeklyReport
from utils.dates import format_epoch_date
from utils.validators import shorten_address

CYS = "CYS"


def _wallet_name(wallet: Wallet) -> str:
    """Display label for a wallet: its label, else a shortened address."""
    if wallet.label:
        return escape(wallet.label)
    return f"<code>{escape(shorten_address(wallet.address))}</code>"


def format_wallet_list(wallets: List[Wallet]) -> str:
    """Render the ``/list`` response."""
    if not wallets:
        return (
            "📭 You are not monitoring any wallets yet.\n"
            "Add one with <code>/add &lt;address&gt;</code>."
        )
    lines = ["👛 <b>You are monitoring:</b>", ""]
    for i, wallet in enumerate(wallets, start=1):
        label = f" — {escape(wallet.label)}" if wallet.label else ""
        lines.append(f"{i}. <code>{escape(wallet.address)}</code>{label}")
    return "\n".join(lines)


def format_daily_report(report: DailyReport) -> str:
    """Render the ``/report daily`` response."""
    lines = [
        "📊 <b>Daily Report</b>",
        "",
        f"<b>Epoch:</b> {format_epoch_date(report.epoch_date)}",
        "",
    ]
    for row in report.rows:
        lines.append(f"{_wallet_name(row.wallet)}")
        lines.append(f"  {row.reward:.2f} {CYS}")
    lines.append("")
    lines.append(f"<b>Total:</b> {report.total:.2f} {CYS}")
    return "\n".join(lines)


def format_weekly_report(report: WeeklyReport, span_label: str = "7") -> str:
    """Render the ``/report weekly`` response."""
    lines = [
        f"📈 <b>Weekly Report</b> (last {span_label} epochs)",
        "",
        "<b>Daily totals:</b>",
    ]
    for day, total in zip(report.epoch_dates, report.daily_totals):
        lines.append(f"  {format_epoch_date(day)} — {total:.2f} {CYS}")

    lines.append("")
    lines.append(f"<b>Total:</b>   {report.total:.2f} {CYS}")
    lines.append(f"<b>Average:</b> {report.average:.2f} {CYS}")

    highest = report.highest
    lowest = report.lowest
    if highest:
        lines.append(
            f"<b>Highest:</b> {highest[1]:.2f} {CYS} ({format_epoch_date(highest[0])})"
        )
    if lowest:
        lines.append(
            f"<b>Lowest:</b>  {lowest[1]:.2f} {CYS} ({format_epoch_date(lowest[0])})"
        )
    return "\n".join(lines)
