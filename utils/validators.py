"""Wallet address validation and normalization.

OpenForge / Cysic uses EVM-style ``0x`` addresses as well as bech32
(``cysic1...``) addresses. Both are accepted. Keeping validation in one place
means commands and services agree on what a "valid address" means.
"""

from __future__ import annotations

import re

# 0x-prefixed 20-byte hex address (Ethereum / EVM style).
_EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

# Generic bech32-style address, e.g. ``cysic1...`` / ``cosmos1...``.
_BECH32_RE = re.compile(r"^[a-z]{2,10}1[02-9ac-hj-np-z]{20,90}$")


def is_valid_address(address: str) -> bool:
    """Return ``True`` if *address* looks like a supported wallet address."""
    if not address:
        return False
    candidate = address.strip()
    return bool(_EVM_RE.match(candidate) or _BECH32_RE.match(candidate.lower()))


def normalize_address(address: str) -> str:
    """Normalize an address for storage and comparison (lower-cased)."""
    return address.strip().lower()


def shorten_address(address: str, head: int = 6, tail: int = 4) -> str:
    """Return a display-friendly ``0x1234…abcd`` form of *address*."""
    if len(address) <= head + tail + 1:
        return address
    return f"{address[:head]}…{address[-tail:]}"
