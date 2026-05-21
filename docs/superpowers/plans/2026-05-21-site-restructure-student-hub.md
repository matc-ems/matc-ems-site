# Site Restructure — Student Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the build-less static site into a student hub at `/` and the existing instructor hub at `/instructors`, with shared design tokens under `shared/`.

**Architecture:** Move the instructor hub and its assets into an `instructors/` folder and the shared stylesheet into `shared/` — on Vercel, folders map directly to URL paths. Add a new plain-HTML student hub at the repo root. No build step, no config files.

**Tech Stack:** Static HTML/CSS, Vercel folder-based routing, git.

**Spec:** `docs/superpowers/specs/2026-05-21-site-restructure-student-hub-design.md`

---

## Before you start

Work on a feature branch, matching the repo's merge-to-`main` convention:

```bash
git checkout -b site-restructure-student-hub
```

All commits below are local. Pushing to `main` triggers a Vercel production deploy, so that is left to the user — do not push.

The local preview server is used for verification throughout. Start it once from the repo root and leave it running:

```bash
python3 -m http.server 8000
```

(Run it in the background. Stop it when the plan is complete.)

---

## Task 1: Move files into `shared/` and `instructors/`

Move the four existing frontend files into folders and fix the one relative path that breaks as a result. After this task, `/instructors` works and `/` is intentionally empty until Task 2.

**Files:**
- Move: `tokens.css` → `shared/tokens.css`
- Move: `index.html` → `instructors/index.html`
- Move: `data.js` → `instructors/data.js`
- Move: `myday.jsx` → `instructors/myday.jsx`
- Modify: `instructors/index.html` (one line — the stylesheet `href`)

- [ ] **Step 1: Move the files with `git mv`**

`git mv` creates the destination directories and preserves file history.

```bash
git mv tokens.css shared/tokens.css
git mv index.html instructors/index.html
git mv data.js instructors/data.js
git mv myday.jsx instructors/myday.jsx
```

- [ ] **Step 2: Verify the new layout**

Run:
```bash
git status --short
ls shared instructors
```
Expected: `git status` shows four renames (`R`). `shared/` contains `tokens.css`; `instructors/` contains `data.js`, `index.html`, `myday.jsx`.

- [ ] **Step 3: Fix the stylesheet path in `instructors/index.html`**

The instructor page now sits one level deep, so its relative reference to the stylesheet must point up and into `shared/`. The `data.js` and `myday.jsx` `<script src>` tags need no change — those files are still siblings.

Change this line:
```html
<link rel="stylesheet" href="tokens.css">
```
to:
```html
<link rel="stylesheet" href="../shared/tokens.css">
```

- [ ] **Step 4: Verify the instructor hub serves correctly**

With `python3 -m http.server 8000` running from the repo root:

```bash
curl -s http://localhost:8000/instructors/ | grep -q 'Instructor Hub' && echo "PAGE OK"
curl -s http://localhost:8000/instructors/ | grep -q '../shared/tokens.css' && echo "CSS PATH OK"
curl -s -o /dev/null -w 'tokens.css HTTP %{http_code}\n' http://localhost:8000/shared/tokens.css
```
Expected: `PAGE OK`, `CSS PATH OK`, and `tokens.css HTTP 200`.

- [ ] **Step 5: Browser check — instructor hub renders fully**

Open `http://localhost:8000/instructors/` in a browser. Expected: the page is styled (warm-neutral palette, correct fonts) and the current week's schedule renders — confirming the Supabase fetch in `data.js` still works and `../shared/tokens.css` resolved.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
Move instructor hub into /instructors, tokens.css into /shared

git mv preserves history. instructors/index.html now references
../shared/tokens.css; data.js and myday.jsx are unchanged siblings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Create the student hub at the repo root

Add a new `index.html` at the repo root — a plain HTML/CSS page with no JavaScript framework. It is a navigation shell: branded header plus a "Tools" section with an empty-state placeholder, ready to receive tool links later.

