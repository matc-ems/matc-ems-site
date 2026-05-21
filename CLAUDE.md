# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The MATC EMS Department site — a build-less static site with three front-end
pages plus a Python data pipeline:

- **Student hub** (`index.html`, served at `/`) — a plain HTML/CSS landing
  page. A navigation hub that will link out to student tools under
  `/tools/<name>` as they are built.
- **Instructor hub** (`instructors/`, served at `/instructors`) — a React page
  showing the current week's EMS lab shifts (date, AM/PM, cohort, class,
  instructors), read from a Supabase `shifts` table.
- **Sim Lab** (`sim-lab/`, served at `/sim-lab`) — a plain HTML/CSS page
  listing the EMS simulation scenarios with category/tier filters. The scenario
  players live in a separate repo (`matc-ems/scenarios`); this page links out
  to them.
- **Data pipeline** — Python in `scripts/` that pulls shifts from Humanity.com
  and writes that `shifts` table.

The instructor hub and the pipeline are joined only by the `shifts` table
(`sql/001_shifts.sql`) — the sync writes it with the service key, the browser
reads it with the anon key. `shared/tokens.css` holds the design tokens used by
every page.

## Commands

The sync script and the test suite run on the **matc-humanity skill's
virtualenv**, not system Python — that venv is where `requests` and
`python-dotenv` live. Do not `pip install` into system Python.
`build_sim_lab_index.py` uses only the standard library and runs on plain
`python3`. The sync also shells out to the `gws` CLI to read the activity
sheet; it must be on PATH and authenticated (`gws auth login`). Pass
`--skip-activities` to run the sync without it. Run everything below from the
repo root.

```bash
PY=~/.claude/skills/matc-humanity/.venv/bin/python

# Tests
$PY -m unittest discover -s tests

# A single test class or method
$PY -m unittest tests.test_sync_to_supabase.TestParseTime
$PY -m unittest tests.test_sync_to_supabase.TestParseTime.test_noon

# Run the sync (current Mon–Fri by default)
$PY scripts/sync_to_supabase.py --dry-run          # print rows, no write
$PY scripts/sync_to_supabase.py                    # fetch Humanity + upsert
$PY scripts/sync_to_supabase.py --from 2026-06-01 --to 2026-06-05
$PY scripts/sync_to_supabase.py --input shifts.json   # skip the Humanity call
$PY scripts/sync_to_supabase.py --skip-activities     # shifts only, no sheet/gws

# Regenerate sim-lab/scenarios.js from the sibling matc-ems/scenarios repo
python3 scripts/build_sim_lab_index.py

# Preview the site (needed — file:// breaks Babel's XHR fetch of myday.jsx)
python3 -m http.server 8000      # pages: / · /instructors/ · /sim-lab/
```

Schema changes: paste the files in `sql/` (`001_shifts.sql`, then
`002_activities_column.sql`) into the Supabase SQL editor, in order. They are
idempotent, so re-running is safe.

Deployment: Vercel auto-deploys on push to `main`. There is no build step and no
`package.json` — what is committed is what ships.

## Frontend architecture

No bundler — folders map directly to URL paths on Vercel. `/` serves the root
`index.html` (student hub); `/instructors` serves `instructors/index.html`;
`/sim-lab` serves `sim-lab/index.html`. Future student tools go under
`tools/<name>/index.html`, served at `/tools/<name>`. `shared/tokens.css` is the
design system shared by every page.

Sub-directory pages (`/instructors`, `/sim-lab`, future `/tools/<name>`) must
use **root-absolute** resource paths (`/shared/tokens.css`, not `../shared/…`):
Vercel serves them with no trailing slash, so a relative path resolves against
the site root and 404s. `tests/test_frontend_paths.py` guards this.

**Student hub** (`index.html`) — plain HTML/CSS, no JavaScript framework. A
navigation shell that links out to tools as they are added.

**Instructor hub** (`instructors/`) — `instructors/index.html` pulls React 18,
ReactDOM, `@babel/standalone`, and `supabase-js` from CDNs, then loads its two
sibling files (`data.js`, `myday.jsx`) and `../shared/tokens.css`. Babel
transpiles `myday.jsx` in the browser at load time. Boot sequence:
1. `await window.loadParamedicData()` — defined in `instructors/data.js`.
2. `ReactDOM.createRoot(...).render(<D5MyDay />)` — `D5MyDay` from `instructors/myday.jsx`.

