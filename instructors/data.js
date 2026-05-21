// data.js — Supabase-backed loader for the MATC Paramedic Lab Instructor Hub.
//
// Exposes `window.loadParamedicData()`, which fetches this week's shifts from
// the public `shifts` table and assembles `window.PARAMEDIC_DATA` in the shape
// myday.jsx expects. The static schedule that used to live here is now driven
// entirely by Supabase (populated by scripts/sync_to_supabase.py).
//
// SHAPE produced (see myday.jsx for the consumer):
//   schedule[cohortId][dayIdx] = { am: Shift|null, pm: Shift|null }
//   Shift = { type, title, room, instructors: [{name, role}],
//             activities: { perInstructor: {<name>: [{label, href}]},
//                           shared: [{name, links: [{label, href}]}] } }

const SUPABASE_URL = "https://tapgnqgbszyhrkjsjmrg.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_SEe6wc-wEwSiRYKfwVZ58Q_0f90CnaB";

// Static week-of/cohort scaffolding. Cohorts always render in this order;
// empty days/shifts come through as `null` and the component greys them out.
const DAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const DAYS_FULL  = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const COHORTS    = [
  { id: "C1", name: "Cohort 1" },
  { id: "C2", name: "Cohort 2" },
  { id: "C3", name: "Cohort 3" },
  { id: "C4", name: "Cohort 4" },
];
const TYPE_META = {
  scenario: { label: "Scenario", short: "SCN" },
  lecture:  { label: "Lecture",  short: "LEC" },
  skills:   { label: "Skills",   short: "SKL" },
  clinical: { label: "Clinical", short: "CLN" },
  exam:     { label: "Exam",     short: "EXM" },
};

// Monday–Friday of the ISO week containing `today`. Weekends resolve to the
// week that just ended (same convention as scripts/sync_to_supabase.py).
function currentWeekRange(today = new Date()) {
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  // getDay(): Sun=0, Mon=1, ..., Sat=6. Map Sunday onto previous Monday.
  const dow = d.getDay();
  const offsetToMonday = dow === 0 ? -6 : 1 - dow;
  const monday = new Date(d); monday.setDate(d.getDate() + offsetToMonday);
  const friday = new Date(monday); friday.setDate(monday.getDate() + 4);
  return { monday, friday };
}

function isoDate(d) {
  // YYYY-MM-DD in local time (matches what Supabase stored from the sync script).
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function shortMonthDay(d) {
  // "May 18", "May 22" — matches the original data.js dates array format.
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function weekOfLabel(monday, friday) {
  // "May 18–22, 2026" if same month, else "May 30–Jun 3, 2026".
  const sameMonth = monday.getMonth() === friday.getMonth();
  const m1 = monday.toLocaleDateString("en-US", { month: "short" });
  const m2 = friday.toLocaleDateString("en-US", { month: "short" });
  const d1 = monday.getDate();
  const d2 = friday.getDate();
  const yr = friday.getFullYear();
  return sameMonth ? `${m1} ${d1}–${d2}, ${yr}` : `${m1} ${d1}–${m2} ${d2}, ${yr}`;
}

// Where today sits in DAYS_SHORT. Saturday/Sunday pin to Friday so the page
// still has a "today" highlight on weekends.
function computeTodayIdx(today = new Date()) {
  const dow = today.getDay();
  if (dow >= 1 && dow <= 5) return dow - 1;
  return 4; // weekend -> Friday
}

// Turn one Supabase row into the Shift object myday.jsx renders.
function shiftFromRow(row) {
  const acts = row.activities || {};
  return {
    type: row.type || "scenario",                       // fallback until v2 wires `type`
    title: row.title || `EMS-${row.class_id}`,
    room: row.room || "",
    instructors: Array.isArray(row.instructors) ? row.instructors : [],
    // Resolved at sync time by scripts/sheet_activities.py; normalized here so
    // the component never sees a missing key.
    activities: {
      perInstructor: (acts && acts.perInstructor) || {},
      shared: (acts && Array.isArray(acts.shared)) ? acts.shared : [],
    },
  };
}

// Build `schedule[Cn][dayIdx] = { am, pm }` from the flat array of rows.
function buildSchedule(rows, mondayISO) {
  const monday = new Date(mondayISO);
  const empty = () => Array.from({ length: 5 }, () => ({ am: null, pm: null }));
  const out = { C1: empty(), C2: empty(), C3: empty(), C4: empty() };

  for (const row of rows) {
    const cohortId = `C${row.cohort_number}`;
    if (!out[cohortId]) continue;             // shouldn't happen, but be defensive

    const rowDate = new Date(row.shift_date);
    const dayIdx = Math.round((rowDate - monday) / (24 * 60 * 60 * 1000));
    if (dayIdx < 0 || dayIdx > 4) continue;   // outside Mon–Fri (defensive)

    const bucket = row.am_pm === "am" ? "am" : "pm";
    out[cohortId][dayIdx][bucket] = shiftFromRow(row);
  }
  return out;
}

// Fetch shifts for the current week and assemble PARAMEDIC_DATA.
window.loadParamedicData = async function loadParamedicData() {
  const client = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  const { monday, friday } = currentWeekRange();
  const mondayISO = isoDate(monday);
  const fridayISO = isoDate(friday);

  const { data: rows, error } = await client
    .from("shifts")
    .select("*")
    .gte("shift_date", mondayISO)
    .lte("shift_date", fridayISO);

  if (error) {
    console.error("Supabase fetch failed:", error);
    throw error;
  }

  const dates = Array.from({ length: 5 }, (_, i) => {
    const d = new Date(monday); d.setDate(monday.getDate() + i);
    return shortMonthDay(d);
  });

  window.PARAMEDIC_DATA = {
    weekOf: weekOfLabel(monday, friday),
    todayIdx: computeTodayIdx(),
    days: DAYS_SHORT,
    fullDays: DAYS_FULL,
    dates,
    shifts: { am: "8:00 – 12:00", pm: "1:00 – 5:00" },
    cohorts: COHORTS,
    schedule: buildSchedule(rows || [], mondayISO),
    typeMeta: TYPE_META,
  };
};