**Files:**
- Create: `index.html`

- [ ] **Step 1: Create `index.html` at the repo root**

Write this exact content to `index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>MATC Paramedic Lab · Student Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="shared/tokens.css">
<style>
  html, body {
    margin: 0; padding: 0;
    background: var(--bg); color: var(--ink);
    font-family: var(--font-sans);
  }
  body { min-height: 100vh; }
  .wrap { max-width: 880px; margin: 0 auto; padding: 28px 36px 48px; }

  .topbar { display: flex; align-items: center; gap: 12px; margin-bottom: 32px; }
  .badge {
    width: 30px; height: 30px; border-radius: 7px;
    background: var(--accent); color: #fff;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 16px;
  }
  .brand-kicker {
    font-size: 11px; font-family: var(--font-mono);
    text-transform: uppercase; letter-spacing: 0.14em; color: var(--ink-soft);
  }
  .brand-name { font-size: 14px; font-weight: 500; }

  .hero { padding: 12px 0 22px; border-bottom: 1px solid var(--line); margin-bottom: 28px; }
  .hero h1 {
    font-family: var(--font-serif); font-weight: 400;
    font-size: 52px; line-height: 1.0; margin: 0;
  }
  .hero p { font-size: 16px; color: var(--ink-soft); margin: 10px 0 0; }

  .section-label {
    font-size: 11px; font-family: var(--font-mono);
    text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-soft);
    margin-bottom: 12px;
  }
  .empty {
    background: var(--bg-sunk); border-radius: 10px;
    padding: 32px; text-align: center;
    font-size: 14px; color: var(--ink-soft);
  }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="badge">+</div>
      <div>
        <div class="brand-kicker">MATC Paramedic Lab</div>
        <div class="brand-name">Student Hub</div>
      </div>
    </div>

    <div class="hero">
      <h1>Student Hub</h1>
      <p>Tools and resources for the MATC paramedic program.</p>
    </div>

    <div class="section-label">Tools</div>
    <div class="empty">Tools coming soon.</div>
  </div>
</body>
</html>
```

- [ ] **Step 2: Verify the student hub serves correctly**

With the server still running:

```bash
curl -s http://localhost:8000/ | grep -q 'Student Hub' && echo "PAGE OK"
curl -s http://localhost:8000/ | grep -q 'shared/tokens.css' && echo "CSS PATH OK"
```
Expected: `PAGE OK` and `CSS PATH OK`.

- [ ] **Step 3: Browser check — student hub renders**

Open `http://localhost:8000/` in a browser. Expected: a styled page (warm-neutral palette, correct fonts) with the branded header, a serif "Student Hub" heading, and the "Tools coming soon" empty state.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "$(cat <<'EOF'
Add student hub landing page at site root

Plain HTML/CSS navigation shell served at /, using shared/tokens.css.
Branded header plus an empty Tools section for future tool links.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update CLAUDE.md for the multi-page structure

`CLAUDE.md` currently describes a single-page "Instructor Hub" at `/`. Update it to describe the two-page site and the new file paths.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Replace the "What this is" section body**

Find this text:
```
The MATC Paramedic Lab "Instructor Hub" — a homepage that shows the current
week's EMS lab shifts (date, AM/PM, cohort, class, instructors). It has two
halves joined only by a Supabase table:

- **Frontend** — a build-less static site (`index.html`, `data.js`, `myday.jsx`,
  `tokens.css`) that reads the `shifts` table.
- **Data pipeline** — Python in `scripts/` that pulls shifts from Humanity.com
  and writes the `shifts` table.

Neither half imports the other. The `shifts` table (`sql/001_shifts.sql`) is the
entire contract between them — the sync writes it with the service key, the
browser reads it with the anon key.
```
Replace it with:
```
The MATC Paramedic Lab site — a build-less static site with two front-end
pages plus a Python data pipeline:

- **Student hub** (`index.html`, served at `/`) — a plain HTML/CSS landing
  page. A navigation hub that will link out to student tools under
  `/tools/<name>` as they are built.
- **Instructor hub** (`instructors/`, served at `/instructors`) — a React page
  showing the current week's EMS lab shifts (date, AM/PM, cohort, class,
  instructors), read from a Supabase `shifts` table.
- **Data pipeline** — Python in `scripts/` that pulls shifts from Humanity.com
  and writes that `shifts` table.

The instructor hub and the pipeline are joined only by the `shifts` table
(`sql/001_shifts.sql`) — the sync writes it with the service key, the browser
reads it with the anon key. `shared/tokens.css` holds the design tokens used by
every page.
```

