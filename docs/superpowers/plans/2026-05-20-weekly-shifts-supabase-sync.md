# Weekly Shifts → Supabase Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data pipeline that pulls EMS lab shifts from Humanity via the existing `matc-humanity` skill, enriches them with a class_id → title lookup, and upserts them into a Supabase `shifts` table that the Vercel homepage will eventually read.

**Architecture:** A new Python script `scripts/sync_to_supabase.py` (running on the existing `matc-humanity` venv) subprocess-calls `humanity_agent.py --workflow` to get a workflow JSON file, normalizes each shift (parses times, derives `am_pm`, looks up `title`, derives instructor `role` from `cohort_lead_last_name`), and POSTs to Supabase PostgREST as an upsert keyed on `(shift_date, cohort_number, start_time)`. A separate `scripts/class_titles.py` holds the hand-maintained class_id → title map. `sql/001_shifts.sql` declares the table + RLS.

**Tech Stack:** Python 3 (stdlib `unittest` for tests, `requests` + `python-dotenv` from the matc-humanity venv), Supabase PostgREST, SQL.

---

## File Structure

| Path | Responsibility |
|---|---|
| `sql/001_shifts.sql` | Idempotent SQL: `shifts` table + index + RLS policy. Run once in Supabase. |
| `.env.example` | Template showing required env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`). |
| `.gitignore` | Add `.env` and `__pycache__/` so secrets and bytecode never get committed. |
| `scripts/class_titles.py` | Single module-level dict `CLASS_TITLES`. Edit by hand. No logic. |
| `scripts/sync_to_supabase.py` | Sync logic: time parsing, normalization, Humanity subprocess, Supabase upsert, CLI, `main()`. |
| `tests/test_class_titles.py` | One sanity test that the lookup imports and has expected keys. |
| `tests/test_sync_to_supabase.py` | Pure-function tests for parsers, normalizers, and date-range helpers; mocked tests for the subprocess and HTTP calls. |

Tests use stdlib `unittest`. Run with `python -m unittest discover -s tests -v` from the repo root.

The matc-humanity skill is **not modified** by any task in this plan.

---

## Conventions

- Run every command from the repo root: `/home/raff/Desktop/matc-ems-site`.
- The matc-humanity venv interpreter is `~/.claude/skills/matc-humanity/.venv/bin/python`. Call it as `PY=~/.claude/skills/matc-humanity/.venv/bin/python` in the shell, or use the literal path in scripts.
- Each task ends with a commit on the `weekly-shifts-supabase-sync` branch (already created off `main`).

---

## Task 1: Project scaffolding (SQL, env, gitignore, tests dir)

**Files:**
- Create: `sql/001_shifts.sql`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `tests/__init__.py` (empty — makes the dir importable)

- [ ] **Step 1: Create `sql/001_shifts.sql`**

```sql
-- v1: shifts table for the matc-ems-site homepage.
-- Idempotent — re-running is safe.

create table if not exists shifts (
  id                    bigserial primary key,
  shift_date            date    not null,
  am_pm                 text    not null check (am_pm in ('am','pm')),
  cohort_number         int     not null check (cohort_number between 1 and 4),
  class_id              int     not null,
  start_time            time    not null,
  end_time              time    not null,
  title                 text,
  type                  text    check (type is null or type in
                          ('scenario','lecture','skills','clinical','exam')),
  room                  text,
  instructors           jsonb   not null default '[]'::jsonb,
  cohort_lead_last_name text,
  synced_at             timestamptz not null default now(),
  unique (shift_date, cohort_number, start_time)
);

create index if not exists shifts_date_idx on shifts (shift_date);

alter table shifts enable row level security;

drop policy if exists "public read" on shifts;
create policy "public read" on shifts for select using (true);
```

- [ ] **Step 2: Create `.env.example`**

```
# Copy to .env (gitignored) and fill in real values.
# SUPABASE_URL is also baked into the public index.html as the anon read endpoint.
SUPABASE_URL=https://tapgnqgbszyhrkjsjmrg.supabase.co

