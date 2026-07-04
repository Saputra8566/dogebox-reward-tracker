"""Parse OpenForge epoch reward data into ``{address: amount}``.

Primary format (what OpenForge actually serves)
-----------------------------------------------
The dashboard SPA loads per-epoch files from the merkle host:

    https://merkle.openforge.one/<YYYY-MM-DD>.json

Each is a JSON array of ``{"address": "0x…", "cumulativeAmount": "<wei>"}``.
Amounts are **cumulative** running totals in wei (18 decimals). Per-epoch
(daily) rewards are computed elsewhere as diffs between consecutive epochs.

:func:`parse_merkle_leaves` handles that format. :func:`parse_epoch_payload`
is a generic JSON/HTML fallback so a future format change degrades gracefully.
If the field names ever change, adjust the ``*_KEYS`` sets below — that's the
single place to change.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable

from bs4 import BeautifulSoup

from utils.logging_config import get_logger
from utils.validators import is_valid_address, normalize_address

logger = get_logger(__name__)

# Keys (case-insensitive) that may hold a wallet address.
ADDRESS_KEYS = {
    "address",
    "wallet",
    "wallet_address",
    "walletaddress",
    "account",
    "addr",
    "holder",
    "owner",
    "miner",
    "recipient",
}

# Keys (case-insensitive) that may hold a *cumulative* on-chain amount.
CUMULATIVE_KEYS = {
    "cumulativeamount",
    "cumulative_amount",
    "cumulative",
    "amount",
    "total",
    "reward",
    "cys",
}

# Keys used by the generic (non-merkle) parser for direct reward values.
REWARD_KEYS = {
    "reward",
    "rewards",
    "cys",
    "cys_reward",
    "cysreward",
    "amount",
    "value",
    "earned",
    "points",
}

# Container keys that may wrap a list of leaves/records.
_CONTAINER_KEYS = ("leaves", "data", "rewards", "claims", "entries", "recipients")

_NUMERIC_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _to_float(value: Any) -> float | None:
    """Best-effort conversion of *value* to a float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = _NUMERIC_RE.search(value.replace(",", ""))
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
    return None


def _wei_to_amount(value: Any, decimals: int) -> float | None:
    """Convert a wei-denominated big-integer (string/int) to a token float."""
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value) / (10 ** decimals)
    if isinstance(value, int):
        return value / (10 ** decimals)
    return _to_float(value)


def parse_merkle_leaves(text: str, decimals: int = 18) -> Dict[str, float]:
    """Parse OpenForge merkle leaves into ``{address: cumulative_amount}``.

    Returns an empty dict when *text* is not the expected format, so the caller
    can fall back to :func:`parse_epoch_payload`.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}

    leaves: Any = payload
    if isinstance(payload, dict):
        for key in _CONTAINER_KEYS:
            if isinstance(payload.get(key), list):
                leaves = payload[key]
                break
    if not isinstance(leaves, list):
        return {}

    result: Dict[str, float] = {}
    for item in leaves:
        if not isinstance(item, dict):
            continue
        address: str | None = None
        amount: float | None = None
        for key, val in item.items():
            key_lc = str(key).lower()
            if address is None and key_lc in ADDRESS_KEYS and isinstance(val, str):
                if is_valid_address(val):
                    address = normalize_address(val)
            elif amount is None and key_lc in CUMULATIVE_KEYS:
                amount = _wei_to_amount(val, decimals)
        if address is not None and amount is not None:
            result[address] = amount
    return result


# --------------------------------------------------------------------------
# Generic fallback parser (JSON records / address-keyed JSON / HTML tables)
# --------------------------------------------------------------------------

def _record_to_reward(record: Dict[str, Any]) -> tuple[str, float] | None:
    address: str | None = None
    reward: float | None = None
    for key, val in record.items():
        key_lc = str(key).lower()
        if address is None and key_lc in ADDRESS_KEYS and isinstance(val, str):
            if is_valid_address(val):
                address = normalize_address(val)
        elif reward is None and key_lc in REWARD_KEYS:
            reward = _to_float(val)
    if address is not None and reward is not None:
        return address, reward
    return None


def _extract_rewards(payload: Any) -> Dict[str, float]:
    results: Dict[str, float] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            pair = _record_to_reward(node)
            if pair is not None:
                results.setdefault(pair[0], pair[1])
            for key, val in node.items():
                if isinstance(key, str) and is_valid_address(key):
                    reward = _to_float(val)
                    if reward is None and isinstance(val, dict):
                        for rk, rv in val.items():
                            if str(rk).lower() in REWARD_KEYS:
                                reward = _to_float(rv)
                                break
                    if reward is not None:
                        results.setdefault(normalize_address(key), reward)
                visit(val)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return results


def _parse_embedded_json(soup: BeautifulSoup) -> Dict[str, float]:
    rewards: Dict[str, float] = {}
    scripts: Iterable[Any] = soup.find_all("script")
    for script in scripts:
        raw = (script.string or script.get_text() or "").strip()
        if not raw or raw[0] not in "{[":
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for addr, reward in _extract_rewards(payload).items():
            rewards.setdefault(addr, reward)
    return rewards


def _parse_html_tables(soup: BeautifulSoup) -> Dict[str, float]:
    rewards: Dict[str, float] = {}
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        reward_col = next(
            (i for i, h in enumerate(headers) if h in REWARD_KEYS), None
        )
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            address = next((c for c in cells if is_valid_address(c)), None)
            if address is None:
                continue
            reward: float | None = None
            if reward_col is not None and reward_col < len(cells):
                reward = _to_float(cells[reward_col])
            if reward is None:
                for cell in reversed(cells):
                    if cell != address:
                        reward = _to_float(cell)
                        if reward is not None:
                            break
            if reward is not None:
                rewards.setdefault(normalize_address(address), reward)
    return rewards


def parse_epoch_payload(text: str, content_type: str = "") -> Dict[str, float]:
    """Generic fallback: parse a raw response body into ``{address: reward}``."""
    if not text:
        return {}
    content_type = (content_type or "").lower()

    if "json" in content_type or text.lstrip()[:1] in "{[":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            rewards = _extract_rewards(payload)
            if rewards:
                return rewards

    soup = BeautifulSoup(text, "html.parser")
    rewards = _parse_embedded_json(soup)
    if rewards:
        return rewards
    return _parse_html_tables(soup)
