"""Sync Humanity workflow JSON into the Supabase `shifts` table.

Run from the repo root:
    ~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from .env (repo root). The
matc-humanity skill must already have a valid bearer token saved on this
machine (`humanity_agent.py --set-token "..."`).
"""
from __future__ import annotations

from datetime import time


def parse_time(humanity_time: str) -> time:
    """Convert Humanity's "08:00AM" / "01:00PM" / "12:00PM" into a `time`.

    Humanity emits 12-hour clock strings with no separator before AM/PM.
    """
    hh, rest = humanity_time[:2], humanity_time[2:]
    mm = rest[1:3]  # rest is ":MMxM" -> skip the leading ":"
    suffix = rest[3:].upper()
    hour = int(hh)
    minute = int(mm)
    if suffix == "AM":
        if hour == 12:
            hour = 0
    elif suffix == "PM":
        if hour != 12:
            hour += 12
    else:
        raise ValueError(f"Unrecognized AM/PM suffix in {humanity_time!r}")
    return time(hour, minute)


def last_name(humanity_name: str) -> str:
    """Humanity returns instructor names as "Last, First". Return the "Last".

    If the format is unexpected (no comma), return the original string so
    downstream comparisons remain deterministic.
    """
    if "," not in humanity_name:
        return humanity_name
    return humanity_name.split(",", 1)[0].strip()


def derive_am_pm(t: time) -> str:
    """Return 'am' for times strictly before noon, 'pm' for noon and after."""
    return "am" if t.hour < 12 else "pm"


def derive_role(instructor_name: str, cohort_lead_last_name: str | None) -> str:
    """Return 'Lead' iff the instructor's last name matches the cohort lead.

    Everything else (including unknown name formats and a missing cohort lead)
    falls through to 'Assist'.
    """
    if not cohort_lead_last_name:
        return "Assist"
    return "Lead" if last_name(instructor_name) == cohort_lead_last_name else "Assist"