# Service-role key. Has full write access. NEVER commit, never ship to the browser.
# Get from: Supabase dashboard -> Project Settings -> API -> service_role secret
SUPABASE_SERVICE_KEY=
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.venv/
```

- [ ] **Step 4: Create `tests/__init__.py` (empty file)**

```
```

(Yes, an empty file. Run `: > tests/__init__.py` to create it, or `touch tests/__init__.py`.)

- [ ] **Step 5: Verify nothing crashes**

```bash
python -m unittest discover -s tests -v
```

Expected: `Ran 0 tests in 0.000s — OK` (no tests yet, but discovery works).

- [ ] **Step 6: Commit**

```bash
git add sql/001_shifts.sql .env.example .gitignore tests/__init__.py
git commit -m "Scaffold sync project: SQL schema, env template, gitignore, tests dir"
```

---

## Task 2: `scripts/class_titles.py` lookup module

**Files:**
- Create: `scripts/class_titles.py`
- Create: `tests/test_class_titles.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_class_titles.py`:

```python
"""Sanity checks on the class_id → title lookup."""
import sys
import unittest
from pathlib import Path

# Make scripts/ importable without packaging it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from class_titles import CLASS_TITLES


class TestClassTitles(unittest.TestCase):
    def test_known_ids_present(self):
        # 912-921 except 917 are the EMS lab class IDs (per matc-generate-week).
        expected_ids = {912, 913, 914, 915, 916, 918, 919, 920, 921}
        self.assertEqual(set(CLASS_TITLES.keys()), expected_ids)

    def test_917_intentionally_absent(self):
        self.assertNotIn(917, CLASS_TITLES)

    def test_values_are_strings(self):
        for cid, title in CLASS_TITLES.items():
            self.assertIsInstance(title, str, f"title for {cid} is not a str")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_class_titles -v
```

Expected: `ModuleNotFoundError: No module named 'class_titles'`.

- [ ] **Step 3: Create `scripts/class_titles.py`**

```python
"""class_id (int) → human-readable shift title (str).

This is the only file you edit when you want to relabel a class on the homepage.
Empty strings are intentional placeholders; the sync script normalizes "" to
NULL in the database, and the frontend will fall back to "EMS-<id>".

Class 917 is intentionally absent — that class number is unused in the program.
"""

