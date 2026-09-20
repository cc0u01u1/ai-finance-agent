"""Period resolution helpers.

Converts a period expression (Chinese or English) into a half-open time range
[start, end) plus a stable label, e.g. '2026-09'.
"""
import re
from calendar import monthrange
from datetime import datetime, timedelta
from typing import Tuple, Optional


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, 0, 0, 0)


def _next_month_start(d: datetime) -> datetime:
    if d.month == 12:
        return datetime(d.year + 1, 1, 1)
    return datetime(d.year, d.month + 1, 1)


def resolve_period(
    expression: Optional[str] = None,
    now: Optional[datetime] = None
) -> Tuple[datetime, datetime, str]:
    """Resolve a period expression to (start, end_exclusive, label).

    Supported expressions:
    - this_month / 本月 / 当月
    - last_month / 上月
    - this_week / 本周
    - last_week / 上周
    - last_30d / 近30天
    - explicit 'YYYY-MM' (e.g. '2026-09')
    - all / 全部 (from year 2000 to far future)

    Defaults to the current month.
    """
    ref = now or datetime.now()
    text = (expression or "this_month").strip().lower()

    # Explicit 'YYYY-MM'
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid month in period expression: {expression}")
        start = _month_start(year, month)
        end = _next_month_start(start)
        return start, end, f"{year:04d}-{month:02d}"

    if text in ("last_month", "上月", "上个月"):
        this_month = _month_start(ref.year, ref.month)
        start = this_month - timedelta(days=1)
        start = _month_start(start.year, start.month)
        end = this_month
        return start, end, f"{start.year:04d}-{start.month:02d}"

    if text in ("this_week", "本周", "这周"):
        today = ref.replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
        return start, end, f"{start:%Y-%m-%d}周"

    if text in ("last_week", "上周", "上一周"):
        today = ref.replace(hour=0, minute=0, second=0, microsecond=0)
        this_week_start = today - timedelta(days=today.weekday())
        start = this_week_start - timedelta(days=7)
        end = this_week_start
        return start, end, f"{start:%Y-%m-%d}周"

    if text in ("last_30d", "近30天", "最近30天", "recent_30d"):
        end = ref.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = end - timedelta(days=30)
        return start, end, "近30天"

    if text in ("all", "全部", "全部时间", "everything"):
        start = datetime(2000, 1, 1)
        end = datetime(3000, 1, 1)
        return start, end, "全部"

    if text not in ("this_month", "本月", "当月", "这个月", "current_month", ""):
        raise ValueError(f"Unknown period expression: {expression}")

    start = _month_start(ref.year, ref.month)
    end = _next_month_start(start)
    return start, end, f"{start.year:04d}-{start.month:02d}"


def previous_period(
    start: datetime, end: datetime, label: str
) -> Tuple[datetime, datetime, str]:
    """Return the period immediately before the given one (same length)."""
    if re.fullmatch(r"\d{4}-\d{2}", label):
        # Calendar-month arithmetic to avoid variable month-length issues
        year, month = start.year, start.month
        if month == 1:
            prev_start = datetime(year - 1, 12, 1)
        else:
            prev_start = datetime(year, month - 1, 1)
        return prev_start, start, month_label(prev_start)

    length = end - start
    prev_end = start
    prev_start = start - length
    return prev_start, prev_end, f"上一周期({label})"


def days_in_period(start: datetime, end: datetime) -> int:
    """Number of calendar days covered by the range (minimum 1)."""
    return max((end.date() - start.date()).days, 1)


def month_label(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def days_remaining_in_month(now: Optional[datetime] = None) -> int:
    ref = now or datetime.now()
    total_days = monthrange(ref.year, ref.month)[1]
    return max(total_days - ref.day + 1, 1)
