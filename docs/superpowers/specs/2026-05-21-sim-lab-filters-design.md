# `/sim-lab` Category & Tier Filters

**Status:** Approved
**Date:** 2026-05-21
**Scope:** Frontend only — changes to `sim-lab/index.html`. No change to
`sim-lab/scenarios.js`, the generator, or any other file.

## Goal

Add filters to the `/sim-lab` page so an instructor can narrow the 64-scenario
list by clinical category and/or difficulty tier. Filtering was deferred as out
of scope in the original `/sim-lab` spec (`2026-05-21-sim-lab-design.md`); this
adds it.

## The filter bar

A filter bar sits between the page hero and the scenario list. It has two
labeled rows of **toggle chips**:

- **Category** — one chip per distinct `category` in the scenario data
  (Behavioral, Cardiac, Medical, Pediatric, Respiratory).
- **Tier** — one chip per distinct `tier` in the data (T1, T2, T3).

The chip sets are **derived from `window.SIM_LAB_SCENARIOS` at render time**, in
the order the (already-sorted) data presents them — no hardcoded category or
tier list to drift from the data.

Chips use the shared design tokens, consistent with the page:

- **Inactive:** outlined — `var(--line)` border, `var(--ink)` text, card
  background.
- **Active:** filled — `var(--accent)` background, white text (the same
  treatment as the page's `+` badge).

Alongside the chips: a small status line showing **`Showing N of <total>`**
(live count of matching scenarios) and a **Clear** control that resets all
chips. The Clear control is shown only when at least one chip is active.

## Filter behavior

- Clicking a chip toggles it on or off. Multiple chips may be active in each
  row (multi-select).
- A scenario is shown when **(no Category chip is active OR its category is
  active) AND (no Tier chip is active OR its tier is active)** — i.e. OR within
  a row, AND across the two rows.
- **Default state — all chips off — shows every scenario** (all 64).
- The category and tier section headings re-render on every filter change;
  groups with no matching scenarios are not drawn.
- When a filter combination matches no scenarios, the list area shows a plain
  empty state: **"No scenarios match these filters."**
- **Clear** turns off every chip, returning to the all-shown default.

## Implementation notes

Everything stays in `sim-lab/index.html` — plain HTML, CSS, and vanilla
JavaScript, no framework, consistent with the page as built.

The current page runs a one-shot render IIFE. It is refactored into:

1. **Filter state** — two `Set`s, `selectedCategories` and `selectedTiers`,
   both empty initially.
2. **Build the chip bar once** — derive the distinct categories and tiers from
   the data, render a chip per value; each chip's click handler toggles its
   value in the corresponding set and calls `render()`.
3. **`render()`** — filter `SIM_LAB_SCENARIOS` by the current sets, update the
   `Showing N of <total>` count and the Clear control's visibility, then
   rebuild the grouped category/tier list (the existing grouping logic already
   omits empty groups, so it needs no change beyond receiving the filtered
   list).

Scenario data continues to come from `window.SIM_LAB_SCENARIOS`; the existing
"missing or empty data" empty state (`No scenarios available.`) is kept for the
case where the data file fails to load, distinct from the filter empty state.

All local resource paths remain root-absolute (`/shared/tokens.css`,
`/sim-lab/scenarios.js`).

## Out of scope

- **Text search.** No free-text search box — only category/tier chips.
- **Filter persistence.** Filter state is in-memory; it is not stored in the
  URL or `localStorage`, and resets on reload.
- **Changes to `sim-lab/scenarios.js` or the generator.** The data and its
  shape are unchanged.
- **Filtering on any other field** (protocol, name, etc.).

## Verification & success criteria

1. Served locally, `/sim-lab` shows the filter bar between the hero and the
   list, with a chip per category and per tier.
2. With all chips off, every scenario is listed and the count reads
   `Showing <total> of <total>`.
3. Activating category chips and/or tier chips narrows the list per the
   behavior above (OR within a row, AND across rows); the count updates and
   empty category/tier groups disappear.
4. A combination that matches nothing shows "No scenarios match these
   filters."; Clear restores the full list.
5. `tests/test_frontend_paths.py` still passes — `sim-lab/index.html` keeps
   root-absolute resource paths.
