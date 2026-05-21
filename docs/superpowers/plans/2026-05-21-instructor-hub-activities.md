# Instructor Hub Activities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show each shift's lab activities on the instructor hub — shared material groups and per-instructor round-robin scenario assignments — pulled from the "Lesson Plan Material" Google Sheet into a new `shifts.activities` column.

**Architecture:** A new `scripts/sheet_activities.py` reads each cohort's sheet tab via the `gws` CLI. `sync_to_supabase.py` joins that data onto the Humanity shifts it already pulls and writes a fully-resolved `{perInstructor, shared}` blob into a new `shifts.activities` JSONB column. The instructor hub renders the blob directly — no client-side computation.

**Tech Stack:** Python 3.12 (stdlib; `requests` / `python-dotenv` on the matc-humanity venv), `gws` CLI, Supabase PostgREST, React 18 via in-browser Babel, `unittest`.

**Conventions:**
- `$PY` in commands = `~/.claude/skills/matc-humanity/.venv/bin/python` (per CLAUDE.md). Run all commands from the repo root.
- Commit messages: short imperative, no prefix (repo style); end each with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer (omitted from the `-m` blocks below for brevity).
- The spec this implements: `docs/superpowers/specs/2026-05-21-instructor-hub-activities-design.md`.

## File Structure

| File | Created/Modified | Responsibility |
|------|------------------|----------------|
| `sql/002_activities_column.sql` | Create | Adds the `activities` JSONB column to `shifts`. |
| `scripts/sheet_activities.py` | Create | Reads a cohort sheet tab; builds the `{perInstructor, shared}` blob for one shift. |
| `tests/test_sheet_activities.py` | Create | Unit tests for the pure helpers in `sheet_activities.py`. |
| `scripts/sync_to_supabase.py` | Modify | Joins sheet activities onto Humanity shifts; new `--skip-activities` flag. |
| `tests/test_sync_to_supabase.py` | Modify | Tests for the new flag and `attach_activities`. |
| `instructors/data.js` | Modify | Surfaces `row.activities` onto the shift object; drops the dead `PD` helper. |
| `instructors/myday.jsx` | Modify | Renders shared groups + per-instructor blocks from `shift.activities`. |
| `CLAUDE.md` | Modify | Documents the sheet pull, the `gws` dependency, and the new column. |

---

### Task 1: Schema migration

**Files:**
- Create: `sql/002_activities_column.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- v1.1: per-shift activity materials for the instructor hub.
-- Adds the `activities` JSONB column to the existing `shifts` table.
-- Idempotent — re-running is safe.

alter table shifts
  add column if not exists activities jsonb not null default '{}'::jsonb;
```

- [ ] **Step 2: Apply it to Supabase** *(human action — an agent cannot do this)*

Paste the contents of `sql/002_activities_column.sql` into the Supabase SQL editor and run it. The existing `public read` RLS policy on `shifts` already covers the new column.

- [ ] **Step 3: Commit**

```bash
git add sql/002_activities_column.sql
git commit -m "Add activities JSONB column to shifts table"
```

---

### Task 2: `sheet_activities.py` — parsing helpers

**Files:**
- Create: `scripts/sheet_activities.py`
- Create: `tests/test_sheet_activities.py`

- [ ] **Step 1: Create the test file with the parsing-helper tests**

Create `tests/test_sheet_activities.py`:

```python
"""Unit tests for scripts/sheet_activities.py."""
import json
import sys
import unittest
from datetime import date, time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sheet_activities as sa


class TestCell(unittest.TestCase):
    def test_returns_stripped_value(self):
        self.assertEqual(sa.cell(["  hi  ", "x"], 0), "hi")

    def test_short_row_returns_empty(self):
        self.assertEqual(sa.cell(["a"], 5), "")


class TestParseSheetDate(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(sa.parse_sheet_date("01-21-26"), date(2026, 1, 21))

    def test_no_leading_zeros(self):
        self.assertEqual(sa.parse_sheet_date("1-5-26"), date(2026, 1, 5))

    def test_bad_value_raises(self):
        with self.assertRaises(ValueError):
            sa.parse_sheet_date("not-a-date")


class TestParseClock(unittest.TestCase):
    def test_morning_no_leading_zero(self):
        self.assertEqual(sa.parse_clock("8:00"), time(8, 0))

    def test_afternoon(self):
        self.assertEqual(sa.parse_clock("13:30"), time(13, 30))

    def test_bad_value_raises(self):
        with self.assertRaises(ValueError):
            sa.parse_clock("noon")


class TestDeriveAmPm(unittest.TestCase):
    def test_before_noon_is_am(self):
        self.assertEqual(sa.derive_am_pm(time(11, 59)), "am")

    def test_noon_is_pm(self):
        self.assertEqual(sa.derive_am_pm(time(12, 0)), "pm")


class TestSplitCell(unittest.TestCase):
    def test_splits_and_trims(self):
        self.assertEqual(sa.split_cell("a, b ,c"), ["a", "b", "c"])

    def test_drops_empties(self):
        self.assertEqual(sa.split_cell("a, ,,b"), ["a", "b"])

    def test_blank_is_empty_list(self):
        self.assertEqual(sa.split_cell(""), [])


class TestIsNewFormat(unittest.TestCase):
    def test_new_header(self):
        self.assertTrue(sa.is_new_format(list(sa.EXPECTED_HEADER)))

    def test_old_cohort1_header(self):
        old = ["Class Date", "Start Time", "End Time", "Room", "Topic"]
        self.assertFalse(sa.is_new_format(old))

    def test_empty_header(self):
        self.assertFalse(sa.is_new_format([]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sheet_activities -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sheet_activities'`.