CLASS_TITLES: dict[int, str] = {
    912: "",
    913: "Adv. Patient Assessment",
    914: "",
    915: "",
    916: "",
    # 917 intentionally absent.
    918: "",
    919: "",
    920: "",
    921: "",
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m unittest tests.test_class_titles -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/class_titles.py tests/test_class_titles.py
git commit -m "Add class_id → title lookup with placeholder values"
```

---

## Task 3: Pure helper functions (`parse_time`, `last_name`, `derive_am_pm`, `derive_role`)

**Files:**
- Create: `scripts/sync_to_supabase.py`
- Create: `tests/test_sync_to_supabase.py`

These four helpers are pure functions with no I/O. They get fully tested before any orchestration code is written.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sync_to_supabase.py`:

```python
"""Unit tests for scripts/sync_to_supabase.py — pure-function layer."""
import sys
import unittest
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_to_supabase as s


class TestParseTime(unittest.TestCase):
    def test_morning(self):
        self.assertEqual(s.parse_time("08:00AM"), time(8, 0))

    def test_late_morning(self):
        self.assertEqual(s.parse_time("11:55AM"), time(11, 55))

    def test_noon(self):
        # 12:00PM is noon -> 12:00 in 24h.
        self.assertEqual(s.parse_time("12:00PM"), time(12, 0))

    def test_afternoon(self):
        self.assertEqual(s.parse_time("01:00PM"), time(13, 0))

    def test_late_afternoon(self):
        self.assertEqual(s.parse_time("04:55PM"), time(16, 55))


class TestLastName(unittest.TestCase):
    def test_standard_humanity_format(self):
        self.assertEqual(s.last_name("Smith, Scott"), "Smith")

    def test_with_extra_whitespace(self):
        self.assertEqual(s.last_name("Olson,  Michael"), "Olson")

    def test_unexpected_format_returns_input(self):
        # No comma -> can't split. Fall back to the whole string so derive_role
        # still has something deterministic to compare against (and will likely
        # produce "Assist", which is the safe default).
        self.assertEqual(s.last_name("Plain Name"), "Plain Name")


class TestDeriveAmPm(unittest.TestCase):
    def test_eight_am_is_am(self):
        self.assertEqual(s.derive_am_pm(time(8, 0)), "am")

    def test_eleven_fifty_five_is_am(self):
        self.assertEqual(s.derive_am_pm(time(11, 55)), "am")

    def test_noon_is_pm(self):
        # Boundary call: 12:00 counts as PM (afternoon session).
        self.assertEqual(s.derive_am_pm(time(12, 0)), "pm")

    def test_one_pm_is_pm(self):
        self.assertEqual(s.derive_am_pm(time(13, 0)), "pm")


class TestDeriveRole(unittest.TestCase):
    def test_lead_when_last_name_matches(self):
        self.assertEqual(s.derive_role("Dean, John", "Dean"), "Lead")

    def test_assist_when_last_name_differs(self):
        self.assertEqual(s.derive_role("Smith, Bob", "Dean"), "Assist")

    def test_assist_when_name_format_is_unexpected(self):
        # last_name("Plain Name") == "Plain Name" which won't equal "Dean".
        self.assertEqual(s.derive_role("Plain Name", "Dean"), "Assist")

    def test_assist_when_cohort_lead_is_none(self):
        self.assertEqual(s.derive_role("Dean, John", None), "Assist")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them to verify they fail**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: `ModuleNotFoundError: No module named 'sync_to_supabase'`.

- [ ] **Step 3: Create `scripts/sync_to_supabase.py` with the four helpers**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 16 tests pass (5 + 3 + 4 + 4).

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add pure helpers: parse_time, last_name, derive_am_pm, derive_role"
```

---

## Task 4: `normalize_shift` (composes the helpers into a row dict)

**Files:**
- Modify: `scripts/sync_to_supabase.py` (add `normalize_shift`)
- Modify: `tests/test_sync_to_supabase.py` (add `TestNormalizeShift`)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_to_supabase.py` (above the `if __name__ == "__main__":` line):

```python
class TestNormalizeShift(unittest.TestCase):
    SAMPLE_SHIFT = {
        "date": "2026-05-19",
        "starting_time": "08:00AM",
        "ending_time": "11:55AM",
        "instructors": [
            {"name": "Dean, John"},
            {"name": "Cech, Kevin"},
            {"name": "Nickels, Keith"},
        ],
        "class_id": 918,
        "cohort_number": 3,
        "cohort_lead_last_name": "Dean",
        "equipment_list": [],
        "summary": None,
        "activities": [],
        "reference_material": [],
    }

    def test_top_level_fields(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={918: "Trauma"})
        self.assertEqual(row["shift_date"], "2026-05-19")
        self.assertEqual(row["am_pm"], "am")
        self.assertEqual(row["cohort_number"], 3)
        self.assertEqual(row["class_id"], 918)
        self.assertEqual(row["start_time"], "08:00:00")
        self.assertEqual(row["end_time"], "11:55:00")
        self.assertEqual(row["title"], "Trauma")
        self.assertEqual(row["cohort_lead_last_name"], "Dean")

    def test_missing_class_id_in_lookup_yields_null_title(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={})
        self.assertIsNone(row["title"])

    def test_empty_string_title_in_lookup_normalizes_to_null(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={918: ""})
        self.assertIsNone(row["title"])

    def test_instructors_get_roles(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={})
        self.assertEqual(
            row["instructors"],
            [
                {"name": "Dean, John",    "role": "Lead"},
                {"name": "Cech, Kevin",   "role": "Assist"},
                {"name": "Nickels, Keith","role": "Assist"},
            ],
        )

    def test_pm_shift_derives_pm(self):
        pm = {**self.SAMPLE_SHIFT, "starting_time": "01:00PM", "ending_time": "04:55PM"}
        row = s.normalize_shift(pm, class_titles={})
        self.assertEqual(row["am_pm"], "pm")
        self.assertEqual(row["start_time"], "13:00:00")
        self.assertEqual(row["end_time"], "16:55:00")
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_sync_to_supabase.TestNormalizeShift -v
```

Expected: `AttributeError: module 'sync_to_supabase' has no attribute 'normalize_shift'`.

- [ ] **Step 3: Add `normalize_shift` to `scripts/sync_to_supabase.py`**

Append to the file:

```python
def normalize_shift(shift: dict, *, class_titles: dict[int, str]) -> dict:
    """Transform one Humanity workflow shift into a row ready for Supabase.

    Returns a dict matching the `shifts` table columns the v1 sync writes.
    `type` and `room` are not set here — they default to NULL in the table.
    """
    start = parse_time(shift["starting_time"])
    end = parse_time(shift["ending_time"])
    lead_last = shift.get("cohort_lead_last_name")
    raw_title = class_titles.get(shift["class_id"], "")
    title = raw_title or None  # empty string -> NULL

    return {
        "shift_date": shift["date"],
        "am_pm": derive_am_pm(start),
        "cohort_number": shift["cohort_number"],
        "class_id": shift["class_id"],
        "start_time": start.strftime("%H:%M:%S"),
        "end_time": end.strftime("%H:%M:%S"),
        "title": title,
        "instructors": [
            {"name": i["name"], "role": derive_role(i["name"], lead_last)}
            for i in shift["instructors"]
        ],
        "cohort_lead_last_name": lead_last,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 21 tests pass total (the 16 from Task 3 plus 5 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add normalize_shift composing helpers into Supabase row dicts"
```

---

## Task 5: `current_week_range` (Monday–Friday computation)

**Files:**
- Modify: `scripts/sync_to_supabase.py`
- Modify: `tests/test_sync_to_supabase.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_to_supabase.py`:

```python
from datetime import date


class TestCurrentWeekRange(unittest.TestCase):
    def test_monday_returns_same_week(self):
        # 2026-05-18 is a Monday.
        mon, fri = s.current_week_range(today=date(2026, 5, 18))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_tuesday_resolves_back_to_monday(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 19))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_friday_returns_same_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 22))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_saturday_resolves_to_just_ended_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 23))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_sunday_resolves_to_just_ended_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 24))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_sync_to_supabase.TestCurrentWeekRange -v
