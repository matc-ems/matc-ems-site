# MATC Paramedic Lab · Instructor Hub

A static homepage for paramedic instructors. Shows the focused single-day briefing for any weekday — AM and PM as two columns, each cohort's scenarios listed under the instructor they're assigned to.

## Files

- **`index.html`** — the page. Open in a browser or serve via GitHub Pages.
- **`data.js`** — the schedule. **This is the only file you'll typically edit each week.**
- **`myday.jsx`** — the React component (UI logic).
- **`tokens.css`** — colors, fonts, spacing.

## Hosting on GitHub Pages

1. Create a new GitHub repo (or use an existing one).
2. Upload all four files to the repo root.
3. In **Settings → Pages**, set source to your branch (e.g. `main`) and folder to `/ (root)`.
4. Your hub will be live at `https://<user>.github.io/<repo>/`.

No build step. No dependencies to install. React, Babel, and Google Fonts load from public CDNs.

## Updating the schedule

Open `data.js` and edit the `schedule` object. The shape is:

```js
schedule: {
  C1: [ // Cohort 1
    { am: <shift or null>, pm: <shift or null> }, // Monday
    { am: ..., pm: ... },                         // Tuesday
    ...                                           // through Friday
  ],
  C2: [...],
  C3: [...],
  C4: [...]
}
```

A `<shift>` looks like:

```js
{
  type: "scenario",          // or "lecture", "skills", "clinical", "exam"
  title: "BVM Skills Stations",
  room: "Sim Bay A",
  instructors: [
    { name: "M. Reyes", role: "Lead" },
    { name: "T. Park",  role: "Assist" }
  ],
  scenarios: [               // optional — list of run sheets / links
    { title: "Station 1 — Adult BVM", href: "scenarios/bvm-adult.html", assignedTo: "M. Reyes" },
    { title: "Station 4 — Difficult airway", href: "scenarios/bvm-difficult.html", assignedTo: "T. Park" },
    { title: "Scene briefing", href: "scenarios/briefing.html" }       // no assignedTo = shared
  ],
  link: { label: "Lecture deck", href: "materials/deck.html" }         // alt: single attached doc
}
```

### Tips
- Set a slot to `null` (e.g. `am: null`) for no session.
- A whole day off is `{ am: null, pm: null }`.
- `assignedTo` can be a single name string, an array of names, or omitted (means shared / everyone).
- `href` links can point to anywhere — relative paths to other pages in this repo, or absolute URLs to external sites.

### Highlighting today
At the top of `data.js`:

```js
todayIdx: 1,  // 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri
```

Set this manually each week, or uncomment the `autoToday()` block at the bottom of `data.js` to detect the weekday automatically (weekends fall back to Friday).

### Each week
Update three things in `data.js`:
1. `weekOf` (e.g. `"May 18–24, 2026"`)
2. `dates` array (the five Mon–Fri dates)
3. The `schedule` object

## Customizing the look

Edit `tokens.css` — all colors, fonts, and cohort tones live there as CSS variables at the top of the file.