- [ ] **Step 2: Update the preview command**

Find this text:
```
# Preview the frontend (needed — file:// breaks Babel's XHR fetch of myday.jsx)
python3 -m http.server 8000      # then open http://localhost:8000
```
Replace it with:
```
# Preview the site (needed — file:// breaks Babel's XHR fetch of myday.jsx)
python3 -m http.server 8000      # / = student hub, /instructors/ = instructor hub
```

- [ ] **Step 3: Replace the "Frontend architecture" section**

Find this text:
```
## Frontend architecture

No bundler. `index.html` pulls React 18, ReactDOM, `@babel/standalone`, and
`supabase-js` from CDNs, then loads the three local files. Babel transpiles
`myday.jsx` in the browser at load time.

Boot sequence (`index.html`):
1. `await window.loadParamedicData()` — defined in `data.js`.
2. `ReactDOM.createRoot(...).render(<D5MyDay />)` — `D5MyDay` is from `myday.jsx`.

`data.js` fetches the current week's rows from the Supabase `shifts` table and
assembles `window.PARAMEDIC_DATA` in the exact shape `myday.jsx` consumes
(`schedule[cohortId][dayIdx] = { am, pm }`). The shape contract is documented in
the header comment of `data.js` — keep producer and consumer in sync.

`myday.jsx` is a single React component tree (`D5MyDay` → `D5ShiftCard` →
`D5InstructorBlock` / `D5ScenarioGroup`). All styling is inline styles plus the
CSS custom properties and pill/rail classes defined in `tokens.css`.
```
Replace it with:
```
## Frontend architecture

No bundler — folders map directly to URL paths on Vercel. `/` serves the root
`index.html` (student hub); `/instructors` serves `instructors/index.html`.
Future student tools go under `tools/<name>/index.html`, served at
`/tools/<name>`. `shared/tokens.css` is the design system shared by every page.

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
```

- [ ] **Step 4: Verify no stale references remain**

Run:
```bash
grep -nE 'tokens\.css|index\.html|data\.js|myday\.jsx' CLAUDE.md
```
Expected: every hit is either a `shared/tokens.css`, `instructors/...`, or root-`index.html` reference consistent with the new layout — no bare `tokens.css` stylesheet path and no claim that `index.html` at the root is the instructor hub.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
Update CLAUDE.md for multi-page site structure

Describe the student hub at / and the instructor hub at /instructors,
with shared design tokens under shared/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

With `python3 -m http.server 8000` running from the repo root:

- [ ] `http://localhost:8000/` renders the student hub, styled via `shared/tokens.css`.
- [ ] `http://localhost:8000/instructors/` renders the instructor hub: styled, with the current week's schedule populated from Supabase.
- [ ] `git log --follow instructors/index.html` shows commit history from before the move (history preserved).
- [ ] `~/.claude/skills/matc-humanity/.venv/bin/python -m unittest discover -s tests` still passes — confirms nothing under `scripts/` was disturbed.

Stop the preview server when done.

## Deployment

Pushing the `site-restructure-student-hub` branch and merging to `main` triggers the Vercel production deploy. That step is left to the user — confirm with them before pushing.