```

Expected: `AttributeError: module 'sync_to_supabase' has no attribute 'current_week_range'`.

- [ ] **Step 3: Add `current_week_range` to `scripts/sync_to_supabase.py`**

Add to the imports near the top:

```python
from datetime import date, time, timedelta
```

(Replace the existing `from datetime import time` line.)

Then append to the file:

```python
def current_week_range(*, today: date | None = None) -> tuple[date, date]:
    """Return (Monday, Friday) of the ISO calendar week containing `today`.

    Sat/Sun resolve to the week that just ended (the most recent Mon-Fri).
    If `today` is omitted, uses `date.today()`. Pass an explicit date in tests.
    """
    if today is None:
        today = date.today()
    # date.weekday(): Monday=0 .. Sunday=6
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 26 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add current_week_range: Mon-Fri of ISO week, weekends resolve back"
```

---

## Task 6: CLI argument parser

**Files:**
- Modify: `scripts/sync_to_supabase.py`
- Modify: `tests/test_sync_to_supabase.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_to_supabase.py`:

```python
class TestParseArgs(unittest.TestCase):
    def test_no_args_returns_defaults(self):
        args = s.parse_args([])
        self.assertIsNone(args.from_date)
        self.assertIsNone(args.to_date)
        self.assertEqual(args.cohorts, "1,2,3,4")
        self.assertIsNone(args.input)
        self.assertFalse(args.dry_run)

    def test_date_range(self):
        args = s.parse_args(["--from", "2026-05-18", "--to", "2026-05-22"])
        self.assertEqual(args.from_date, "2026-05-18")
        self.assertEqual(args.to_date, "2026-05-22")

    def test_cohorts_subset(self):
        args = s.parse_args(["--cohorts", "1,3"])
        self.assertEqual(args.cohorts, "1,3")

    def test_input_path(self):
        args = s.parse_args(["--input", "/tmp/shifts.json"])
        self.assertEqual(args.input, "/tmp/shifts.json")

    def test_dry_run(self):
        args = s.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)

    def test_from_without_to_errors(self):
        with self.assertRaises(SystemExit):
            s.parse_args(["--from", "2026-05-18"])

    def test_to_without_from_errors(self):
        with self.assertRaises(SystemExit):
            s.parse_args(["--to", "2026-05-22"])
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_sync_to_supabase.TestParseArgs -v
```

Expected: `AttributeError: module 'sync_to_supabase' has no attribute 'parse_args'`.

- [ ] **Step 3: Add `parse_args` to `scripts/sync_to_supabase.py`**

Add to the imports:

```python
import argparse
```

Append:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse sync_to_supabase.py CLI args.

    `--from` and `--to` are independent of the Humanity agent's `--from`/`--to`
    even though they have the same names; the sync forwards them when calling
    the agent.
    """
    p = argparse.ArgumentParser(description="Sync Humanity shifts into Supabase.")
    p.add_argument("--from", dest="from_date",
                   help="Inclusive range start (YYYY-MM-DD). Must be paired with --to.")
    p.add_argument("--to", dest="to_date",
                   help="Inclusive range end (YYYY-MM-DD). Must be paired with --from.")
    p.add_argument("--cohorts", default="1,2,3,4",
                   help="Comma-separated cohort numbers. Default: 1,2,3,4.")
    p.add_argument("--input",
                   help="Path to a pre-fetched workflow JSON. Skips the Humanity call.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print rows that would be upserted; make no Supabase call.")
    args = p.parse_args(argv)
    if bool(args.from_date) ^ bool(args.to_date):
        p.error("--from and --to must be provided together")
    return args
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 33 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add CLI argument parser with from/to pairing validation"
```

