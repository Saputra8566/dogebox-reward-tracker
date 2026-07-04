"""Typed data models shared across the bot."""

from models.models import (
    DailyReport,
    EpochRewards,
    RewardRecord,
    Wallet,
    WalletReward,
    WeeklyReport,
)

__all__ = [
    "Wallet",
    "RewardRecord",
    "EpochRewards",
    "WalletReward",
    "DailyReport",
    "WeeklyReport",
]
