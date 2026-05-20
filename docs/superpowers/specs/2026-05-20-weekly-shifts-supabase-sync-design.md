# Weekly Shifts → Supabase Sync (v1)

**Status:** Draft for review
**Date:** 2026-05-20
**Scope:** Data pipeline only. The Vercel `index.html` rewrite that reads from this table is a separate later task.

## Goal

The `matc-ems-site` homepage (hosted on Vercel) should display the current week's EMS lab shifts — date, AM/PM, cohort, class number, instructors — pulled from a Supabase `shifts` table. This spec covers how shift data gets *into* that table.

## Architecture

```
Humanity API
   │  humanity_agent.py --workflow --from <Mon> --to <Fri> --cohorts 1,2,3,4
   ▼
shifts_<dates>_cohorts*.json   (in ~/.claude/skills/matc-humanity/output/)
   │
   ▼
scripts/sync_to_supabase.py    (new, in this repo)
   │  • reads workflow JSON
   │  • enriches each shift via CLASS_TITLES lookup → title
   │  • derives am_pm from start_time, instructor roles from cohort_lead
   │  • upserts each row into the shifts table
   ▼
Supabase  (project: tapgnqgbszyhrkjsjmrg)
   │  PostgREST  shifts table, public SELECT via anon key
   ▼
matc-ems-site/index.html  (rewrite — separate task, out of scope here)
```

The Humanity skill is **not modified**. It already produces the JSON we need via `--workflow`. The new code is entirely in this repo.

## Files added to this repo

```
matc-ems-site/
├── docs/superpowers/specs/2026-05-20-weekly-shifts-supabase-sync-design.md   ← this file
├── scripts/
│   ├── sync_to_supabase.py     ← sync logic + CLI
│   └── class_titles.py         ← editable class_id → title map
├── sql/
│   └── 001_shifts.sql          ← table + RLS, idempotent (CREATE IF NOT EXISTS)
├── .env.example                ← template for SUPABASE_URL / SUPABASE_SERVICE_KEY
└── .gitignore                  ← add `.env`
```

No changes to `index.html`, `style.css`, or `matc lab index/` in this spec.

## Supabase schema

`sql/001_shifts.sql`:

```sql
create table if not exists shifts (
  id                    bigserial primary key,
  shift_date            date    not null,
  am_pm                 text    not null check (am_pm in ('am','pm')),
  cohort_number         int     not null check (cohort_number between 1 and 4),
  class_id              int     not null,
  start_time            time    not null,
  end_time              time    not null,
  title                 text,                                       -- from CLASS_TITLES; nullable
  type                  text    check (type is null or type in
                          ('scenario','lecture','skills','clinical','exam')),
  room                  text,                                       -- reserved for v2; always NULL in v1
  instructors           jsonb   not null default '[]'::jsonb,       -- [{name, role}]
  cohort_lead_last_name text,
  synced_at             timestamptz not null default now(),
  unique (shift_date, cohort_number, start_time)
);

create index if not exists shifts_date_idx on shifts (shift_date);

alter table shifts enable row level security;

drop policy if exists "public read" on shifts;
create policy "public read" on shifts for select using (true);
```

**Notes:**

- `type` and `room` are reserved for v2 (they drive pill colors and the room label in the reference UI). The v1 sync writes `NULL` to both.
- `instructors` is JSONB so it can grow to `[{name, role, links: [...]}]` later without a migration.
- Unique key is `(shift_date, cohort_number, start_time)` — finer than `am_pm`, so an edge case where a cohort has two AM shifts on the same day still upserts cleanly.
- RLS is on with a `public read` policy. Anon key from the browser can SELECT but not write. Writes from the sync script use the service-role key, which bypasses RLS.

## `scripts/class_titles.py`

The only file an instructor edits to relabel a class.

```python
# class_id (int) → human-readable shift title (str)
# Edit this dict when you want to change what the homepage shows for a class.
# Leave a value as "" if you don't have a title yet; the sync script will
# store NULL for that class and the homepage will fall back to "EMS-<id>".

CLASS_TITLES: dict[int, str] = {
    912: "",
    913: "Adv. Patient Assessment",
    914: "",
    915: "",
    916: "",
    # 917 intentionally absent (skipped class)
    918: "",
    919: "",
    920: "",
    921: "",
}
```

Stubs are intentional — they get filled in by hand. Empty strings normalize to `NULL` in the sync.

## `scripts/sync_to_supabase.py`

**Interpreter:** Reuses the matc-humanity venv to keep dependencies in one place.

```
~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py [options]
```

That venv already has `requests` and `python-dotenv`. The sync uses `requests` to call Supabase's PostgREST endpoint directly — no new dependency needed.

**CLI:**

```
sync_to_supabase.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                    [--cohorts 1,2,3,4]
                    [--input path/to/shifts.json]
                    [--dry-run]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--from` / `--to` | current Mon–Fri (computed from local date) | Inclusive date range. Both required together if either is given. |
| `--cohorts` | `1,2,3,4` | Comma-separated cohort numbers. |
| `--input` | none (calls Humanity) | Skip the Humanity fetch and use a pre-fetched workflow JSON file instead. Useful for re-running without burning the bearer token. |
| `--dry-run` | off | Print what would be upserted; make no Supabase call. |

**Flow:**

