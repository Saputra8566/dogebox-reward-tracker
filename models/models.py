"""Dataclasses describing wallets, epoch rewards and reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List


@dataclass(frozen=True)
class Wallet:
    """A monitored wallet address (belongs to one user)."""

    address: str
    label: str | None = None
    id: int | None = None
    user_id: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class RewardRecord:
    """A single cached cumulative-reward row for one wallet in one epoch."""

    epoch_date: date
    wallet: str
    reward: float
    created_at: str | None = None


@dataclass(frozen=True)
class EpochRewards:
    """Per-wallet rewards for a single epoch date.

    ``rewards`` maps a normalized wallet address to its CYS reward.
    """

    epoch_date: date
    rewards: Dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        """Sum of rewards across all wallets in this epoch."""
        return sum(self.rewards.values())

    def reward_for(self, address: str) -> float:
        """Return the reward for *address* (0.0 if absent)."""
        return self.rewards.get(address, 0.0)


@dataclass(frozen=True)
class WalletReward:
    """A wallet paired with its reward for a report row."""

    wallet: Wallet
    reward: float


@dataclass(frozen=True)
class DailyReport:
    """Result of ``/report daily``."""

    epoch_date: date
    rows: List[WalletReward]

    @property
    def total(self) -> float:
        return sum(row.reward for row in self.rows)


@dataclass(frozen=True)
class WeeklyReport:
    """Result of ``/report weekly`` (aggregated across N epochs)."""

    epoch_dates: List[date]
    daily_totals: List[float]

    @property
    def total(self) -> float:
        return sum(self.daily_totals)

    @property
    def average(self) -> float:
        return self.total / len(self.daily_totals) if self.daily_totals else 0.0

    @property
    def highest(self) -> tuple[date, float] | None:
        if not self.daily_totals:
            return None
        idx = max(range(len(self.daily_totals)), key=self.daily_totals.__getitem__)
        return self.epoch_dates[idx], self.daily_totals[idx]

    @property
    def lowest(self) -> tuple[date, float] | None:
        if not self.daily_totals:
            return None
        idx = min(range(len(self.daily_totals)), key=self.daily_totals.__getitem__)
        return self.epoch_dates[idx], self.daily_totals[idx]
