// Paramedic instructor schedule data
//
// SHAPE
//   schedule[cohortId][dayIdx] = { am: Shift|null, pm: Shift|null }
//   Shift = {
//     type: "scenario"|"lecture"|"skills"|"clinical"|"exam",
//     title: string,           // overall theme of the shift
//     room: string,
//     instructors: [{ name, role }],
//     scenarios?: [             // list of scenarios for this shift
//        { title, href, assignedTo?: string | string[] | null }
//        // assignedTo missing  -> shared (everyone in the shift)
//        // assignedTo "name"   -> just that instructor
//        // assignedTo ["A","B"] -> those instructors
//     ],
//     link?: { label, href }    // single attached doc for non-scenario shifts
//   }
//
// To update the schedule, edit the schedule object below. dayIdx is 0=Mon, 4=Fri.
// `todayIdx` controls which day is highlighted. Set it manually each week, or
// switch to the auto-detect snippet at the bottom of this file.

window.PARAMEDIC_DATA = {
  weekOf: "May 11–17, 2026",
  todayIdx: 1, // 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri

  days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
  fullDays: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  dates: ["May 11", "May 12", "May 13", "May 14", "May 15"],
  shifts: { am: "8:00 – 12:00", pm: "1:00 – 5:00" },

  cohorts: [
    { id: "C1", name: "Cohort 1", stage: "Foundations" },
    { id: "C2", name: "Cohort 2", stage: "Field Ops" },
    { id: "C3", name: "Cohort 3", stage: "Clinical" },
    { id: "C4", name: "Cohort 4", stage: "Capstone" }
  ],

  schedule: {
    // —— Cohort 1 ——————————————————————————————————————————————
    C1: [
      // Mon
      {
        am: { type: "lecture", title: "Airway Anatomy", room: "Room 204",
              instructors: [{ name: "M. Reyes", role: "Lead" }],
              link: { label: "Lecture deck", href: "materials/airway-anatomy.html" } },
        pm: null
      },
      // Tue
      {
        am: { type: "scenario", title: "BVM Skills Stations", room: "Sim Bay A",
              instructors: [{ name: "M. Reyes", role: "Lead" }, { name: "T. Park", role: "Assist" }],
              scenarios: [
                { title: "Station 1 — Adult BVM",       href: "scenarios/bvm-adult.html",     assignedTo: "M. Reyes" },
                { title: "Station 2 — Pediatric",       href: "scenarios/bvm-peds.html",      assignedTo: "M. Reyes" },
                { title: "Station 3 — Two-rescuer",     href: "scenarios/bvm-two.html",       assignedTo: "T. Park" },
                { title: "Station 4 — Difficult airway", href: "scenarios/bvm-difficult.html", assignedTo: "T. Park" }
              ] },
        pm: { type: "scenario", title: "Adult Respiratory Distress", room: "Sim Bay A",
              instructors: [{ name: "M. Reyes", role: "Lead" }],
              scenarios: [
                { title: "Case A — COPD exacerbation",     href: "scenarios/copd.html" },
                { title: "Case B — Acute asthma",          href: "scenarios/asthma.html" },
                { title: "Case C — CHF / pulmonary edema", href: "scenarios/chf.html" }
              ] }
      },
      // Wed
      {
        am: null,
        pm: { type: "skills", title: "IV Access Lab", room: "Skills Lab 1",
              instructors: [{ name: "T. Park", role: "Lead" }],
              link: { label: "Station rotation map", href: "materials/iv-stations.html" } }
      },
      // Thu
      {
        am: { type: "skills", title: "Medication Administration", room: "Skills Lab 1",
              instructors: [{ name: "T. Park", role: "Lead" }] },
        pm: { type: "lecture", title: "Pharmacology Pt. 1", room: "Room 204",
              instructors: [{ name: "M. Reyes", role: "Lead" }],
              link: { label: "Reading + slides", href: "materials/pharm-1.html" } }
      },
      // Fri
      { am: null, pm: null }
    ],

    // —— Cohort 2 ——————————————————————————————————————————————
    C2: [
      // Mon
      {
        am: { type: "scenario", title: "MVC — Multi-Patient Triage", room: "Sim Bay B",
              instructors: [
                { name: "D. Okafor", role: "Lead" },
                { name: "S. Liu",    role: "Assist" },
                { name: "R. Bauer",  role: "Assist" }
              ],
              scenarios: [
                { title: "Incident command brief",            href: "scenarios/mvc-ic.html", assignedTo: "D. Okafor" },
                { title: "Patient 2 actor — chest trauma",    href: "scenarios/mvc-p2.html", assignedTo: "S. Liu" },
                { title: "Patient 3 actor — entrapped",       href: "scenarios/mvc-p3.html", assignedTo: "R. Bauer" },
                { title: "Patient 4 actor — bystander",       href: "scenarios/mvc-p4.html", assignedTo: ["S. Liu", "R. Bauer"] }
              ] },
        pm: { type: "lecture", title: "Hemorrhage Control Review", room: "Room 207",
              instructors: [{ name: "D. Okafor", role: "Lead" }] }
      },
      // Tue
      {
        am: { type: "scenario", title: "Pediatric Seizure", room: "Sim Bay B",
              instructors: [{ name: "S. Liu", role: "Lead" }],
              scenarios: [
                { title: "Run sheet — febrile seizure", href: "scenarios/peds-febrile.html" },
                { title: "Parent actor brief",          href: "scenarios/peds-parent.html" },
                { title: "Debrief prompts",             href: "scenarios/peds-debrief.html" }
              ] },
        pm: null
      },
      // Wed
      {
        am: { type: "scenario", title: "Tactical Casualty Care", room: "Field Site 2",
              instructors: [
                { name: "D. Okafor", role: "Lead" },
                { name: "R. Bauer",  role: "Assist" }
              ],
              scenarios: [
                { title: "Scene safety briefing",  href: "scenarios/tccc-safety.html" }, // shared
                { title: "Tourniquet station",     href: "scenarios/tccc-tq.html",   assignedTo: "R. Bauer" },
                { title: "Casualty drag & carry",  href: "scenarios/tccc-drag.html", assignedTo: "D. Okafor" }
              ] },
        pm: null
      },
      // Thu
      {
        am: null,
        pm: { type: "exam", title: "Module 4 Practical Exam", room: "Sim Bay B",
              instructors: [{ name: "D. Okafor", role: "Examiner" }, { name: "S. Liu", role: "Examiner" }],
              link: { label: "Exam rubric + station sheets", href: "materials/m4-exam.html" } }
      },
      // Fri
      {
        am: { type: "scenario", title: "OB / Childbirth", room: "Sim Bay B",
              instructors: [{ name: "S. Liu", role: "Lead" }],
              scenarios: [
                { title: "Normal delivery",   href: "scenarios/ob-normal.html" },
                { title: "Shoulder dystocia", href: "scenarios/ob-dystocia.html" }
              ] },
        pm: null
      }
    ],

    // —— Cohort 3 ——————————————————————————————————————————————
    C3: [
      // Mon
      {
        am: null,
        pm: { type: "clinical", title: "ED Rotation — St. Mary's", room: "Off-site",
              instructors: [{ name: "A. Chen", role: "Preceptor" }],
              link: { label: "Sign-off checklist", href: "materials/ed-checklist.html" } }
      },
      // Tue
      {
        am: { type: "scenario", title: "Cardiac Arrest — ROSC", room: "Sim Bay C",
              instructors: [
                { name: "A. Chen", role: "Lead" },
                { name: "J. Hall", role: "Assist" }
              ],
              scenarios: [
                { title: "Witnessed VF arrest",      href: "scenarios/vf-arrest.html", assignedTo: "A. Chen" },
                { title: "PEA — reversible causes",  href: "scenarios/pea.html",       assignedTo: "A. Chen" },
                { title: "Post-ROSC management",     href: "scenarios/post-rosc.html", assignedTo: "J. Hall" },
                { title: "ECG interpretation drill", href: "scenarios/ecg-drill.html", assignedTo: "J. Hall" }
              ] },
        pm: null
      },
      // Wed
      {
        am: { type: "scenario", title: "STEMI — 12-lead", room: "Sim Bay C",
              instructors: [{ name: "J. Hall", role: "Lead" }],
              scenarios: [
                { title: "Anterior STEMI",                href: "scenarios/stemi-ant.html" },
                { title: "Inferior STEMI + RV",           href: "scenarios/stemi-inf.html" },
                { title: "Transport decision algorithm",  href: "scenarios/stemi-transport.html" }
              ] },
        pm: { type: "scenario", title: "Stroke Assessment", room: "Sim Bay C",
              instructors: [{ name: "A. Chen", role: "Lead" }],
              scenarios: [
                { title: "Cincinnati scale walkthrough", href: "scenarios/stroke-cincinnati.html" },
                { title: "Last-known-well interview",    href: "scenarios/stroke-lkw.html" }
              ] }
      },
      // Thu
      {
        am: { type: "lecture", title: "Pharmacology Review", room: "Room 204",
              instructors: [{ name: "A. Chen", role: "Lead" }] },
        pm: null
      },
      // Fri
      {
        am: null,
        pm: { type: "clinical", title: "ED Rotation — St. Mary's", room: "Off-site",
              instructors: [{ name: "A. Chen", role: "Preceptor" }] }
      }
    ],

    // —— Cohort 4 ——————————————————————————————————————————————
    C4: [
      // Mon
      {
        am: { type: "scenario", title: "Capstone — Pediatric Drowning", room: "Sim Bay D",
              instructors: [{ name: "K. Mendez", role: "Lead Evaluator" }],
              scenarios: [
                { title: "Drowning — full run sheet", href: "scenarios/capstone-drowning.html" },
                { title: "Evaluator scoring rubric",  href: "scenarios/capstone-rubric.html" }
              ] },
        pm: null
      },
      // Tue
      { am: null, pm: null },
      // Wed
      {
        am: { type: "scenario", title: "Capstone — Anaphylaxis", room: "Sim Bay D",
              instructors: [
                { name: "K. Mendez", role: "Lead Evaluator" },
                { name: "P. Novak",  role: "Assist Evaluator" }
              ],
              scenarios: [
                { title: "Anaphylaxis run sheet", href: "scenarios/capstone-anaphylaxis.html" },
                { title: "Med kit + scoring",     href: "scenarios/capstone-medkit.html", assignedTo: "P. Novak" }
              ] },
        pm: null
      },
      // Thu
      {
        am: { type: "scenario", title: "Capstone — Multi-System Trauma", room: "Sim Bay D",
              instructors: [
                { name: "K. Mendez", role: "Lead Evaluator" },
                { name: "P. Novak",  role: "Assist Evaluator" }
              ],
              scenarios: [
                { title: "Trauma run sheet",     href: "scenarios/capstone-trauma.html" },
                { title: "Trauma timing & flow", href: "scenarios/capstone-timing.html", assignedTo: "P. Novak" }
              ] },
        pm: { type: "exam", title: "Final Oral Boards", room: "Room 301",
              instructors: [{ name: "K. Mendez", role: "Examiner" }, { name: "P. Novak", role: "Examiner" }],
              link: { label: "Oral board question set", href: "materials/oral-boards.html" } }
      },
      // Fri
      {
        am: { type: "exam", title: "Final Written Exam", room: "Room 301",
              instructors: [{ name: "K. Mendez", role: "Proctor" }],
              link: { label: "Proctor instructions", href: "materials/written-exam.html" } },
        pm: null
      }
    ]
  },

  typeMeta: {
    scenario: { label: "Scenario", short: "SCN" },
    lecture:  { label: "Lecture",  short: "LEC" },
    skills:   { label: "Skills",   short: "SKL" },
    clinical: { label: "Clinical", short: "CLN" },
    exam:     { label: "Exam",     short: "EXM" }
  }
};