---

## Task 7: Humanity workflow subprocess invocation

**Files:**
- Modify: `scripts/sync_to_supabase.py`
- Modify: `tests/test_sync_to_supabase.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_to_supabase.py`:

```python
import json
import tempfile
from unittest.mock import patch, MagicMock


class TestRunHumanityWorkflow(unittest.TestCase):
    def test_calls_subprocess_with_expected_args(self):
        fake_stdout = "/tmp/fake-shifts.json\n"
        with patch.object(s.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_stdout, returncode=0)
            path = s.run_humanity_workflow(
                from_date="2026-05-18", to_date="2026-05-22", cohorts="1,2,3,4"
            )
        self.assertEqual(path, "/tmp/fake-shifts.json")
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn("--workflow", cmd)
        self.assertIn("--from", cmd)
        self.assertIn("2026-05-18", cmd)
        self.assertIn("--to", cmd)
        self.assertIn("2026-05-22", cmd)
        self.assertIn("--cohorts", cmd)
        self.assertIn("1,2,3,4", cmd)

    def test_nonzero_exit_raises(self):
        with patch.object(s.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=1, stderr="boom")
            with self.assertRaises(SystemExit):
                s.run_humanity_workflow(
                    from_date="2026-05-18", to_date="2026-05-22", cohorts="1"
                )

    def test_load_workflow_json_reads_file(self):
        sample = [{"date": "2026-05-18", "class_id": 918}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            path = f.name
        loaded = s.load_workflow_json(path)
        self.assertEqual(loaded, sample)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_sync_to_supabase.TestRunHumanityWorkflow -v
```

