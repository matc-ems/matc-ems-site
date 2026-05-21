# `/sim-lab` Scenario Index Page

**Status:** Approved
**Date:** 2026-05-21
**Scope:** A new front-end page on `matc-ems-site` plus a generator script. No
change to the `matc-ems/scenarios` repo, its GitHub Pages hosting, or the
scenario-generator pipeline. No database.

## Goal

Add a `/sim-lab` page to `matc-ems-site` that lists the program's sim-lab
training scenarios and lets an instructor click through to any one of them. It
is the unified front door: instructors go to `matc-ems-site` for the schedule,
tools, and now scenarios.

The scenario players themselves already exist and are already hosted — the
`matc-ems/scenarios` repo publishes 64 self-contained interactive scenario
pages via GitHub Pages at `https://matc-ems.github.io/scenarios/`. This page
links out to them; it does not host or duplicate them.

## Why not a database

The scenario players are ~1.6 MB self-contained interactive HTML documents —
static artifacts, generated from each scenario's `unified.json` (the canonical
source of truth) by the scenario-generator skill. A database is the right tool
for small, structured, frequently-queried data that changes often (which is why
`shifts` lives in Supabase); it is the wrong tool for large static documents.
Storing them in Postgres would also require a serving layer to get them back
out — strictly more moving parts than serving a file. Scenarios stay static
files; `/sim-lab` is just an index that links to them.

## Architecture

```
                 scripts/build_sim_lab_index.py
   ../scenarios/sim-lab/<CODE>/unified.json  ──read──▶  sim-lab/scenarios.js
                                                              │
                                                              ▼
   browser ──▶ matc-ems-site /sim-lab  (sim-lab/index.html loads scenarios.js,
                                        renders the grouped list)
                                                              │ click
                                                              ▼
              https://matc-ems.github.io/scenarios/sim-lab/<CODE>/  (new tab)
```

The page is a build-less static page — plain HTML/CSS with a small inline
render script. No React, no Supabase: the scenario list is static data that
changes only when scenarios are added.

## Files added

```
matc-ems-site/
├── sim-lab/
│   ├── index.html        ← the /sim-lab page
│   └── scenarios.js      ← generated data (committed)
└── scripts/
    └── build_sim_lab_index.py   ← regenerates scenarios.js
```

`scenarios.js` is committed — the site is build-less, so what is committed is
what Vercel ships. Vercel does not run the generator.

## `scripts/build_sim_lab_index.py`

Regenerates `sim-lab/scenarios.js` from the scenario source data. Run it
whenever scenarios are added or renamed.

**Interpreter:** plain `python3` — standard library only (`json`, `pathlib`,
`os`, `argparse`). Unlike `sync_to_supabase.py`, it needs no third-party
packages and no virtualenv.

**Input:** the `matc-ems/scenarios` repo checked out as a sibling of
`matc-ems-site` — default `../scenarios` relative to the repo root, overridable
with `--scenarios-dir`. (This mirrors how `sync_to_supabase.py` already depends
on a sibling location, the matc-humanity skill.) It reads every directory under
`<scenarios-dir>/sim-lab/` whose name matches the scenario-code pattern
`<Letter>-T<digit>-<digits>` (e.g. `C-T1-01`).

**Per scenario, it produces an entry:**

| Field | Source |
|-------|--------|
| `code` | the folder name (e.g. `C-T1-01`) — also the URL path component |
| `category` | the leading letter mapped: `B`→Behavioral, `C`→Cardiac, `M`→Medical, `P`→Pediatric, `R`→Respiratory |
| `tier` | the `T<digit>` segment of the code (`T1`, `T2`, `T3`) |
| `name` | `meta.name` from that folder's `unified.json`; falls back to `code` if missing or empty |
| `url` | `https://matc-ems.github.io/scenarios/sim-lab/<code>/` |

Category and tier are derived from the **folder code**, not from `unified.json`
— the code is the authoritative, always-present identifier and the URL path.
Only `meta.name` is read from the JSON, so a malformed `unified.json` degrades
to the code as the display name (with a stderr warning) rather than failing the
build.

**Output:** `sim-lab/scenarios.js`, a single assignment:

```js
window.SIM_LAB_SCENARIOS = [
  { code: "B-T1-01", category: "Behavioral", tier: "T1", name: "…",
    url: "https://matc-ems.github.io/scenarios/sim-lab/B-T1-01/" },
  …
];
```

Entries are sorted by category (Behavioral, Cardiac, Medical, Pediatric,
Respiratory), then tier (T1, T2, T3), then code.

**Structure:** pure helpers (code parsing, category mapping, building one
entry) separated from the I/O shell (directory scan, file read, file write),
so the helpers are unit-testable — the same split as `sync_to_supabase.py`.

## `sim-lab/index.html`

A plain HTML/CSS page, no JavaScript framework. It loads `shared/tokens.css`
for the shared design system and matches the branded header of the student and
instructor hubs (the `+` badge, the "MATC Paramedic Lab" kicker, page name
"Sim Lab").

- Loads the data with `<script src="/sim-lab/scenarios.js"></script>`.
- A small inline `<script>` reads `window.SIM_LAB_SCENARIOS`, groups entries by
  category and then tier, and renders the grouped list.
- Each scenario is a clickable row showing its `code` and `name`. The link is
  `<a href="{url}" target="_blank" rel="noopener">` — it opens the GitHub Pages
  player in a new tab, leaving `/sim-lab` open.
- If `SIM_LAB_SCENARIOS` is missing or empty, the page shows a plain empty
  state instead of a broken list.

**Path correctness:** every local resource reference is root-absolute
(`/shared/tokens.css`, `/sim-lab/scenarios.js`). Vercel serves `/sim-lab`
without a trailing slash, so relative paths would resolve against the site root
and 404 — the same failure fixed earlier on `/instructors`.

## Out of scope

- **`main-lab` scenarios.** This page covers the 64 `sim-lab/` scenarios only.
- **Filtering / search.** The list is grouped and browsable; no search box.
- **Cross-navigation.** `/sim-lab` is reachable directly by URL; no links to it
  are added from `/`, `/instructors`, or elsewhere yet.
- **Hosting the scenario players on `matc-ems-site`.** They remain in the
  `scenarios` repo on GitHub Pages.
- **Changes to the `scenarios` repo or the scenario-generator skill.**

## Verification & success criteria

1. With the `scenarios` repo checked out as a sibling, running
   `python3 scripts/build_sim_lab_index.py` writes `sim-lab/scenarios.js`
   containing one entry per `sim-lab/` scenario (64 today), each with a correct
   `matc-ems.github.io` URL.
2. Served locally (`python3 -m http.server` from the repo root), `/sim-lab`
   renders the scenarios grouped by category and tier; each row links to the
   right player URL and opens in a new tab.
3. `tests/test_frontend_paths.py` is extended to cover `sim-lab/index.html` and
   passes — every local resource path is root-absolute.
4. The generator's pure helpers have unit tests in `tests/`; the full suite
   passes.
5. Browser check: the page is styled consistently with the student and
   instructor hubs, and scenario links open the correct interactive players.