// —— helpers used by the page ————————————————————————————————————
window.PD = {
  // Group a shift's scenarios by instructor, with shared scenarios collected separately
  scenariosByInstructor(shift) {
    if (!shift || !shift.scenarios || shift.scenarios.length === 0) return null;
    const result = new Map();
    shift.instructors.forEach(i => result.set(i.name, []));
    const shared = [];
    shift.scenarios.forEach(scn => {
      if (!scn.assignedTo) { shared.push(scn); return; }
      const targets = Array.isArray(scn.assignedTo) ? scn.assignedTo : [scn.assignedTo];
      targets.forEach(t => {
        if (!result.has(t)) result.set(t, []);
        result.get(t).push(scn);
      });
    });
    return { perInstructor: result, shared };
  }
};

// —— OPTIONAL: auto-detect today (overrides todayIdx above) ——
// Uncomment this block to have the page automatically highlight the current
// weekday. Saturday/Sunday will fall back to Friday.
//
// (function autoToday() {
//   const dow = new Date().getDay(); // 0=Sun .. 6=Sat
//   if (dow >= 1 && dow <= 5) window.PARAMEDIC_DATA.todayIdx = dow - 1;
//   else window.PARAMEDIC_DATA.todayIdx = 4; // weekend -> Friday
// })();
