from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import get_settings

settings = get_settings()

DATE_FMT = "%Y-%m-%d"


def tz() -> ZoneInfo:
    return ZoneInfo(settings.app_tz)


def today_str() -> str:
    """Today in the user's local timezone -- never off by a day."""
    return datetime.now(tz()).strftime(DATE_FMT)


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def days_between(earlier: str, later: str) -> int:
    return (parse_date(later) - parse_date(earlier)).days


def date_range(start: str, end: str) -> list[str]:
    cur, stop = parse_date(start), parse_date(end)
    out = []
    while cur <= stop:
        out.append(cur.strftime(DATE_FMT))
        cur += timedelta(days=1)
    return out


def normalize(name: str) -> str:
    return " ".join(name.lower().strip().split())
