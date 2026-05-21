# /sim-lab Category & Tier Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-select category and tier filters to the `/sim-lab` page.

**Architecture:** A filter bar of toggle chips is added to `sim-lab/index.html`; the page's inline render script gains filter state and re-renders the grouped list on every chip toggle. One file changes; no framework, no data or generator change.

**Tech Stack:** Static HTML/CSS, vanilla JavaScript.

**Spec:** `docs/superpowers/specs/2026-05-21-sim-lab-filters-design.md`

---

## Before you start

Work on a feature branch:

```bash
git checkout -b sim-lab-filters
```

All commits are local. Pushing `main` triggers a Vercel deploy — leave pushing to the user.

Tests run with the repo's interpreter:

```bash
PY=~/.claude/skills/matc-humanity/.venv/bin/python
```

**Note:** this page has no JavaScript test harness (build-less, in-browser). Verification is a Node syntax check on the inline script, the existing `tests/test_frontend_paths.py` guard, and a browser check — consistent with how the rest of this frontend is verified.

---

## Task 1: Add the filter bar to `sim-lab/index.html`

Replace the page with a version that has a category/tier filter bar and filtering logic. The change is one self-contained file rewrite: filter-bar CSS, filter-bar markup, and a render script refactored to filter and re-render.

**Files:**
- Modify: `sim-lab/index.html` (full-file replacement)

- [ ] **Step 1: Replace `sim-lab/index.html`**

