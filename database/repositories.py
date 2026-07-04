"""Data-access repositories for wallets (per-user) and the reward cache.

Repositories expose synchronous methods. Telegram command handlers call them
through :func:`asyncio.to_thread` so the event loop stays responsive.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Dict, List

from database.db import Database, DatabaseError
from models.models import RewardRecord, Wallet
from utils.dates import format_epoch_date, parse_epoch_date
from utils.logging_config import get_logger

logger = get_logger(__name__)


class WalletRepository:
    """Per-user CRUD operations for monitored wallet addresses."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, user_id: str, address: str, label: str | None = None) -> Wallet:
        """Insert a wallet for *user_id*, raising ValueError on duplicates."""
        try:
            with self._db.cursor() as cur:
                cur.execute(
                    "INSERT INTO wallets (user_id, address, label) VALUES (?, ?, ?)",
                    (user_id, address, label),
                )
                new_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Address already monitored: {address}") from exc
        except sqlite3.Error as exc:
            raise DatabaseError(str(exc)) from exc
        logger.info("User %s added wallet %s (id=%s)", user_id, address, new_id)
        return Wallet(id=new_id, address=address, label=label, user_id=user_id)

    def remove(self, user_id: str, address: str) -> bool:
        """Delete a user's wallet. Returns ``True`` if a row was removed."""
        with self._db.cursor() as cur:
            cur.execute(
                "DELETE FROM wallets WHERE user_id = ? AND address = ?",
                (user_id, address),
            )
            removed = cur.rowcount > 0
        if removed:
            logger.info("User %s removed wallet %s", user_id, address)
        return removed

    def exists(self, user_id: str, address: str) -> bool:
        """Return ``True`` if *user_id* already monitors *address*."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM wallets WHERE user_id = ? AND address = ?",
                (user_id, address),
            )
            return cur.fetchone() is not None

    def count(self, user_id: str) -> int:
        """Number of wallets a user monitors (used for the per-user cap)."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM wallets WHERE user_id = ?", (user_id,)
            )
            return int(cur.fetchone()["n"])

    def list_all(self, user_id: str) -> List[Wallet]:
        """Return a user's wallets ordered by insertion time."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, address, label, created_at FROM wallets "
                "WHERE user_id = ? ORDER BY id",
                (user_id,),
            )
            rows = cur.fetchall()
        return [
            Wallet(
                id=row["id"],
                user_id=row["user_id"],
                address=row["address"],
                label=row["label"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_addresses(self, user_id: str) -> List[str]:
        """Return just the addresses a user monitors."""
        return [w.address for w in self.list_all(user_id)]

    # --- Global helpers used by the scheduler ---

    def all_distinct_addresses(self) -> List[str]:
        """Every unique address across all users (to warm the shared cache)."""
        with self._db.cursor() as cur:
            cur.execute("SELECT DISTINCT address FROM wallets")
            return [row["address"] for row in cur.fetchall()]

    def all_user_ids(self) -> List[str]:
        """Every user id that monitors at least one wallet."""
        with self._db.cursor() as cur:
            cur.execute("SELECT DISTINCT user_id FROM wallets")
            return [row["user_id"] for row in cur.fetchall()]


class RewardCacheRepository:
    """Shared cache of per-wallet *cumulative* rewards keyed by epoch date."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(self, epoch_date: date, wallet: str, reward: float) -> None:
        """Insert or update the cached cumulative amount for a wallet/epoch."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reward_cache (epoch_date, wallet, reward)
                VALUES (?, ?, ?)
                ON CONFLICT(epoch_date, wallet)
                DO UPDATE SET reward = excluded.reward,
                              created_at = datetime('now')
                """,
                (format_epoch_date(epoch_date), wallet, float(reward)),
            )

    def upsert_many(self, epoch_date: date, rewards: Dict[str, float]) -> None:
        """Bulk upsert of ``{wallet: cumulative}`` for a single epoch."""
        epoch_key = format_epoch_date(epoch_date)
        with self._db.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO reward_cache (epoch_date, wallet, reward)
                VALUES (?, ?, ?)
                ON CONFLICT(epoch_date, wallet)
                DO UPDATE SET reward = excluded.reward,
                              created_at = datetime('now')
                """,
                [
                    (epoch_key, wallet, float(reward))
                    for wallet, reward in rewards.items()
                ],
            )

    def get_epoch(self, epoch_date: date) -> Dict[str, float]:
        """Return the cached ``{wallet: cumulative}`` map for *epoch_date*."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT wallet, reward FROM reward_cache WHERE epoch_date = ?",
                (format_epoch_date(epoch_date),),
            )
            rows = cur.fetchall()
        return {row["wallet"]: row["reward"] for row in rows}

    def epoch_cached(self, epoch_date: date) -> bool:
        """Return ``True`` if any rows are cached for *epoch_date*."""
        with self._db.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM reward_cache WHERE epoch_date = ? LIMIT 1",
                (format_epoch_date(epoch_date),),
            )
            return cur.fetchone() is not None

    def history_for_wallet(self, wallet: str, limit: int = 60) -> List[RewardRecord]:
        """Return recent cached rewards for a single wallet, newest first."""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT epoch_date, wallet, reward, created_at
                FROM reward_cache
                WHERE wallet = ?
                ORDER BY epoch_date DESC
                LIMIT ?
                """,
                (wallet, limit),
            )
            rows = cur.fetchall()
        return [
            RewardRecord(
                epoch_date=parse_epoch_date(row["epoch_date"]),
                wallet=row["wallet"],
                reward=row["reward"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