- [ ] **Step 3: Create `scripts/sheet_activities.py` with the helpers**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sheet_activities -v`
Expected: PASS — all parsing-helper tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/sheet_activities.py tests/test_sheet_activities.py
git commit -m "Add sheet_activities parsing helpers"
```

---

### Task 3: `round_robin`

**Files:**
- Modify: `scripts/sheet_activities.py`
- Modify: `tests/test_sheet_activities.py`

- [ ] **Step 1: Write the failing test**

Append this class to `tests/test_sheet_activities.py`, just above the `if __name__ == "__main__":` block:

```python
class TestRoundRobin(unittest.TestCase):
    def test_six_items_three_instructors(self):
        # per = 2: I0 gets items 0,3 · I1 gets 1,4 · I2 gets 2,5.
        self.assertEqual(sa.round_robin([0, 1, 2, 3, 4, 5], 3),
                         [[0, 3], [1, 4], [2, 5]])

    def test_six_items_four_instructors_drops_remainder(self):
        # per = 1: each gets one item; items 4 and 5 are dropped.
        self.assertEqual(sa.round_robin([0, 1, 2, 3, 4, 5], 4),
                         [[0], [1], [2], [3]])

    def test_fewer_items_than_instructors_drops_all(self):
        self.assertEqual(sa.round_robin([0, 1], 3), [[], [], []])

    def test_zero_instructors_returns_empty(self):
        self.assertEqual(sa.round_robin([0, 1, 2], 0), [])

    def test_empty_pool(self):
        self.assertEqual(sa.round_robin([], 3), [[], [], []])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$PY -m unittest tests.test_sheet_activities.TestRoundRobin -v`
Expected: FAIL — `AttributeError: module 'sheet_activities' has no attribute 'round_robin'`.

- [ ] **Step 3: Implement `round_robin`**

Append to the end of `scripts/sheet_activities.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `$PY -m unittest tests.test_sheet_activities.TestRoundRobin -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sheet_activities.py tests/test_sheet_activities.py
git commit -m "Add round_robin scenario distribution"
```

---

### Task 4: `resolve_doc_title` and `empty_activities`

**Files:**
- Modify: `scripts/sheet_activities.py`
- Modify: `tests/test_sheet_activities.py`

- [ ] **Step 1: Write the failing tests**

Append these classes to `tests/test_sheet_activities.py`, just above the `if __name__ == "__main__":` block:

```python
class TestResolveDocTitle(unittest.TestCase):
    def test_non_drive_url_returns_url(self):
        self.assertEqual(sa.resolve_doc_title("https://example.com/x"),
                         "https://example.com/x")

    def test_resolves_doc_title(self):
        url = "https://docs.google.com/document/d/ABC123/edit"
        fake = MagicMock(returncode=0, stdout='{"name": "My Doc"}')
        with patch.object(sa.subprocess, "run", return_value=fake):
            self.assertEqual(sa.resolve_doc_title(url), "My Doc")

    def test_gws_failure_falls_back_to_url(self):
        url = "https://docs.google.com/document/d/ABC123/edit"
        fake = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch.object(sa.subprocess, "run", return_value=fake):
            self.assertEqual(sa.resolve_doc_title(url), url)