`instructors/data.js` fetches the current week's rows from the Supabase `shifts`
table and assembles `window.PARAMEDIC_DATA` in the exact shape `myday.jsx`
consumes (`schedule[cohortId][dayIdx] = { am, pm }`). The shape contract is
documented in the header comment of `data.js` — keep producer and consumer in
sync.

`instructors/myday.jsx` is a single React component tree (`D5MyDay` →
`D5ShiftCard` → `D5InstructorBlock` / `D5ScenarioGroup`). All styling is inline
styles plus the CSS custom properties and pill/rail classes defined in
`shared/tokens.css`.

**Sim Lab** (`sim-lab/`) — `sim-lab/index.html` is plain HTML/CSS with a small
inline vanilla-JS script, no framework. It loads `sim-lab/scenarios.js` — a
generated `window.SIM_LAB_SCENARIOS` array — and renders the scenarios grouped
by category and tier, with multi-select filter chips. Each scenario links out,
in a new tab, to its interactive player on the `matc-ems/scenarios` GitHub
Pages site (`https://matc-ems.github.io/scenarios/`).

`sim-lab/scenarios.js` is generated by `scripts/build_sim_lab_index.py`, which
reads each scenario's `unified.json` from the **sibling `matc-ems/scenarios`
repo** (expected checked out at `../scenarios`). Re-run it and commit the
updated `sim-lab/scenarios.js` whenever scenarios are added or renamed. The
scenario player HTML is large and self-contained — it is deliberately hosted in
the `scenarios` repo, not here.

## Data pipeline architecture

`scripts/sync_to_supabase.py` is the sync. Its flow:

1. Resolve a date range (defaults to current Mon–Fri).
2. Subprocess out to `~/.claude/skills/matc-humanity/humanity_agent.py
   --workflow` to fetch shifts from Humanity, **or** read a pre-fetched JSON via
   `--input`.
3. `normalize_shift()` turns each Humanity shift into a `shifts` table row:
   parses 12-hour times, derives `am_pm`, looks up the title in `CLASS_TITLES`,
   and tags each instructor `Lead`/`Assist` by matching last name against
   `cohort_lead_last_name`.
4. Upsert via PostgREST `POST /rest/v1/shifts`, keyed on the unique constraint
   `(shift_date, cohort_number, start_time)`.

The file is split into pure helpers (tested in `tests/`) and an I/O shell
(`main`, `run_humanity_workflow`, `upsert_to_supabase`, `_read_secrets`). Keep
new logic pure and tested where possible.

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

## Things to know

- **Secrets:** `.env` (gitignored) holds `SUPABASE_URL` and
  `SUPABASE_SERVICE_KEY`. The service key has full write access — never put it in
  the browser. `instructors/data.js` intentionally embeds the **anon** key and URL; that key
  can only `SELECT` (`shifts` has RLS with a `public read` policy).
- **Humanity auth:** the sync inherits the matc-humanity skill's bearer token.
  If it is missing or expired, the sync exits 1 with refresh instructions — this
  is a token problem, not a code bug.
- **Duplicated week logic:** `instructors/data.js` `currentWeekRange()` and
  `sync_to_supabase.py` `current_week_range()` implement the same convention
  (Mon–Fri of the ISO week; weekends resolve back to the just-ended week).
  Change one, change the other.
- **Reserved columns:** `type` and `room` exist in the table but are always
  `NULL` in v1. They are reserved for v2 (pill colors and the room label).
- **Activity data:** `shifts.activities` (JSONB) holds the resolved per-shift
  lab activities — `{perInstructor, shared}` — written by `sync_to_supabase.py`
  from the "Lesson Plan Material" sheet and rendered directly by
  `instructors/myday.jsx`. The sync needs the `gws` CLI authenticated; a `gws`
  failure aborts the run with a re-auth message. `--skip-activities` runs the
  Humanity-only sync.
- **Specs and plans** for past work live in `docs/superpowers/`. The
  weekly-sync design doc there is the authoritative description of v1 scope and
  the deferred v2 items.