1. **Resolve date range.** If `--from`/`--to` omitted, compute Monday and Friday of the ISO calendar week containing `date.today()` (so Saturday and Sunday resolve to the week that just ended; for next week, pass `--from`/`--to` explicitly).
2. **Get workflow JSON.**
   - With `--input`: read that file.
   - Without: subprocess
     ```
     humanity_agent.py --workflow --date today \
       --from <Mon> --to <Fri> \
       --cohorts 1,2,3,4
     ```
     `--date today` is required by the agent's argparse even though `--from`/`--to` override the range. Capture the file path from stdout and read the JSON it points to.
3. **Build rows.** For each shift in the JSON, build a dict:
   ```python
   def normalize(shift):
       start = parse_time(shift["starting_time"])   # "08:00AM" -> "08:00:00"
       end   = parse_time(shift["ending_time"])
       am_pm = "am" if start_hour(start) < 12 else "pm"
       title = CLASS_TITLES.get(shift["class_id"], "") or None
       lead_last = shift["cohort_lead_last_name"]
       instructors = [
           {
               "name": i["name"],
               "role": "Lead" if last_name(i["name"]) == lead_last else "Assist",
           }
           for i in shift["instructors"]
       ]
       return {
           "shift_date": shift["date"],
           "am_pm": am_pm,
           "cohort_number": shift["cohort_number"],
           "class_id": shift["class_id"],
           "start_time": start,
           "end_time": end,
           "title": title,
           "instructors": instructors,
           "cohort_lead_last_name": lead_last,
       }
   ```
   - `last_name(name)`: Humanity returns `"Last, First"` → split on `", "` and take `[0]`. Names that don't follow that pattern fall through to `Assist`.
   - `type` and `room` are not set (default `NULL`).
4. **Upsert.** One POST per batch of rows:
   ```
   POST {SUPABASE_URL}/rest/v1/shifts?on_conflict=shift_date,cohort_number,start_time
   apikey: <SERVICE_KEY>
   Authorization: Bearer <SERVICE_KEY>
   Content-Type: application/json
   Prefer: resolution=merge-duplicates,return=representation
   Body: [row, row, ...]
   ```
   PostgREST treats this as an UPSERT keyed on the unique constraint.
5. **Report.** Print one line per shift: `Mon 2026-05-18 AM C3 #918 — synced (3 instructors)`. End with `N shifts synced, M skipped (no class match)`.

**Secrets:** Read from `.env` at the repo root via `dotenv.load_dotenv()`:
```
SUPABASE_URL=https://tapgnqgbszyhrkjsjmrg.supabase.co
SUPABASE_SERVICE_KEY=...
```
`.env.example` is committed with placeholders. `.env` is gitignored.

**Error handling:**

| Condition | Behaviour |
|---|---|
| Humanity returns 401 (expired token) | Print the same refresh instructions the agent prints; exit 1. |
| `class_id` missing from `CLASS_TITLES` | Warn to stderr, write row with `title=NULL`. Don't fail. |
| Instructor name doesn't match `Last, First` | Warn to stderr, default role to `Assist`. |
| Supabase 4xx/5xx | Print response body, exit 2. |
| `.env` missing required vars | Print which var is missing, exit 3. |

## Out of scope for v1

The following are deliberately *not* in this spec. Each can be added without rewriting v1:

- **Scenarios sub-table.** v2 will add `scenarios (shift_id FK, title, href, assigned_to, ord)` and the sync script will read them from the Cohort 3 activity sheet / lesson-plan output.
- **`type` and `room` population.** Columns exist but are unused. v2 can extend `CLASS_TITLES` into `CLASS_INFO` with `{title, type, room}` per id.
- **Frontend rewrite.** `index.html` currently queries the wrong table (`weekly_tasks`). Until that file is rewritten, the live Vercel page will keep showing "No tasks found" even after this sync runs successfully — the table will populate, but nothing is yet reading it. The rewrite is its own spec, downstream of this one.
- **Scheduled sync.** Manual `python scripts/sync_to_supabase.py` for now. Cron/GitHub Action can be added once the bearer-token refresh story is worked out.
- **Multiple instructor roles beyond Lead/Assist.** No "Examiner", "Preceptor" derivation yet — those exist in the reference UI but require info Humanity doesn't expose.

## Open items (for the user to do, not blocking the spec)

- Fill in the real titles in `scripts/class_titles.py` after the file is created. The sync will tolerate empty strings until you do.
- Run the SQL in `sql/001_shifts.sql` against the Supabase project (paste into the SQL editor, or use `psql`).
- Add `SUPABASE_SERVICE_KEY` to `.env` (the anon key is fine in the committed `index.html`, but writes need the service role).
- Make sure the Humanity bearer token has been saved on this machine (`humanity_agent.py --set-token "…"`). The sync inherits matc-humanity's auth; if the token is missing or expired the sync exits 1 with the refresh instructions.

## Success criteria

After running `python scripts/sync_to_supabase.py` on a week with known Humanity data:

1. The `shifts` table contains one row per `(shift_date, cohort_number, start_time)` triple from Humanity.
2. Each row's `instructors` JSONB matches Humanity's instructor list, with exactly one `role: "Lead"` per shift (the one whose last name matches `cohort_lead_last_name`).
3. Re-running the script with no data change is idempotent: row count and `id` values stay the same, only `synced_at` updates.
4. A `class_id` not in `CLASS_TITLES` produces a row with `title = NULL` and a stderr warning, not a failure.
5. The Supabase anon key (already present in `index.html`) can `SELECT * FROM shifts` from the browser; it cannot `INSERT`, `UPDATE`, or `DELETE`.