Expected: `AttributeError: module 'sync_to_supabase' has no attribute 'run_humanity_workflow'`.

- [ ] **Step 3: Add `run_humanity_workflow` and `load_workflow_json` to `scripts/sync_to_supabase.py`**

Add to the imports:

```python
import json
import os
import subprocess
import sys
```

Append:

```python
# Path to the Humanity skill's bundled CLI + venv interpreter.
HUMANITY_PY = os.path.expanduser("~/.claude/skills/matc-humanity/.venv/bin/python")
HUMANITY_AGENT = os.path.expanduser("~/.claude/skills/matc-humanity/humanity_agent.py")


def run_humanity_workflow(*, from_date: str, to_date: str, cohorts: str) -> str:
    """Shell out to humanity_agent.py --workflow and return the output JSON path.

    The agent prints only the file path to stdout in --workflow mode.
    On non-zero exit, prints stderr and aborts the sync (likely a 401 token
    expiry; the agent's own message tells the user how to refresh).
    """
    cmd = [
        HUMANITY_PY, HUMANITY_AGENT,
        "--workflow",
        "--from", from_date,
        "--to", to_date,
        "--cohorts", cohorts,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "humanity_agent.py failed with no stderr.\n")
        sys.exit(1)
    return result.stdout.strip()


def load_workflow_json(path: str) -> list[dict]:
    """Read a Humanity workflow JSON file; expected to be a list of shifts."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of shifts in {path}, got {type(data).__name__}")
    return data
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 36 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add Humanity workflow subprocess + JSON loader"
```

---

## Task 8: Supabase upsert (HTTP POST)

**Files:**
- Modify: `scripts/sync_to_supabase.py`
- Modify: `tests/test_sync_to_supabase.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sync_to_supabase.py`:

```python
class TestUpsertToSupabase(unittest.TestCase):
    SAMPLE_ROWS = [
        {
            "shift_date": "2026-05-18", "am_pm": "pm", "cohort_number": 3,
            "class_id": 918, "start_time": "13:00:00", "end_time": "16:55:00",
            "title": None, "instructors": [{"name": "Dean, John", "role": "Lead"}],
            "cohort_lead_last_name": "Dean",
        }
    ]

    def test_posts_to_correct_url(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        args, kwargs = mock_post.call_args
        self.assertEqual(
            args[0],
            "https://abc.supabase.co/rest/v1/shifts"
            "?on_conflict=shift_date,cohort_number,start_time",
        )

    def test_sends_correct_headers(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        _, kwargs = mock_post.call_args
        headers = kwargs["headers"]
        self.assertEqual(headers["apikey"], "svc-xyz")
        self.assertEqual(headers["Authorization"], "Bearer svc-xyz")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertIn("resolution=merge-duplicates", headers["Prefer"])

    def test_sends_rows_as_json(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], self.SAMPLE_ROWS)

    def test_4xx_raises_systemexit(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400, text='{"message":"bad row"}'
            )
            with self.assertRaises(SystemExit):
                s.upsert_to_supabase(
                    self.SAMPLE_ROWS,
                    supabase_url="https://abc.supabase.co",
                    service_key="svc-xyz",
                )

    def test_empty_rows_noop(self):
        with patch.object(s.requests, "post") as mock_post:
            s.upsert_to_supabase(
                [],
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        mock_post.assert_not_called()
```

- [ ] **Step 2: Run it to verify it fails**

```bash
python -m unittest tests.test_sync_to_supabase.TestUpsertToSupabase -v
```

Expected: `AttributeError: module 'sync_to_supabase' has no attribute 'upsert_to_supabase'`.

