"""Pull per-shift lab activities from the "Lesson Plan Material" Google Sheet.

Each cohort has a tab (`Cohort 1` … `Cohort 4`) listing dated activity rows.
`build_activities()` turns the rows for one shift into the `{perInstructor,
shared}` blob stored in `shifts.activities` and rendered by the instructor hub.

Pure helpers are unit-tested in tests/test_sheet_activities.py. `gws_get_values`
and `resolve_doc_title` are the thin `gws`-CLI I/O shell — the same split as
scripts/sync_to_supabase.py. This deliberately re-implements logic that overlaps
the matc-lesson-plan skill's pull_activity_data.py so the site pipeline is
self-contained and testable on its own.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, time

SPREADSHEET_ID = "1aSnWNVMK6ib84AVnvmf9TTlkJCe0i7WxgdKxlD_bmh8"
SLUG_BASE_URL = "https://matc-ems.github.io/scenarios/main-lab/"

# New 14-column tab layout (columns A–N). Indices of the columns we read.
COL_DATE = 0
COL_START = 3
COL_TITLE = 8
COL_SCENARIO_SLUGS = 10
COL_SCENARIO_LINKS = 11
COL_PP_SKILL_LINKS = 12
COL_ACTIVITY_LINKS = 13

# Header row of the new layout — used to reject the old `Cohort 1` format.
EXPECTED_HEADER = [
    "date", "day_of_week", "shift", "start_time", "end_time", "duration_min",
    "activity_type", "activity_id", "activity_title", "activity_description",
    "scenario_slugs", "scenario_links", "pp_skill_links", "activity_links",
]


def cell(row, idx):
    """Return row[idx] stripped, or '' when the row is shorter than idx+1."""
    return row[idx].strip() if idx < len(row) else ""


def parse_sheet_date(value):
    """Parse a sheet date 'MM-DD-YY' into a date. Lenient on leading zeros.

    Raises ValueError on anything that is not three integer parts.
    """
    parts = value.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"bad sheet date: {value!r}")
    month, day, year = (int(p) for p in parts)
    if year < 100:
        year += 2000
    return date(year, month, day)


def parse_clock(value):
    """Parse a 24-hour 'H:MM' clock string into a time.

    Raises ValueError if the string is not H:MM.
    """
    return datetime.strptime(value.strip(), "%H:%M").time()


def derive_am_pm(t):
    """'am' for times strictly before noon, 'pm' for noon and after."""
    return "am" if t.hour < 12 else "pm"


def split_cell(value):
    """Split a comma-separated cell into trimmed parts, dropping empties."""
    return [part.strip() for part in value.split(",") if part.strip()]


def is_new_format(header_row):
    """True when a tab's header row matches the 14-column activity layout.

    The old `Cohort 1` tab (`Class Date, Start Time, …`) returns False so the
    caller can skip it gracefully.
    """
    cleaned = [c.strip().lower() for c in header_row[: len(EXPECTED_HEADER)]]
    return cleaned == EXPECTED_HEADER


_DOC_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]+)|[?&]id=([A-Za-z0-9_-]+)")


def resolve_doc_title(url):
    """Best-effort: return a Google Doc/Drive file's title for a URL.

    Falls back to the URL itself for a non-Drive link or any `gws` failure —
    this is cosmetic enrichment and must never break the pull.
    """
    match = _DOC_ID_RE.search(url)
    if not match:
        return url
    file_id = match.group(1) or match.group(2)
    try:
        result = subprocess.run(
            ["gws", "drive", "files", "get", "--params",
             json.dumps({"fileId": file_id, "fields": "name",
                         "supportsAllDrives": True}),
             "--format", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return url
        brace = result.stdout.find("{")
        if brace == -1:
            return url
        return json.loads(result.stdout[brace:]).get("name") or url
    except Exception:
        return url


def empty_activities():
    """The `activities` blob for a shift with no sheet data."""
    return {"perInstructor": {}, "shared": []}


def round_robin(pool, n_instructors):
    """Distribute `pool` across `n_instructors`, round-robin, evenly.

    Returns a list of `n_instructors` lists. Each instructor gets exactly
    `per = len(pool) // n_instructors` items: item k goes to instructor
    k % n_instructors, so instructor i receives items i, i+n, i+2n, ….
    The trailing `len(pool) - per*n_instructors` items are dropped so every
    instructor's list has the same length. Returns [] when n_instructors <= 0.
    """
    if n_instructors <= 0:
        return []
    per = len(pool) // n_instructors
    used = pool[: per * n_instructors]
    buckets = [[] for _ in range(n_instructors)]
    for k, item in enumerate(used):
        buckets[k % n_instructors].append(item)
    return buckets