Replace the entire contents of `sim-lab/index.html` with exactly this:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>MATC Paramedic Lab · Sim Lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/shared/tokens.css">
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

  .hero { padding: 12px 0 22px; border-bottom: 1px solid var(--line); margin-bottom: 24px; }
  .hero h1 {
    font-family: var(--font-serif); font-weight: 400;
    font-size: 52px; line-height: 1.0; margin: 0;
  }
  .hero p { font-size: 16px; color: var(--ink-soft); margin: 10px 0 0; }

  .filterbar { margin-bottom: 26px; }
  .filter-row { display: flex; align-items: baseline; gap: 14px; margin-bottom: 10px; }
  .filter-label {
    font-size: 11px; font-family: var(--font-mono);
    text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-soft);
    min-width: 76px;
  }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip {
    font-family: var(--font-mono); font-size: 11px;
    padding: 4px 11px; border-radius: 999px;
    border: 1px solid var(--line); background: var(--bg-card);
    color: var(--ink-mid); cursor: pointer;
  }
  .chip:hover { border-color: var(--accent); }
  .chip.active {
    background: var(--accent); border-color: var(--accent); color: #fff;
  }
  .filter-status {
    font-size: 11px; font-family: var(--font-mono);
    color: var(--ink-soft); margin-top: 14px;
  }
  .clear-btn {
    font: inherit; color: var(--accent-deep);
    background: none; border: none; padding: 0; cursor: pointer;
  }
  .clear-btn::before { content: "·"; margin: 0 6px; color: var(--ink-soft); }
  .clear-btn:hover { text-decoration: underline; }

  .category { margin-bottom: 30px; }
  .category-label {
    font-family: var(--font-serif); font-size: 28px; line-height: 1; margin-bottom: 12px;
  }
  .tier-label {
    font-size: 11px; font-family: var(--font-mono);
    text-transform: uppercase; letter-spacing: 0.12em; color: var(--ink-soft);
    margin: 16px 0 8px;
  }
  .scenario {
    display: flex; align-items: baseline; gap: 12px;
    padding: 10px 14px; margin-bottom: 6px;
    border: 1px solid var(--line); border-radius: 8px;
    background: var(--bg-card);
    text-decoration: none; color: var(--ink);
  }
  .scenario:hover { border-color: var(--accent); }
  .scenario-code {
    font-family: var(--font-mono); font-size: 12px;
    color: var(--ink-soft); min-width: 64px;
  }
  .scenario-name { font-size: 14px; font-weight: 500; }
  .empty {
    background: var(--bg-sunk); border-radius: 10px;
    padding: 32px; text-align: center; font-size: 14px; color: var(--ink-soft);
  }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="badge">+</div>
      <div>
        <div class="brand-kicker">MATC Paramedic Lab</div>
        <div class="brand-name">Sim Lab</div>
      </div>
    </div>

    <div class="hero">
      <h1>Sim Lab</h1>
      <p>Interactive simulation scenarios for the MATC paramedic program.</p>
    </div>

    <div class="filterbar">
      <div class="filter-row">
        <div class="filter-label">Category</div>
        <div class="chips" id="category-chips"></div>
      </div>
      <div class="filter-row">
        <div class="filter-label">Tier</div>
        <div class="chips" id="tier-chips"></div>
      </div>
      <div class="filter-status">
        <span id="result-count"></span><button type="button" class="clear-btn" id="clear-filters" hidden>Clear</button>
      </div>
    </div>

    <div id="scenario-list"></div>
  </div>

  <script src="/sim-lab/scenarios.js"></script>
  <script>
    (function () {
      var TIER_ORDER = ["T1", "T2", "T3"];
      var scenarios = window.SIM_LAB_SCENARIOS || [];

      var listRoot = document.getElementById("scenario-list");
      var countEl = document.getElementById("result-count");
      var clearBtn = document.getElementById("clear-filters");
      var categoryChipsEl = document.getElementById("category-chips");
      var tierChipsEl = document.getElementById("tier-chips");

      var selectedCategories = new Set();
      var selectedTiers = new Set();

      // Distinct categories (in data order) and tiers (ordered T1..T3).
      var categories = [];
      var tiers = [];
      scenarios.forEach(function (s) {
        if (categories.indexOf(s.category) === -1) categories.push(s.category);
        if (tiers.indexOf(s.tier) === -1) tiers.push(s.tier);
      });
      tiers.sort(function (a, b) {
        return TIER_ORDER.indexOf(a) - TIER_ORDER.indexOf(b);
      });

      function makeChip(value, selectedSet, chipsEl) {
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = value;
        chip.addEventListener("click", function () {
          if (selectedSet.has(value)) {
            selectedSet.delete(value);
            chip.classList.remove("active");
          } else {
            selectedSet.add(value);
            chip.classList.add("active");
          }
          render();
        });
        chipsEl.appendChild(chip);
      }

      function matchesFilter(s) {
        var catOk = selectedCategories.size === 0 || selectedCategories.has(s.category);
        var tierOk = selectedTiers.size === 0 || selectedTiers.has(s.tier);
        return catOk && tierOk;
      }

      function appendEmpty(message) {
        var empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = message;
        listRoot.appendChild(empty);
      }

      function renderScenario(s) {
        var a = document.createElement("a");
        a.className = "scenario";
        a.href = s.url;
        a.target = "_blank";
        a.rel = "noopener";

        var code = document.createElement("span");
        code.className = "scenario-code";
        code.textContent = s.code;
        a.appendChild(code);

        var name = document.createElement("span");
        name.className = "scenario-name";
        name.textContent = s.name;
        a.appendChild(name);

        return a;
      }

      function render() {
        var filtered = scenarios.filter(matchesFilter);

        countEl.textContent =
          "Showing " + filtered.length + " of " + scenarios.length;
        clearBtn.hidden =
          selectedCategories.size === 0 && selectedTiers.size === 0;

        listRoot.textContent = "";

        if (scenarios.length === 0) {
          appendEmpty("No scenarios available.");
          return;
        }
        if (filtered.length === 0) {
          appendEmpty("No scenarios match these filters.");
          return;
        }

        // Group the filtered scenarios by category (data order), then tier.
        var byCategory = {};
        var orderedCategories = [];
        filtered.forEach(function (s) {
          if (!byCategory[s.category]) {
            byCategory[s.category] = [];
            orderedCategories.push(s.category);
          }
          byCategory[s.category].push(s);
        });

        orderedCategories.forEach(function (cat) {
          var section = document.createElement("div");
          section.className = "category";

          var label = document.createElement("div");
          label.className = "category-label";
          label.textContent = cat;
          section.appendChild(label);

          TIER_ORDER.forEach(function (tier) {
            var inTier = byCategory[cat].filter(function (s) {
              return s.tier === tier;
            });
            if (inTier.length === 0) return;

            var tierLabel = document.createElement("div");
            tierLabel.className = "tier-label";
            tierLabel.textContent = "Tier " + tier.slice(1);
            section.appendChild(tierLabel);

            inTier.forEach(function (s) {
              section.appendChild(renderScenario(s));
            });
          });

          listRoot.appendChild(section);
        });
      }

      clearBtn.addEventListener("click", function () {
        selectedCategories.clear();
        selectedTiers.clear();
        var chips = document.querySelectorAll(".chip");
        for (var i = 0; i < chips.length; i++) {
          chips[i].classList.remove("active");
        }
        render();
      });

      categories.forEach(function (c) {
        makeChip(c, selectedCategories, categoryChipsEl);
      });
      tiers.forEach(function (t) {
        makeChip(t, selectedTiers, tierChipsEl);
      });

      render();
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify the inline script is valid JavaScript**

`new Function(body)` compiles the script without running it — it throws `SyntaxError` on invalid JS. Run from the repo root:

```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('sim-lab/index.html','utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
new Function(m[1]);
console.log('inline script: valid JS');
"
```
Expected: `inline script: valid JS` (no `SyntaxError`).

- [ ] **Step 3: Run the test suite**

The filter change keeps every local resource path root-absolute, so `tests/test_frontend_paths.py` must still pass.

Run: `$PY -m unittest discover -s tests`
Expected: OK — 71 tests, no failures.

- [ ] **Step 4: Verify the page serves**

Start `python3 -m http.server 8000` from the repo root (background), then:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/sim-lab/
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/sim-lab/scenarios.js
curl -s http://localhost:8000/sim-lab/ | grep -q 'id="category-chips"' && echo "FILTER BAR OK"
```
Expected: `200`, `200`, `FILTER BAR OK`. Stop the server.

- [ ] **Step 5: Browser check**

Open `http://localhost:8000/sim-lab/` in a browser. Confirm:
- A filter bar appears below the hero with a **Category** row of chips and a **Tier** row of chips.
- The count reads `Showing 64 of 64` and **Clear** is not shown.
- Clicking a category chip (and/or tier chip) narrows the list, hides empty category/tier headings, updates the count, and reveals **Clear**.
- Selecting multiple chips in a row ORs them; category + tier combine with AND.
- A combination matching nothing shows "No scenarios match these filters."
- **Clear** un-toggles every chip and restores the full list.

If you have no browser tooling, note this as a manual follow-up — Steps 2–4 are the automatable evidence.

- [ ] **Step 6: Commit**

```bash
git add sim-lab/index.html
git commit -m "$(cat <<'EOF'
Add category and tier filters to the /sim-lab page

A filter bar of multi-select toggle chips, derived from the scenario
data; the render script filters (OR within a dimension, AND across
category and tier) and re-renders, with a live count and a Clear control.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

- [ ] `$PY -m unittest discover -s tests` passes with no failures.
- [ ] The inline script passes the Node syntax check (Step 2).
- [ ] Served locally, the filter bar renders and filtering behaves per the spec's success criteria (Step 5).

## Deployment

Pushing the `sim-lab-filters` branch / merging to `main` triggers a Vercel deploy — leave that to the user.

Note: `/sim-lab` is currently **not live in production** — a previous push (`741f547`) did not deploy, a Vercel-side issue the user is resolving separately. Until that is fixed, verify the filters on the **local** preview server, not `matc-ems-site.vercel.app`.