- [ ] **Step 3: Add `upsert_to_supabase` to `scripts/sync_to_supabase.py`**

Add to the imports:

```python
import requests
```

Append:

```python
def upsert_to_supabase(rows: list[dict], *, supabase_url: str, service_key: str) -> None:
    """POST rows to Supabase PostgREST as an upsert keyed on the unique index.

    No-op when rows is empty. On 4xx/5xx, prints the response body and exits 2.
    """
    if not rows:
        return
    url = (
        f"{supabase_url.rstrip('/')}/rest/v1/shifts"
        "?on_conflict=shift_date,cohort_number,start_time"
    )
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    resp = requests.post(url, headers=headers, json=rows)
    if resp.status_code >= 400:
        sys.stderr.write(f"Supabase {resp.status_code}: {resp.text}\n")
        sys.exit(2)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m unittest tests.test_sync_to_supabase -v
```

Expected: 41 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add scripts/sync_to_supabase.py tests/test_sync_to_supabase.py
git commit -m "Add Supabase PostgREST upsert with auth headers + error handling"
```

---

## Task 9: `main()` orchestration + manual smoke test

**Files:**
- Modify: `scripts/sync_to_supabase.py`

This task has no unit test — `main()` is thin glue and we've already tested all the pieces it calls. Instead, the verification step is a manual end-to-end run against a real Supabase project.

- [ ] **Step 1: Add `dotenv` import + `main()` to `scripts/sync_to_supabase.py`**

Add to the imports:

```python
from dotenv import load_dotenv
```

Append (and add the standard `__main__` entry point):

```python
def _read_secrets() -> tuple[str, str]:
    """Load .env and return (SUPABASE_URL, SUPABASE_SERVICE_KEY). Exits if missing."""
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url:
        sys.stderr.write("Missing SUPABASE_URL in .env\n")
        sys.exit(3)
    if not key:
        sys.stderr.write("Missing SUPABASE_SERVICE_KEY in .env\n")
        sys.exit(3)
    return url, key


