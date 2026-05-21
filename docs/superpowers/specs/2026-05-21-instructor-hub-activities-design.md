# Instructor Hub Activities — Design

- **Date:** 2026-05-21
- **Status:** Approved (brainstorming)

## Goal

Today the instructor hub (`/instructors`) shows *who* is working each shift. This
adds *what* each shift does — the lab activity materials. Each shift card gains:

- **Shared material groups**, above the instructor list — links grouped by
  activity name, for every instructor.
- **Per-instructor scenario assignments** — scenario slugs/links round-robin'd
  across the shift's instructors.

The dormant `D5ScenarioGroup` / `D5InstructorBlock` components in `myday.jsx`
already render exactly this layout; today `data.js` never populates them.

## Data sources

Two sources, joined by the **combined sync script**:

1. **Humanity** (existing) — via `sync_to_supabase.py`: shift date, AM/PM,
   cohort, `class_id`, start/end, instructors. Drives which dates we look up.
2. **"Lesson Plan Material" Google Sheet** (`1aSnWNVMK6ib84AVnvmf9TTlkJCe0i7WxgdKxlD_bmh8`)
   — one tab per cohort: `Cohort 1` … `Cohort 4`.

### Sheet layout (new 14-column format, columns A–N)

| Col | Field | Used |
|-----|-------|------|
| A | date (`MM-DD-YY`) | ✅ match to Humanity date |
| B | day_of_week | — (empty) |
| C | shift | — (empty; AM/PM derived from D) |
| D | start_time (`H:MM`, 24-hour) | ✅ AM/PM split + row ordering |
| E | end_time | — |
| F | duration_min | — (empty) |
| G | activity_type | — (routing is column-based, not type-based) |
| H | activity_id | — (empty) |
| I | activity_title | ✅ shared-group name |
| J | activity_description | — (v1: not rendered) |
| K | scenario_slugs | ✅ → per-instructor pool |
| L | scenario_links | ✅ → per-instructor pool |
| M | pp_skill_links | ✅ → shared |
| N | activity_links | ✅ → shared |

K/L/M/N hold **comma-separated** values. `Cohort 1`'s tab is still the *old*
format (`Class Date, Start Time, End Time, Room, Topic`) and will not parse
against this layout — it yields empty activities until converted (out of scope).

## Schema

`sql/002_activities_column.sql` — idempotent, nothing removed:

```sql
alter table shifts
  add column if not exists activities jsonb not null default '{}'::jsonb;
```

`type` / `room` are left untouched (still dormant). `shifts` already has a
`public read` RLS policy that covers the new column.

## `shifts.activities` shape

Fully resolved at sync time — the frontend renders it directly, no computation:

```json
{
  "perInstructor": {
    "Smith, Scott": [
      {"label": "cardiac-aortic-dissection-001",
       "href": "https://matc-ems.github.io/scenarios/main-lab/cardiac-aortic-dissection-001"}
    ],
    "Jones, Amy": [
      {"label": "AHA Megacode 3", "href": "https://docs.google.com/document/d/..."}
    ]
  },
  "shared": [
    {"name": "Class Expectations Presentation",
     "links": [{"label": "Class Expectations", "href": "https://docs.google.com/presentation/d/..."}]}
  ]
}
```

A shift with no matching sheet rows stores `{"perInstructor": {}, "shared": []}`.
The column default `'{}'` covers rows the sync never touches.

## Routing rules

Scope: one shift = one cohort tab, one date, one AM/PM block. A block is the set
of that date's rows whose `start_time` is before noon (AM) or noon-or-later (PM).

### Per-instructor pool

Gather, in row order (sorted by `start_time`), each row's `scenario_slugs` then
`scenario_links`:

- slug → `{label: slug, href: "https://matc-ems.github.io/scenarios/main-lab/" + slug}`
- link → `{label: <resolved Doc title>, href: link}`

Round-robin across the shift's instructors (in Humanity order):

- `I` = instructor count, `N` = pool size, `per = N // I`.
- Items `0 .. per*I - 1` are dealt round-robin: item `k` → instructor `k % I`,
  so instructor `i` receives items `i, i+I, i+2I, …` — its list is
  `[pool[i], pool[i+I], …]` (length `per`).
- The trailing `N - per*I` items are **dropped** — keeps every instructor's
  count equal.
- `I == 0` → the whole pool is dropped.

Worked examples (confirmed with the user):

- 6 items, 3 instructors → `per = 2`. I0 = items 0,3 · I1 = 1,4 · I2 = 2,5.
- 6 items, 4 instructors → `per = 1`. I0 = 0 · I1 = 1 · I2 = 2 · I3 = 3.
  Items 4 and 5 are dropped.

### Shared groups

For each row (in `start_time` order) with a non-empty `pp_skill_links` **or**
`activity_links`, emit one group:

```
{"name": <activity_title>, "links": [<pp_skill_links…>, <activity_links…>]}
```

Each link resolves to `{label: <resolved Doc title>, href: url}`. Multiple links
under one activity stay together in that one group. (`activity_type` column G is
not consulted — routing is purely by which column the value is in.)

## Resilience: partial and missing sheet data

A Humanity shift must **always render** — the sheet is supplementary. Every
degraded case below produces a valid shift card showing at least the instructor
list, and never an error:

- **No sheet rows for the date** → `activities = {"perInstructor": {}, "shared": []}`.
  Card renders the flat instructor list, exactly as today.
- **Rows exist but K/L/M/N are all blank** → same: empty pools, flat list.
- **Partially filled rows** → only the non-blank cells contribute. A row with an
  `activity_title` but no links produces no shared group; a row with links but a
  blank title still emits its group (`name: ""`, rendered without a heading).
  Blank cells are skipped, never an error.
