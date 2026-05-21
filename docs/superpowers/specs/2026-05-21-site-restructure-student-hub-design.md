# Site Restructure — Student Hub at `/`, Instructor Hub at `/instructors`

**Status:** Approved
**Date:** 2026-05-21
**Scope:** Frontend file/URL restructure only. No change to the data pipeline
(`scripts/`, `sql/`, `tests/`) or the instructor hub's behavior.

## Goal

`matc-ems-site` currently serves a single page — the instructor hub — at `/`.
Restructure it into a multi-page static site:

- A **student-facing hub** at `/` (a simple shell for now).
- The **instructor hub** moved unchanged to `/instructors`.
- A documented convention for future per-tool pages under `/tools/<name>`.

The student hub is a navigation hub: as student tools are built, each becomes
its own page and the hub links out to it. This spec delivers the restructure and
the hub shell — not the tools themselves.

## Site map

| URL | File | Audience |
|-----|------|----------|
| `/` | `index.html` | Students |
| `/instructors` | `instructors/index.html` | Instructors |
| `/tools/<name>` | `tools/<name>/index.html` *(future, not in this spec)* | Students |

Vercel maps folders to URL paths automatically, so `instructors/index.html` is
served at both `/instructors` and `/instructors/`. No `vercel.json` is needed,
and none is added — the project stays config-free.

## Directory layout

**Before:**

```
matc-ems-site/
├── index.html        ← instructor hub
├── data.js
├── myday.jsx
├── tokens.css
├── scripts/  sql/  tests/  docs/
├── CLAUDE.md
└── .env  .env.example  .gitignore
```

**After:**

```
matc-ems-site/
├── index.html            ← NEW: student hub, served at /
├── shared/
│   └── tokens.css        ← MOVED from root
├── instructors/
│   ├── index.html        ← MOVED from root
│   ├── data.js           ← MOVED from root
│   └── myday.jsx         ← MOVED from root
├── scripts/  sql/  tests/  docs/   ← unchanged
├── CLAUDE.md             ← updated (paths)
└── .env  .env.example  .gitignore  ← unchanged
```

No empty `tools/` directory is created — git does not track empty directories,
and there is no tool yet (YAGNI). The `/tools/<name>/index.html` convention is
documented in `CLAUDE.md`; the folder is created when the first tool is built.

## File moves

All moves use `git mv` to preserve file history:

| From | To |
|------|----|
| `tokens.css` | `shared/tokens.css` |
| `index.html` | `instructors/index.html` |
| `data.js` | `instructors/data.js` |
| `myday.jsx` | `instructors/myday.jsx` |

## Reference updates

Relative `href`/`src` paths resolve against the HTML file's own location, so the
moves require exactly these edits:

- **`instructors/index.html`:** change `<link rel="stylesheet" href="tokens.css">`
  to `<link rel="stylesheet" href="../shared/tokens.css">`. The `data.js` and
  `myday.jsx` `<script src>` tags are unchanged — those files are still siblings.
  The CDN `<script>` tags are unchanged.
- **`instructors/data.js`** and **`instructors/myday.jsx`:** no changes. `data.js`
  contains the Supabase URL/anon key (not a file path); `myday.jsx` references
  CSS classes and custom properties resolved at runtime from the loaded
  stylesheet. Neither has a path dependency.

## The student hub (`index.html`)

A new, plain **HTML + CSS** page at the repo root. Deliberately **no React, no
Babel, no Supabase**: the instructor hub needs React to render live schedule
data, but the student hub is a static list of links, so it stays lightweight.

- Loads `shared/tokens.css` via `<link rel="stylesheet" href="shared/tokens.css">`
  for the shared fonts and warm-neutral palette.
- Page-specific layout lives in an inline `<style>` block, matching how the
  instructor `index.html` is written.
- **Header:** MATC Paramedic Lab branding consistent with the instructor hub's
  treatment (terracotta `+` badge, mono uppercase label), identifying this as
  the student view.
- **Tools section:** a heading plus an empty-state placeholder (e.g. "Tools
  coming soon"), since no tools exist yet. The section is the shell that future
  tool links populate.
- `<title>`: identifies the page as the MATC Paramedic Lab student page.
- **No link to `/instructors`** — the two audiences are separate; instructors
  navigate to `/instructors` directly.

## Documentation update

`CLAUDE.md` is updated to reflect the new structure:

- The file list in the "What this is" section.
- The "Frontend architecture" section — file paths and the two-page layout.
- The local-preview note — `/` serves the student hub, `/instructors/` serves
  the instructor hub.
- A note recording the `/tools/<name>/index.html` convention for future tools.

## Out of scope

- **Actual student tools.** The hub ships with an empty-state placeholder.
- **Creating the `tools/` folder.** Created with the first tool.
- **Any data-pipeline change.** `scripts/`, `sql/`, `tests/` are untouched.
- **Splitting `tokens.css`.** It currently holds both `:root` design tokens and
  instructor-specific component classes (`.pill`, `.rail-c*`, `.scenario-link`).
  The student hub loads the whole file (~3 KB); splitting tokens from
  instructor-component styles is a possible later refinement, not done now.
- **Shared site header / cross-navigation** between the two hubs.

## Verification & success criteria

1. Serve the repo root with `python3 -m http.server`; `http://localhost:8000/`
   renders the student hub, styled via `shared/tokens.css`.
2. `http://localhost:8000/instructors/` renders the instructor hub: `tokens.css`
   resolves via `../shared/`, and the Supabase fetch populates the current
   week's schedule.
3. `git log --follow instructors/index.html` (and the other moved files) shows
   history preserved across the moves.
4. The Python test suite still passes — unaffected by the frontend move, but
   confirms nothing under `scripts/` was disturbed.
5. After deploy, both `/` and `/instructors` resolve on Vercel.