def main(argv: list[str] | None = None) -> None:
    from class_titles import CLASS_TITLES

    args = parse_args(argv)

    # Resolve date range.
    if args.from_date:
        from_date, to_date = args.from_date, args.to_date
    else:
        mon, fri = current_week_range()
        from_date, to_date = mon.isoformat(), fri.isoformat()

    # Get workflow JSON.
    if args.input:
        json_path = args.input
    else:
        json_path = run_humanity_workflow(
            from_date=from_date, to_date=to_date, cohorts=args.cohorts
        )
    shifts = load_workflow_json(json_path)

    # Normalize.
    rows: list[dict] = []
    missing_titles: set[int] = set()
    for shift in shifts:
        rows.append(normalize_shift(shift, class_titles=CLASS_TITLES))
        if shift["class_id"] not in CLASS_TITLES or not CLASS_TITLES[shift["class_id"]]:
            missing_titles.add(shift["class_id"])

    # Report per-shift.
    for r in rows:
        n_inst = len(r["instructors"])
        print(
            f"{r['shift_date']} {r['am_pm'].upper():2} "
            f"C{r['cohort_number']} #{r['class_id']} — "
            f"{n_inst} instructor{'s' if n_inst != 1 else ''}"
        )

    if missing_titles:
        sys.stderr.write(
            f"warning: class_ids without titles in CLASS_TITLES: "
            f"{sorted(missing_titles)} (stored as NULL)\n"
        )

    if args.dry_run:
        print(f"\nDRY RUN — would upsert {len(rows)} rows. Nothing sent.")
        return

    supabase_url, service_key = _read_secrets()
    upsert_to_supabase(rows, supabase_url=supabase_url, service_key=service_key)
    print(f"\nUpserted {len(rows)} shifts into Supabase.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Confirm the full test suite still passes**

```bash
python -m unittest discover -s tests -v
```

Expected: 44 tests pass — 41 in `test_sync_to_supabase.py` plus 3 in `test_class_titles.py`. No new automated tests in this task.

- [ ] **Step 3: Dry-run with a real Humanity workflow file**

Use an existing file the matc-humanity skill already wrote:

```bash
~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py \
  --input ~/.claude/skills/matc-humanity/output/shifts_2026-05-18_to_2026-05-22_cohorts1-3.json \
  --dry-run
```

Expected output: one line per shift like `2026-05-19 AM C3 #918 — 3 instructors`, followed by `DRY RUN — would upsert N rows.` and probably a `warning: class_ids without titles ...` line (because `class_titles.py` currently has empty stubs for everything but 913).

- [ ] **Step 4: Run the schema SQL in Supabase**

Open the Supabase dashboard for project `tapgnqgbszyhrkjsjmrg` → SQL Editor → paste the contents of `sql/001_shifts.sql` → run. Confirm the `shifts` table exists with the expected columns (Table Editor → `shifts`).

- [ ] **Step 5: Create `.env` with real credentials**

```bash
cp .env.example .env
# Edit .env and paste the service_role key from Supabase project settings.
```

Confirm `.env` is gitignored: `git status` should not list it.

- [ ] **Step 6: Live end-to-end sync**

```bash
~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py \
  --from 2026-05-18 --to 2026-05-22 --cohorts 1,3
```

Expected: per-shift output lines, then `Upserted N shifts into Supabase.`

- [ ] **Step 7: Verify rows in Supabase**

In the Supabase dashboard → Table Editor → `shifts`. Confirm rows are present for the date range, with `instructors` showing as a JSON array with `role` set.

- [ ] **Step 8: Verify idempotency — re-run the same sync**

```bash
~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py \
  --from 2026-05-18 --to 2026-05-22 --cohorts 1,3
```

Open the Supabase table again; row count should be unchanged. `synced_at` should bump to the current timestamp but `id` values should be stable. (You can confirm by sorting the table by `id` and comparing before/after.)

- [ ] **Step 9: Verify the anon key can SELECT but not write**

In the Supabase SQL editor, run:

```sql
-- as anon (use the API tab, or run from the browser console with the anon key)
select count(*) from shifts;  -- should succeed
insert into shifts (shift_date, am_pm, cohort_number, class_id, start_time, end_time)
  values ('2026-01-01','am',1,999,'08:00','12:00');  -- should fail with RLS error
```

- [ ] **Step 10: Commit**

```bash
git add scripts/sync_to_supabase.py
git commit -m "Wire main(): load .env, dispatch sync, report results"
```

---

## Task 10: Fill in known class titles (optional cleanup)

This is a one-line edit per known class. Out of scope if the user doesn't have the titles handy — leaving placeholders is fine and was anticipated by the design.

- [ ] **Step 1: Edit `scripts/class_titles.py`**

For each `class_id` whose title the user knows, replace `""` with the real title (e.g. `913: "Adv. Patient Assessment"` is already filled in as an example).

- [ ] **Step 2: Re-run the sync to push new titles**

```bash
~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py
```

Existing rows will have their `title` column updated in place (it's an upsert).

- [ ] **Step 3: Commit**

```bash
git add scripts/class_titles.py
git commit -m "Fill in class_id titles"
```

---

## Out of Scope (Reminder)

The following are deliberately excluded and have their own future specs:

- Frontend rewrite of `index.html` to read from `shifts` and render the card-based UI from `matc lab index/`.
- A `scenarios` sub-table and the activity-sheet → scenarios sync.
- Populating the `type` and `room` columns (currently nullable, always NULL in v1).
- Scheduled/automated sync (cron, GitHub Actions, Supabase Edge Function).
- Roles beyond Lead/Assist (Examiner, Preceptor, etc.).

The homepage rewrite (since completed) reads from this table with the anon key baked into `index.html` — see `data.js`.
