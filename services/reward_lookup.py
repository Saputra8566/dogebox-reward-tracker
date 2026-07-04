"""Fetch and cache epoch reward data from the OpenForge merkle distributor.

How OpenForge exposes rewards
-----------------------------
``dash.openforge.one/epoch/<date>`` is a client-rendered SPA with no data. It
loads per-epoch reward files from a separate host:

    https://merkle.openforge.one/<YYYY-MM-DD>.json

Each file is a JSON array of ``{"address", "cumulativeAmount"}`` where amounts
are **cumulative** 18-decimal wei. A wallet's reward for a given epoch is:

    reward(epoch) = cumulative(epoch) - cumulative(previous available epoch)

Responsibilities:
* Build the merkle URL dynamically from the current date (never hard-coded).
* Fall back to earlier dates when the latest epoch is not yet published.
* Cache cumulative amounts per epoch in SQLite to avoid re-downloading.
* Expose *daily* (per-epoch) rewards as differences between epochs.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Sequence

import httpx

from models.models import EpochRewards
from services.reward_parser import parse_epoch_payload, parse_merkle_leaves
from utils.config import Config
from utils.dates import format_epoch_date, iter_dates_backwards, today_in_timezone
from utils.logging_config import get_logger

logger = get_logger(__name__)

# A browser-like UA avoids Cloudflare edge-blocking on the merkle host.
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


class EpochLookupService:
    """Downloads, parses and caches OpenForge cumulative reward data.

    The SQLite ``reward_cache`` stores cumulative amounts; daily rewards are
    derived on demand as epoch-to-epoch diffs.
    """

    def __init__(self, config: Config, cache_repo) -> None:
        self._config = config
        self._cache = cache_repo

    def _candidate_urls(self, day: date) -> List[str]:
        """Return candidate reward URLs for an epoch date, best first."""
        key = format_epoch_date(day)
        return [
            f"{self._config.merkle_base_url}/{key}.json",
            # Defensive fallback for a possible future JSON API.
            f"{self._config.dashboard_base_url}/api/epoch/{key}",
        ]

    async def _fetch_cumulative_for_date(
        self, client: httpx.AsyncClient, day: date
    ) -> Dict[str, float] | None:
        """Return the full ``{address: cumulative}`` map for *day*, or ``None``."""
        for url in self._candidate_urls(day):
            try:
                response = await client.get(url)
            except httpx.TimeoutException:
                logger.warning("Timeout fetching %s", url)
                continue
            except httpx.HTTPError as exc:
                logger.warning("HTTP error fetching %s: %s", url, exc)
                continue

            if response.status_code != 200:
                logger.debug("Non-200 (%s) for %s", response.status_code, url)
                continue

            rewards = parse_merkle_leaves(response.text, self._config.token_decimals)
            if not rewards:
                rewards = parse_epoch_payload(
                    response.text, response.headers.get("content-type", "")
                )
            if rewards:
                logger.info(
                    "Fetched epoch %s from %s (%d addresses)",
                    format_epoch_date(day),
                    url,
                    len(rewards),
                )
                return rewards
        return None

    async def _cumulative_snapshot(
        self, client: httpx.AsyncClient, day: date, addresses: Sequence[str]
    ) -> EpochRewards | None:
        """Return monitored-wallet *cumulative* amounts for *day* (cache-aware)."""
        cached = self._cache.get_epoch(day)
        if cached and all(addr in cached for addr in addresses):
            return EpochRewards(
                epoch_date=day,
                rewards={addr: cached.get(addr, 0.0) for addr in addresses},
            )

        full = await self._fetch_cumulative_for_date(client, day)
        if full is None:
            return None

        monitored = {addr: full.get(addr, 0.0) for addr in addresses}
        if monitored:
            self._cache.upsert_many(day, monitored)
        return EpochRewards(epoch_date=day, rewards=monitored)

    async def _collect_cumulative(
        self, addresses: Sequence[str], count: int
    ) -> List[EpochRewards]:
        """Return up to *count* most-recent cumulative snapshots (newest first)."""
        start = today_in_timezone(self._config.timezone)
        max_days = count + self._config.epoch_lookback_days
        collected: List[EpochRewards] = []

        timeout = httpx.Timeout(self._config.request_timeout)
        async with httpx.AsyncClient(
            timeout=timeout, headers=_DEFAULT_HEADERS, follow_redirects=True
        ) as client:
            for day in iter_dates_backwards(start, max_days):
                if len(collected) >= count:
                    break
                snapshot = await self._cumulative_snapshot(client, day, addresses)
                if snapshot is not None:
                    collected.append(snapshot)

        if not collected:
            logger.warning(
                "No epoch found within %d days of %s",
                max_days,
                format_epoch_date(start),
            )
        return collected

    def _to_daily(
        self,
        snapshots: Sequence[EpochRewards],
        addresses: Sequence[str],
        count: int,
    ) -> List[EpochRewards]:
        """Convert newest-first cumulative snapshots into daily rewards.

        ``reward(epoch_i) = cumulative(epoch_i) - cumulative(epoch_i+1)``. The
        oldest snapshot has no predecessor, so its reward is its cumulative
        amount. Negative diffs are clamped to 0.
        """
        results: List[EpochRewards] = []
        for i in range(min(count, len(snapshots))):
            current = snapshots[i]
            previous = snapshots[i + 1] if i + 1 < len(snapshots) else None
            daily = {
                addr: max(
                    0.0,
                    current.reward_for(addr)
                    - (previous.reward_for(addr) if previous else 0.0),
                )
                for addr in addresses
            }
            results.append(EpochRewards(epoch_date=current.epoch_date, rewards=daily))
        return results

    # -- Public API ---------------------------------------------------------

    async def collect_recent_epochs(
        self, addresses: Sequence[str], count: int
    ) -> List[EpochRewards]:
        """Return up to *count* recent epochs' *daily* rewards (newest first)."""
        if count <= 0 or not addresses:
            return []
        # Fetch one extra epoch so the oldest requested epoch has a predecessor.
        snapshots = await self._collect_cumulative(addresses, count + 1)
        return self._to_daily(snapshots, addresses, count)

    async def get_latest_epoch(
        self, addresses: Sequence[str]
    ) -> EpochRewards | None:
        """Return the newest available epoch's daily reward per wallet."""
        daily = await self.collect_recent_epochs(addresses, 1)
        return daily[0] if daily else None

    async def sync_latest(self, addresses: Sequence[str]) -> EpochRewards | None:
        """Fetch and cache the latest epoch (used by the scheduler)."""
        epoch = await self.get_latest_epoch(addresses)
        if epoch is not None:
            logger.info(
                "Synced epoch %s: total %.4f CYS across %d wallets",
                format_epoch_date(epoch.epoch_date),
                epoch.total,
                len(epoch.rewards),
            )
        return epoch
