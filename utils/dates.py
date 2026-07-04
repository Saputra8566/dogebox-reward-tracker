"""Date helpers for epoch handling.

Epoch files are keyed by calendar date (``YYYY-MM-DD``) in the configured
timezone. These helpers keep timezone-aware "today" logic and epoch-date
iteration in one place so the rest of the code never hard-codes a date.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterator

import pytz

EPOCH_DATE_FMT = "%Y-%m-%d"


def today_in_timezone(timezone: str) -> date:
    """Return today's calendar date in *timezone* (never hard-coded)."""
    tz = pytz.timezone(timezone)
    return datetime.now(tz).date()


def format_epoch_date(day: date) -> str:
    """Format a :class:`date` as the ``YYYY-MM-DD`` epoch key."""
    return day.strftime(EPOCH_DATE_FMT)


def parse_epoch_date(value: str) -> date:
    """Parse a ``YYYY-MM-DD`` epoch key back into a :class:`date`."""
    return datetime.strptime(value, EPOCH_DATE_FMT).date()


def iter_dates_backwards(start: date, max_days: int) -> Iterator[date]:
    """Yield *start*, then each preceding day, for up to *max_days* days."""
    for offset in range(max_days):
        yield date.fromordinal(start.toordinal() - offset)