class TestEmptyActivities(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(sa.empty_activities(),
                         {"perInstructor": {}, "shared": []})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sheet_activities.TestResolveDocTitle tests.test_sheet_activities.TestEmptyActivities -v`
Expected: FAIL — `AttributeError` for `resolve_doc_title` / `empty_activities`.

- [ ] **Step 3: Implement both functions**

Append to the end of `scripts/sheet_activities.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sheet_activities.TestResolveDocTitle tests.test_sheet_activities.TestEmptyActivities -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sheet_activities.py tests/test_sheet_activities.py
git commit -m "Add resolve_doc_title and empty_activities helpers"
```

---

### Task 5: `build_activities`

**Files:**
- Modify: `scripts/sheet_activities.py`
- Modify: `tests/test_sheet_activities.py`

- [ ] **Step 1: Write the failing tests**

Append this class to `tests/test_sheet_activities.py`, just above the `if __name__ == "__main__":` block:

```python
class TestBuildActivities(unittest.TestCase):
    # Identity resolver so tests are deterministic and gws-free.
    RESOLVE = staticmethod(lambda url: url)

    @staticmethod
    def row(date="01-21-26", start="8:00", title="", slugs="", scen_links="",
            pp_links="", act_links=""):
        # 14-column row (A–N); only the columns build_activities reads matter.
        r = [""] * 14
        r[sa.COL_DATE] = date
        r[sa.COL_START] = start
        r[sa.COL_TITLE] = title
        r[sa.COL_SCENARIO_SLUGS] = slugs
        r[sa.COL_SCENARIO_LINKS] = scen_links
        r[sa.COL_PP_SKILL_LINKS] = pp_links
        r[sa.COL_ACTIVITY_LINKS] = act_links
        return r

    def test_scenarios_round_robin_per_instructor(self):
        rows = [self.row(start="8:00", slugs="s1, s2, s3, s4")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}, {"name": "B"}],
                                  resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "s1", "href": sa.SLUG_BASE_URL + "s1"},
                  {"label": "s3", "href": sa.SLUG_BASE_URL + "s3"}],
            "B": [{"label": "s2", "href": sa.SLUG_BASE_URL + "s2"},
                  {"label": "s4", "href": sa.SLUG_BASE_URL + "s4"}],
        })
        self.assertEqual(out["shared"], [])

    def test_shared_groups_by_activity_title(self):
        rows = [self.row(start="9:00", title="XABC Cards",
                         act_links="http://u1, http://u2")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["shared"], [
            {"name": "XABC Cards",
             "links": [{"label": "http://u1", "href": "http://u1"},
                       {"label": "http://u2", "href": "http://u2"}]}])
        self.assertEqual(out["perInstructor"], {})

    def test_am_pm_split(self):
        rows = [self.row(start="8:00", slugs="morning"),
                self.row(start="13:00", slugs="afternoon")]
        out = sa.build_activities(rows, date(2026, 1, 21), "pm",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "afternoon",
                   "href": sa.SLUG_BASE_URL + "afternoon"}]})

    def test_no_matching_rows_is_empty(self):
        rows = [self.row(date="02-02-26", slugs="x")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out, {"perInstructor": {}, "shared": []})

    def test_partially_filled_rows(self):
        # Title but no links -> no shared group. Links but blank title ->
        # group with name "".
        rows = [self.row(start="8:00", title="Just a title"),
                self.row(start="9:00", title="", pp_links="http://only")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["shared"], [
            {"name": "", "links": [{"label": "http://only",
                                    "href": "http://only"}]}])
        self.assertEqual(out["perInstructor"], {})

    def test_unparseable_row_is_skipped(self):
        rows = [self.row(date="bad-date", start="8:00", slugs="skipme"),
                self.row(date="01-21-26", start="8:00", slugs="keep")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "keep", "href": sa.SLUG_BASE_URL + "keep"}]})

    def test_zero_instructors_drops_scenarios(self):
        rows = [self.row(start="8:00", slugs="s1, s2")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am", [],
                                  resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sheet_activities.TestBuildActivities -v`
Expected: FAIL — `AttributeError: module 'sheet_activities' has no attribute 'build_activities'`.

- [ ] **Step 3: Implement `_matching_rows` and `build_activities`**

Append to the end of `scripts/sheet_activities.py`:

```python
def _matching_rows(data_rows, target_date, am_pm):
    """Data rows for `target_date` whose start_time is in the am/pm block.

    Rows with a blank or unparseable date/start_time are skipped (a warning is
    printed for unparseable ones). The result is sorted by start_time.
    """
    matched = []
    for row in data_rows:
        raw_date = cell(row, COL_DATE)
        raw_start = cell(row, COL_START)
        if not raw_date or not raw_start:
            continue
        try:
            row_date = parse_sheet_date(raw_date)
            row_start = parse_clock(raw_start)
        except ValueError:
            sys.stderr.write(
                f"warning: skipping unparseable activity row "
                f"(date={raw_date!r}, start={raw_start!r})\n"
            )
            continue
        if row_date == target_date and derive_am_pm(row_start) == am_pm:
            matched.append((row_start, row))
    matched.sort(key=lambda pair: pair[0])
    return [row for _, row in matched]


def build_activities(data_rows, target_date, am_pm, instructors,
                     *, resolve=resolve_doc_title):
    """Assemble the `{perInstructor, shared}` blob for one shift.

    `data_rows` is the cohort tab's rows without the header. `instructors` is the
    shift's instructor list in Humanity order (each a dict with a "name").
    `resolve` maps a link URL to a display label — defaults to `resolve_doc_title`;
    tests inject a pure function. Best-effort: unparseable rows are skipped and
    blank cells contribute nothing.
    """
    rows = _matching_rows(data_rows, target_date, am_pm)

    # Per-instructor pool: each row's scenario slugs then scenario links.
    pool = []
    for row in rows:
        for slug in split_cell(cell(row, COL_SCENARIO_SLUGS)):
            pool.append({"label": slug, "href": SLUG_BASE_URL + slug})
        for link in split_cell(cell(row, COL_SCENARIO_LINKS)):
            pool.append({"label": resolve(link), "href": link})

    names = [i["name"] for i in instructors]
    buckets = round_robin(pool, len(names))
    per_instructor = {
        name: bucket for name, bucket in zip(names, buckets) if bucket
    }

    # Shared groups: one per row carrying pp_skill_links or activity_links.
    shared = []
    for row in rows:
        links = []
        for url in split_cell(cell(row, COL_PP_SKILL_LINKS)):
            links.append({"label": resolve(url), "href": url})
        for url in split_cell(cell(row, COL_ACTIVITY_LINKS)):
            links.append({"label": resolve(url), "href": url})
        if links:
            shared.append({"name": cell(row, COL_TITLE), "links": links})

    return {"perInstructor": per_instructor, "shared": shared}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sheet_activities.TestBuildActivities -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add scripts/sheet_activities.py tests/test_sheet_activities.py
git commit -m "Add build_activities shift assembler"
```

---

### Task 6: `gws_get_values` (I/O shell)

**Files:**
- Modify: `scripts/sheet_activities.py`
- Modify: `tests/test_sheet_activities.py`

- [ ] **Step 1: Write the failing tests**

Append this class to `tests/test_sheet_activities.py`, just above the `if __name__ == "__main__":` block:

```python
class TestGwsGetValues(unittest.TestCase):
    def test_returns_values_on_success(self):
        payload = '{"values": [["date", "x"], ["01-21-26", "y"]]}'
        fake = MagicMock(returncode=0, stdout=payload)
        with patch.object(sa.subprocess, "run", return_value=fake):
            rows = sa.gws_get_values(3)
        self.assertEqual(rows, [["date", "x"], ["01-21-26", "y"]])

    def test_requests_the_cohort_tab(self):
        fake = MagicMock(returncode=0, stdout='{"values": []}')
        with patch.object(sa.subprocess, "run", return_value=fake) as mock_run:
            sa.gws_get_values(3)
        cmd = mock_run.call_args[0][0]
        params = json.loads(cmd[cmd.index("--params") + 1])
        self.assertEqual(params["range"], "'Cohort 3'!A1:N1000")

    def test_nonzero_exit_raises_runtimeerror(self):
        fake = MagicMock(returncode=1, stdout="", stderr="auth expired")
        with patch.object(sa.subprocess, "run", return_value=fake):
            with self.assertRaises(RuntimeError):
                sa.gws_get_values(3)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sheet_activities.TestGwsGetValues -v`
Expected: FAIL — `AttributeError: module 'sheet_activities' has no attribute 'gws_get_values'`.

- [ ] **Step 3: Implement `gws_get_values`**

Append to the end of `scripts/sheet_activities.py`:

```python
def gws_get_values(cohort_number):
    """Fetch the `Cohort N` tab's cells via the `gws` CLI.

    Returns the raw rows (header included). Raises RuntimeError on any `gws`
    failure — the caller turns that into a hard stop with a re-auth message.
    """
    tab = f"Cohort {cohort_number}"
    cmd = [
        "gws", "sheets", "spreadsheets", "values", "get",
        "--params", json.dumps({
            "spreadsheetId": SPREADSHEET_ID,
            "range": f"'{tab}'!A1:N1000",
        }),
        "--format", "json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"gws failed for tab {tab!r}: {result.stderr or result.stdout}"
        )
    brace = result.stdout.find("{")
    if brace == -1:
        raise RuntimeError(
            f"no JSON in gws output for tab {tab!r}: {result.stdout!r}"
        )
    return json.loads(result.stdout[brace:]).get("values", [])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sheet_activities.TestGwsGetValues -v`
Expected: PASS.

- [ ] **Step 5: Run the whole `sheet_activities` suite**

Run: `$PY -m unittest tests.test_sheet_activities -v`
Expected: PASS — every class green.

- [ ] **Step 6: Commit**

```bash
git add scripts/sheet_activities.py tests/test_sheet_activities.py
git commit -m "Add gws_get_values sheet fetch"
```

---

### Task 7: `--skip-activities` flag

**Files:**
- Modify: `scripts/sync_to_supabase.py` (`parse_args`)
- Modify: `tests/test_sync_to_supabase.py` (`TestParseArgs`)

- [ ] **Step 1: Write the failing tests**

Add these two methods to the `TestParseArgs` class in `tests/test_sync_to_supabase.py` (after `test_dry_run`):

```python
    def test_skip_activities_defaults_false(self):
        self.assertFalse(s.parse_args([]).skip_activities)

    def test_skip_activities_flag(self):
        self.assertTrue(s.parse_args(["--skip-activities"]).skip_activities)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sync_to_supabase.TestParseArgs -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'skip_activities'`.

- [ ] **Step 3: Add the argument**

In `scripts/sync_to_supabase.py`, in `parse_args`, replace:

```python
    p.add_argument("--dry-run", action="store_true",
                   help="Print rows that would be upserted; make no Supabase call.")
    args = p.parse_args(argv)
```

with:

```python
    p.add_argument("--dry-run", action="store_true",
                   help="Print rows that would be upserted; make no Supabase call.")
    p.add_argument("--skip-activities", action="store_true",
                   help="Skip the activity-sheet pull (shifts only; no gws needed).")
    args = p.parse_args(argv)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sync_to_supabase.TestParseArgs -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add --skip-activities flag to the sync"
```

---

### Task 8: `attach_activities` and `main()` wiring

**Files:**
- Modify: `scripts/sync_to_supabase.py` (new `attach_activities`; `main()`)
- Modify: `tests/test_sync_to_supabase.py` (new `TestAttachActivities`)

- [ ] **Step 1: Write the failing tests**

Append this class to `tests/test_sync_to_supabase.py`, just above the `if __name__ == "__main__":` block:

```python
class TestAttachActivities(unittest.TestCase):
    HEADER = [
        "date", "day_of_week", "shift", "start_time", "end_time", "duration_min",
        "activity_type", "activity_id", "activity_title", "activity_description",
        "scenario_slugs", "scenario_links", "pp_skill_links", "activity_links",
    ]

    def _row(self, sheet_date, start, slugs=""):
        r = [""] * 14
        r[0] = sheet_date
        r[3] = start
        r[10] = slugs
        return r

    def _shift_row(self, cohort, shift_date, am_pm):
        return {
            "shift_date": shift_date, "am_pm": am_pm, "cohort_number": cohort,
            "class_id": 916, "instructors": [{"name": "A", "role": "Lead"}],
        }

    def test_attaches_built_activities(self):
        tab = [self.HEADER, self._row("05-20-26", "8:00", "scn1")]
        rows = [self._shift_row(3, "2026-05-20", "am")]
        s.attach_activities(rows, get_values=lambda c: tab, resolve=lambda u: u)
        self.assertEqual(
            rows[0]["activities"]["perInstructor"],
            {"A": [{"label": "scn1",
                    "href": "https://matc-ems.github.io/scenarios/main-lab/scn1"}]},
        )

    def test_old_format_tab_yields_empty(self):
        old_tab = [["Class Date", "Start Time", "End Time", "Room", "Topic"]]
        rows = [self._shift_row(1, "2026-05-20", "am")]
        s.attach_activities(rows, get_values=lambda c: old_tab,
                            resolve=lambda u: u)
        self.assertEqual(rows[0]["activities"],
                         {"perInstructor": {}, "shared": []})

    def test_tab_fetched_once_per_cohort(self):
        calls = []

        def fake_get(cohort):
            calls.append(cohort)
            return [self.HEADER]

        rows = [self._shift_row(3, "2026-05-20", "am"),
                self._shift_row(3, "2026-05-20", "pm")]
        s.attach_activities(rows, get_values=fake_get, resolve=lambda u: u)
        self.assertEqual(calls, [3])  # one fetch despite two cohort-3 shifts
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$PY -m unittest tests.test_sync_to_supabase.TestAttachActivities -v`
Expected: FAIL — `AttributeError: module 'sync_to_supabase' has no attribute 'attach_activities'`.

- [ ] **Step 3: Add `attach_activities`**

In `scripts/sync_to_supabase.py`, insert this function immediately above the `def upsert_to_supabase(` line:

```python
def attach_activities(rows, *, get_values=None, resolve=None):
    """Attach an `activities` blob to every shift row, in place.

    Fetches each cohort's sheet tab once (cached). A cohort whose tab is missing
    or still in the old format gets `empty_activities()` for all its shifts,
    with a warning. `get_values` / `resolve` are injectable for tests; they
    default to the gws-backed functions in sheet_activities.
    """
    import sheet_activities as sa

    if get_values is None:
        get_values = sa.gws_get_values
    if resolve is None:
        resolve = sa.resolve_doc_title

    tab_cache = {}  # cohort_number -> data rows (None means an unusable tab)

    def cohort_data(cohort_number):
        if cohort_number not in tab_cache:
            values = get_values(cohort_number)
            if values and sa.is_new_format(values[0]):
                tab_cache[cohort_number] = values[1:]
            else:
                sys.stderr.write(
                    f"warning: Cohort {cohort_number} sheet tab is empty or "
                    f"not the 14-column activity format; no activities for it\n"
                )
                tab_cache[cohort_number] = None
        return tab_cache[cohort_number]

    for row in rows:
        data_rows = cohort_data(row["cohort_number"])
        if data_rows is None:
            row["activities"] = sa.empty_activities()
            continue
        row["activities"] = sa.build_activities(
            data_rows,
            date.fromisoformat(row["shift_date"]),
            row["am_pm"],
            row["instructors"],
            resolve=resolve,
        )
```

(`date` is already imported at the top of `sync_to_supabase.py` via
`from datetime import date, time, timedelta`.)

- [ ] **Step 4: Wire `attach_activities` into `main()` and extend the report**

In `scripts/sync_to_supabase.py`, in `main()`, replace:

```python
    # Report per-shift.
    for r in rows:
        n_inst = len(r["instructors"])
        print(
            f"{r['shift_date']} {r['am_pm'].upper():2} "
            f"C{r['cohort_number']} #{r['class_id']} — "
            f"{n_inst} instructor{'s' if n_inst != 1 else ''}"
        )
```

with:

```python
    # Attach activity-sheet data (unless skipped).
    if not args.skip_activities:
        try:
            attach_activities(rows)
        except RuntimeError as exc:
            sys.stderr.write(
                f"{exc}\n\n"
                "The activity-sheet pull needs the `gws` CLI authenticated.\n"
                "Run `gws auth login` and retry, or pass --skip-activities to "
                "sync shifts only.\n"
            )
            sys.exit(4)

    # Report per-shift.
    for r in rows:
        n_inst = len(r["instructors"])
        acts = r.get("activities") or {}
        n_shared = len(acts.get("shared", []))
        n_scn = sum(len(v) for v in acts.get("perInstructor", {}).values())
        print(
            f"{r['shift_date']} {r['am_pm'].upper():2} "
            f"C{r['cohort_number']} #{r['class_id']} — "
            f"{n_inst} instructor{'s' if n_inst != 1 else ''}, "
            f"{n_shared} shared, {n_scn} scenario{'s' if n_scn != 1 else ''}"
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$PY -m unittest tests.test_sync_to_supabase -v`
Expected: PASS — `TestAttachActivities` and every existing class green.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Join sheet activities onto Humanity shifts in the sync"
```

---

### Task 9: Frontend — render activities on the instructor hub

**Files:**
- Modify: `instructors/data.js`
- Modify: `instructors/myday.jsx`

The repo has no JavaScript test runner — these files are verified by loading
the page (this task) and end-to-end against real data (Task 11). `data.js` and
`myday.jsx` must change together so the page is never broken between commits.

- [ ] **Step 1: Update the `data.js` shape-contract comment**

In `instructors/data.js`, replace:

```javascript
//   schedule[cohortId][dayIdx] = { am: Shift|null, pm: Shift|null }
//   Shift = { type, title, room, instructors: [{name, role}], scenarios?: [...] }
```

with:

```javascript
//   schedule[cohortId][dayIdx] = { am: Shift|null, pm: Shift|null }
//   Shift = { type, title, room, instructors: [{name, role}],
//             activities: { perInstructor: {<name>: [{label, href}]},
//                           shared: [{name, links: [{label, href}]}] } }
```

- [ ] **Step 2: Surface `activities` in `shiftFromRow`**

In `instructors/data.js`, replace:

```javascript
function shiftFromRow(row) {
  return {
    type: row.type || "scenario",                       // fallback until v2 wires `type`
    title: row.title || `EMS-${row.class_id}`,
    room: row.room || "",
    instructors: Array.isArray(row.instructors) ? row.instructors : [],
    // scenarios stays absent in v1; component handles its absence gracefully.
  };
}
```

with:

```javascript
function shiftFromRow(row) {
  const acts = row.activities || {};
  return {
    type: row.type || "scenario",                       // fallback until v2 wires `type`
    title: row.title || `EMS-${row.class_id}`,
    room: row.room || "",
    instructors: Array.isArray(row.instructors) ? row.instructors : [],
    // Resolved at sync time by scripts/sheet_activities.py; normalized here so
    // the component never sees a missing key.
    activities: {
      perInstructor: (acts && acts.perInstructor) || {},
      shared: (acts && Array.isArray(acts.shared)) ? acts.shared : [],
    },
  };
}
```

- [ ] **Step 3: Delete the dead `window.PD` helper**

In `instructors/data.js`, delete this entire block (it is the last thing in the file):

```javascript
// PD helpers used by myday.jsx (`window.PD.scenariosByInstructor`). Kept here
// for symmetry with the original reference file. v1 shifts have no scenarios,
// so this returns null for every shift and the component falls through to its
// "flat instructor list" branch.
window.PD = {
  scenariosByInstructor(shift) {
    if (!shift || !shift.scenarios || shift.scenarios.length === 0) return null;
    const result = new Map();
    shift.instructors.forEach(i => result.set(i.name, []));
    const shared = [];
    shift.scenarios.forEach(scn => {
      if (!scn.assignedTo) { shared.push(scn); return; }
      const targets = Array.isArray(scn.assignedTo) ? scn.assignedTo : [scn.assignedTo];
      targets.forEach(t => {
        if (!result.has(t)) result.set(t, []);
        result.get(t).push(scn);
      });
    });
    return { perInstructor: result, shared };
  }
};
```

- [ ] **Step 4: Rewrite the `D5ShiftCard` body in `myday.jsx`**

In `instructors/myday.jsx`, in `D5ShiftCard`, replace everything from
`const grouped = window.PD.scenariosByInstructor(shift);` through the end of the
function's `return` (the block below):

```javascript
  const grouped = window.PD.scenariosByInstructor(shift);
  const hasMultiInstructors = shift.instructors.length > 1;

  return (
    <div className={`rail-c${cIdx}`} style={{
      background: "var(--bg-card)",
      border: "1px solid var(--line)",
      borderRadius: 10,
      padding: "14px 16px 16px 22px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-mid)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {cohort.name}
        </div>
        <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>{shift.room}</span>
      </div>

      <div className="font-serif" style={{ fontSize: 22, lineHeight: 1.15, marginBottom: 10 }}>
        {shift.title}
      </div>

      {/* Per-instructor blocks */}
      {grouped ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {grouped.shared.length > 0 && (
            <D5ScenarioGroup label="Everyone" scenarios={grouped.shared} />
          )}
          {[...grouped.perInstructor.entries()].map(([name, scns]) => (
            <D5InstructorBlock
              key={name}
              name={name}
              scenarios={scns}
              solo={!hasMultiInstructors}
            />
          ))}
        </div>
      ) : (
        // No scenarios — show instructors flat + optional link
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {shift.instructors.map((ins, i) => (
            <div key={i} style={{ fontSize: 13, fontWeight: 500 }}>
              {ins.name}
            </div>
          ))}
          {shift.link && (
            <a href={shift.link.href} className="scenario-link" style={{ marginTop: 6, fontSize: 13 }}>{shift.link.label}</a>
          )}
        </div>
      )}
    </div>
  );
```

with:

```javascript
  const { perInstructor, shared } = shift.activities;
  const hasMultiInstructors = shift.instructors.length > 1;
  const hasAssigned = shift.instructors.some(
    ins => (perInstructor[ins.name] || []).length > 0
  );

  return (
    <div className={`rail-c${cIdx}`} style={{
      background: "var(--bg-card)",
      border: "1px solid var(--line)",
      borderRadius: 10,
      padding: "14px 16px 16px 22px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-mid)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {cohort.name}
        </div>
        <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>{shift.room}</span>
      </div>

      <div className="font-serif" style={{ fontSize: 22, lineHeight: 1.15, marginBottom: 10 }}>
        {shift.title}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Shared material groups, one per activity, above the instructors. */}
        {shared.map((group, gi) => (
          <D5ScenarioGroup key={`shared-${gi}`} label={group.name} scenarios={group.links} />
        ))}

        {/* Instructors: per-instructor blocks when scenarios are assigned,
            otherwise a flat name list (same as a shift with no sheet data). */}
        {hasAssigned ? (
          shift.instructors.map(ins => (
            <D5InstructorBlock
              key={ins.name}
              name={ins.name}
              scenarios={perInstructor[ins.name] || []}
              solo={!hasMultiInstructors}
            />
          ))
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {shift.instructors.map((ins, i) => (
              <div key={i} style={{ fontSize: 13, fontWeight: 500 }}>
                {ins.name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
```

- [ ] **Step 5: Update the scenario-item label field**

The activity data uses `{label, href}`, not `{title, href}`. In
`instructors/myday.jsx`, replace `{s.title}` with `{s.label}` everywhere
(it appears twice — in `D5InstructorBlock` and in `D5ScenarioGroup`). Use a
replace-all so both are changed.

- [ ] **Step 6: Make the `D5ScenarioGroup` heading optional**

A shared group built from a row with a blank `activity_title` has `name: ""`.
In `instructors/myday.jsx`, in `D5ScenarioGroup`, replace:

```javascript
      <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
        {label}
      </div>
```

with:

```javascript
      {label && (
        <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
          {label}
        </div>
      )}
```

- [ ] **Step 7: Verify the page still renders**

Run: `$PY -m unittest tests.test_frontend_paths -v`
Expected: PASS — resource paths unchanged.

Then run `python3 -m http.server 8000`, open `http://localhost:8000/instructors/`,
and confirm: the page loads, shift cards render, and the browser console shows
**no errors**. (Until the sync runs in Task 11, `activities` is `{}` for every
row, so every card shows its flat instructor list — exactly as before.)

- [ ] **Step 8: Commit**

```bash
git add instructors/data.js instructors/myday.jsx
git commit -m "Render shift activities on the instructor hub"
```

---

### Task 10: Documentation — `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Note the `gws` dependency in the Commands intro**

In `CLAUDE.md`, replace:

```
The sync script and the test suite run on the **matc-humanity skill's
virtualenv**, not system Python — that venv is where `requests` and
`python-dotenv` live. Do not `pip install` into system Python.
`build_sim_lab_index.py` uses only the standard library and runs on plain
`python3`. Run everything below from the repo root.
```

with:

```
The sync script and the test suite run on the **matc-humanity skill's
virtualenv**, not system Python — that venv is where `requests` and
`python-dotenv` live. Do not `pip install` into system Python.
`build_sim_lab_index.py` uses only the standard library and runs on plain
`python3`. The sync also shells out to the `gws` CLI to read the activity
sheet; it must be on PATH and authenticated (`gws auth login`). Pass
`--skip-activities` to run the sync without it. Run everything below from the
repo root.
```

- [ ] **Step 2: Add the `--skip-activities` example**

In `CLAUDE.md`, replace:

```
$PY scripts/sync_to_supabase.py --input shifts.json   # skip the Humanity call
```

with:

```
$PY scripts/sync_to_supabase.py --input shifts.json   # skip the Humanity call
$PY scripts/sync_to_supabase.py --skip-activities     # shifts only, no sheet/gws
```

- [ ] **Step 3: Update the schema-changes note**

In `CLAUDE.md`, replace:

```
Schema changes: paste `sql/001_shifts.sql` into the Supabase SQL editor. It is
idempotent (`create ... if not exists`), so re-running is safe.
```

with:

```
Schema changes: paste the files in `sql/` (`001_shifts.sql`, then
`002_activities_column.sql`) into the Supabase SQL editor, in order. They are
idempotent, so re-running is safe.
```

- [ ] **Step 4: Document the sheet pull in the Data pipeline section**

In `CLAUDE.md`, replace:

```
`scripts/class_titles.py` is the **only** file to edit when relabeling a class
on the instructor hub. An empty string normalizes to `NULL`, and the frontend then
falls back to `EMS-<id>`. Class 917 is intentionally absent (unused class
number).
```

with:

```
`scripts/class_titles.py` is the **only** file to edit when relabeling a class
on the instructor hub. An empty string normalizes to `NULL`, and the frontend then
falls back to `EMS-<id>`. Class 917 is intentionally absent (unused class
number).

`scripts/sheet_activities.py` pulls per-shift lab activities from the "Lesson
Plan Material" Google Sheet (one tab per cohort) via the `gws` CLI. For each
Humanity shift, `sync_to_supabase.py` calls `build_activities()` to assemble the
`activities` JSONB blob — scenario slugs/links round-robin'd across the shift's
instructors, and `pp_skill_links` / `activity_links` grouped by activity name
for everyone. A cohort tab that is missing or still in the old format yields
empty activities (the shift then renders with just its instructor list). This
re-implements logic that overlaps the matc-lesson-plan skill's
`pull_activity_data.py` so the site pipeline stays self-contained and testable.
```

- [ ] **Step 5: Update the "Things to know" section**

In `CLAUDE.md`, replace:

```
- **Reserved columns:** `type` and `room` exist in the table but are always
  `NULL` in v1. They are reserved for v2 (pill colors and the room label). The
  `scenarios` per-instructor UI in `instructors/myday.jsx` is likewise dormant — v1 shifts
  have no scenarios, so `window.PD.scenariosByInstructor` returns `null` and the
  component renders a flat instructor list.
```

with:

```
- **Reserved columns:** `type` and `room` exist in the table but are always
  `NULL` in v1. They are reserved for v2 (pill colors and the room label).
- **Activity data:** `shifts.activities` (JSONB) holds the resolved per-shift
  lab activities — `{perInstructor, shared}` — written by `sync_to_supabase.py`
  from the "Lesson Plan Material" sheet and rendered directly by
  `instructors/myday.jsx`. The sync needs the `gws` CLI authenticated; a `gws`
  failure aborts the run with a re-auth message. `--skip-activities` runs the
  Humanity-only sync.
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "Document the activity-sheet pull in CLAUDE.md"
```

---

### Task 11: End-to-end verification

**Files:** none (verification only — no commit).

Prerequisites: `sql/002_activities_column.sql` applied (Task 1), the matc-humanity
bearer token valid, `gws` authenticated, `.env` populated.

- [ ] **Step 1: Run the full test suite**

Run: `$PY -m unittest discover -s tests`
Expected: PASS — every test across all files (`OK`).

- [ ] **Step 2: Dry-run the sync for a week with Cohort 3 sheet data**

Pick a Monday–Friday range whose dates appear in the `Cohort 3` tab of the
"Lesson Plan Material" sheet, then run (substituting the dates):

Run: `$PY scripts/sync_to_supabase.py --dry-run --from <YYYY-MM-DD> --to <YYYY-MM-DD> --cohorts 3`
Expected: each printed line ends with `… N shared, M scenarios`, with non-zero
counts on shifts that have sheet rows. No traceback. (If a week has no sheet
rows, counts are `0 shared, 0 scenarios` — that is the valid empty case.)

- [ ] **Step 3: Run the real sync**

Run: `$PY scripts/sync_to_supabase.py --from <YYYY-MM-DD> --to <YYYY-MM-DD>`
Expected: ends with `Upserted N shifts into Supabase.` and no error. A warning
for `Cohort 1` (old-format tab) is expected and harmless.

- [ ] **Step 4: Verify the instructor hub**

Run `python3 -m http.server 8000`, open `http://localhost:8000/instructors/`,
and use the day picker to land on a day in the synced range. Confirm:
- Cohort 3 shift cards show shared material groups (with working links) above
  the instructors, and per-instructor scenario lists when scenarios were dealt.
- A shift with no sheet data still shows its flat instructor list.
- The browser console shows no errors.

---

## Notes for the executor

- **Task order matters.** Tasks 2→6 append functions to `sheet_activities.py` in
  dependency order (`build_activities`'s default arg references
  `resolve_doc_title`). Do not reorder.
- **Task 1 Step 2 and Task 11 need a human / live credentials** — Supabase SQL
  editor access, the Humanity token, and `gws` auth. The Python/test tasks
  (2–10) are fully self-contained and need none of that.
- The spec's resilience requirements (no rows / partial rows / unparseable rows
  / old-format tab / `gws` failure) are exercised by `TestBuildActivities`
  (Task 5) and `TestAttachActivities` (Task 8).