- **Mixed** — a shift may have shared groups but no per-instructor items, or vice
  versa. Whatever is present renders; the instructor names always appear.
- **Unparseable row** (bad date or `start_time`) → that single row is skipped
  with a stderr warning; the shift's other rows still process. `build_activities`
  never raises on row-level data.
- **Old-format or missing cohort tab** → warn, empty activities for that cohort.
- **`gws` auth failure** → the one hard stop (see Failure handling) — a systemic
  problem, not partial data.

Frontend: `D5ShiftCard` always lists every instructor. Shared groups render when
present; per-instructor scenarios render under their instructor when present;
with neither, the card is the flat list. No card state hides an instructor or
shows an error.

## Components

### `scripts/sheet_activities.py` (new — own copy of the sheet pull)

Pure, unit-tested helpers plus a thin `gws` I/O shell — the same split as
`sync_to_supabase.py`. This is a deliberate own copy of logic that overlaps the
`matc-lesson-plan` skill's `pull_activity_data.py`, so the site pipeline is
self-contained and testable on its own.

- `gws_get_values(tab) -> list[list[str]]` — I/O shell; reads `'Cohort N'!A1:N1000`.
- `resolve_doc_title(url) -> str` — I/O shell; best-effort `gws drive files get`,
  falls back to the URL on any failure.
- `parse_sheet_date("01-21-26") -> date` — `MM-DD-YY`, lenient on leading zeros.
- `parse_clock("13:00") -> time` — 24-hour `H:MM`.
- `derive_am_pm(time) -> "am" | "pm"`.
- `split_cell(cell) -> list[str]` — comma-split, trim, drop empties.
- `round_robin(pool, n_instructors) -> list[list]` — the algorithm above.
- `is_new_format(header_row) -> bool` — guards against the old `Cohort 1` layout.
- `build_activities(rows, date, am_pm, instructors) -> dict` — assembles the full
  `{perInstructor, shared}` blob. Pure: takes already-fetched rows. Best-effort
  per row — skips rows it cannot parse (bad date/time) instead of raising; blank
  cells contribute nothing.

Constants: `SPREADSHEET_ID`, `SLUG_BASE_URL`. Tab name = `f"Cohort {n}"`.

### `scripts/sync_to_supabase.py` (extended)

After normalizing Humanity shifts:

1. Fetch each needed cohort tab **once** and cache it (`{cohort_number: rows}`),
   lazily — only cohorts present in the Humanity result.
2. For each shift row, call `build_activities(...)` with that shift's date,
   AM/PM, and instructor list → attach the `activities` blob.
3. Upsert, now including the `activities` column.

Failure handling:

- A `gws` failure (missing/expired auth) **aborts** the sync with a clear
  `gws auth login` message. Silently writing empty activities to every shift
  would be worse than a hard stop.
- An old-format or missing cohort tab is **not** a failure: warn to stderr,
  that cohort's shifts get `{"perInstructor": {}, "shared": []}`.
- `--dry-run` prints an activities summary per shift.
- New flag `--skip-activities` runs the Humanity-only sync (no sheet, no `gws`)
  — preserves the existing offline `--input` workflow and eases testing.

The sync now depends on **both** the matc-humanity venv (`requests`,
`python-dotenv`) **and** the `gws` CLI on PATH — to be documented in `CLAUDE.md`.

### Frontend

- `instructors/data.js` — `shiftFromRow` adds an `activities` field, normalized
  to the full shape so consumers never see missing keys:
  `{perInstructor: row.activities?.perInstructor ?? {}, shared: row.activities?.shared ?? []}`
  (the column default `'{}'` means an untouched row arrives as `{}`, not null).
  Delete the now-unused `PD.scenariosByInstructor` helper; update the
  shape-contract comment in the file header.
- `instructors/myday.jsx` — `D5ShiftCard` reads `shift.activities`:
  - render one `D5ScenarioGroup` per `shared[]` entry (label = `name`) above the
    instructor list;
  - render one `D5InstructorBlock` per instructor, scenarios = `perInstructor[name]`
    (or `[]`);
  - when `activities` has no `shared` entries and no `perInstructor` keys, fall
    back to the current flat instructor list.
  - `D5ScenarioGroup` / `D5InstructorBlock` switch from `s.title` to `s.label`.
  - The dead `shift.link` branch is removed.

The instructor hub reads Supabase live, so writing the `activities` column *is*
updating the site — there is no generated file (unlike sim-lab's `scenarios.js`).

## Tests

- `tests/test_sheet_activities.py` (new) — date/time parsing, `split_cell`,
  `round_robin` (including the 6/3 and 6/4 cases above), `is_new_format`, and
  `build_activities` end-to-end on fixture rows — including a partially-filled
  shift (blank link columns, blank title), an all-blank shift, and an
  unparseable row that is skipped without raising.
- `tests/test_sync_to_supabase.py` (extended) — the activities merge: matching
  sheet rows by date + AM/PM, cohort-tab caching, empty result for an
  old-format tab.

Pure helpers are tested without `gws`; `gws_get_values` / `resolve_doc_title`
are the I/O seams left untested (mirrors `run_humanity_workflow`).

## Out of scope (future)

- Converting `Cohort 1`'s tab to the new 14-column layout (a sheet edit).
- Rendering `activity_description` (column J) on the hub.
- The catalog model (a dateless curriculum plus per-cohort date mapping)
  discussed during brainstorming — deferred. Storing `activities` on the shift
  row is forward-compatible: it is the resolved per-shift output either way.
