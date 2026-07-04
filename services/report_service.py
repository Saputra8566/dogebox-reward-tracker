"""Build per-user daily and weekly reports from wallets + epoch data."""

from __future__ import annotations

import asyncio
from typing import List

from database.repositories import RewardCacheRepository, WalletRepository
from models.models import DailyReport, EpochRewards, WalletReward, WeeklyReport
from services.reward_lookup import EpochLookupService
from utils.logging_config import get_logger

logger = get_logger(__name__)


class ReportService:
    """Coordinates per-user wallet data + epoch lookups into report models."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        cache_repo: RewardCacheRepository,
        lookup: EpochLookupService,
    ) -> None:
        self._wallets = wallet_repo
        self._cache = cache_repo
        self._lookup = lookup

    async def addresses(self, user_id: str) -> List[str]:
        """Return a user's monitored addresses (DB access off the event loop)."""
        wallets = await asyncio.to_thread(self._wallets.list_all, user_id)
        return [w.address for w in wallets]

    async def daily_report(self, user_id: str) -> DailyReport | None:
        """Build the latest-epoch report for one user's wallets."""
        wallets = await asyncio.to_thread(self._wallets.list_all, user_id)
        if not wallets:
            return None

        addresses = [w.address for w in wallets]
        epoch = await self._lookup.get_latest_epoch(addresses)
        if epoch is None:
            return None

        rows = [
            WalletReward(wallet=wallet, reward=epoch.reward_for(wallet.address))
            for wallet in wallets
        ]
        return DailyReport(epoch_date=epoch.epoch_date, rows=rows)

    async def collect_epochs(self, user_id: str, count: int) -> List[EpochRewards]:
        """Return up to *count* recent epochs for one user's wallets."""
        addresses = await self.addresses(user_id)
        if not addresses:
            return []
        return await self._lookup.collect_recent_epochs(addresses, count)

    async def weekly_report(
        self, user_id: str, epochs_count: int = 7
    ) -> WeeklyReport | None:
        """Aggregate the latest *epochs_count* epochs into a weekly summary."""
        epochs = await self.collect_epochs(user_id, epochs_count)
        if not epochs:
            return None

        epochs_sorted = sorted(epochs, key=lambda e: e.epoch_date)
        return WeeklyReport(
            epoch_dates=[e.epoch_date for e in epochs_sorted],
            daily_totals=[e.total for e in epochs_sorted],
        )
