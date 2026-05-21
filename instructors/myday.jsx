/* Design 5: "My Day" — focused single-day briefing
   The view an instructor opens at 7:45 AM.
   AM and PM are two big columns. Within each shift card, scenarios are
   listed with per-instructor assignments. A small day-picker tab strip
   on top lets them peek at other days, but the focus is today.
*/
const { useState: useS5 } = React;

function D5MyDay() {
  const D = window.PARAMEDIC_DATA;
  const [dayIdx, setDayIdx] = useS5(D.todayIdx);

  // For the focused day, collect each cohort's am and pm shifts
  const dayCohorts = D.cohorts.map((c, ci) => ({
    cohort: c, cIdx: ci+1, day: D.schedule[c.id][dayIdx]
  }));

  return (
    <div style={{
      fontFamily: "var(--font-sans)",
      background: "var(--bg)",
      color: "var(--ink)",
      minHeight: "100%",
      padding: "28px 36px 40px"
    }}>
      {/* Top bar */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 7,
            background: "var(--accent)",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            color: "white", fontWeight: 700, fontSize: 16
          }}>+</div>
          <div>
            <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.14em", color: "var(--ink-soft)" }}>
              MATC EMS Department
            </div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Instructor Hub</div>
          </div>
        </div>

        {/* Day picker */}
        <div style={{ display: "flex", gap: 4, padding: 4, background: "var(--bg-sunk)", borderRadius: 10 }}>
          {D.days.map((d, di) => {
            const isActive = di === dayIdx;
            const isToday = di === D.todayIdx;
            return (
              <button key={di} onClick={() => setDayIdx(di)} style={{
                background: isActive ? "var(--bg-card)" : "transparent",
                color: isActive ? "var(--ink)" : "var(--ink-mid)",
                border: "none",
                borderRadius: 7,
                padding: "8px 14px",
                cursor: "pointer",
                display: "flex", alignItems: "baseline", gap: 6,
                boxShadow: isActive ? "0 1px 2px rgba(0,0,0,0.06)" : "none"
              }}>
                <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.08em", color: isToday ? "var(--accent-deep)" : "inherit" }}>
                  {d}
                </span>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{D.dates[di].split(" ")[1]}</span>
                {isToday && <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--accent)", marginLeft: 2 }} />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Date hero */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 16, padding: "12px 0 18px", borderBottom: "1px solid var(--line)", marginBottom: 22 }}>
        <div className="font-serif" style={{ fontSize: 52, lineHeight: 0.95 }}>
          {D.fullDays[dayIdx]}
        </div>
        <div style={{ fontSize: 18, color: "var(--ink-soft)" }}>{D.dates[dayIdx]}</div>
        {dayIdx === D.todayIdx && (
          <div style={{
            fontSize: 10, fontFamily: "var(--font-mono)",
            background: "var(--accent)", color: "white",
            padding: "4px 9px", borderRadius: 3,
            letterSpacing: "0.14em", alignSelf: "center"
          }}>● TODAY</div>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12, color: "var(--ink-soft)", fontFamily: "var(--font-mono)" }}>
          {countActive(dayCohorts)} active sessions · {D.cohorts.length} cohorts
        </div>
      </div>

      {/* AM / PM columns */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        {["am", "pm"].map(shiftKey => (
          <div key={shiftKey}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12 }}>
              <div className="font-serif" style={{ fontSize: 28, lineHeight: 1 }}>
                {shiftKey === "am" ? "Morning" : "Afternoon"}
              </div>
              <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-soft)", letterSpacing: "0.06em" }}>
                {D.shifts[shiftKey]}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {dayCohorts.map(({ cohort, cIdx, day }) => {
                const shift = day && day[shiftKey];
                return (
                  <D5ShiftCard key={cohort.id} cohort={cohort} cIdx={cIdx} shift={shift} />
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function countActive(dayCohorts) {
  let n = 0;
  dayCohorts.forEach(({ day }) => {
    if (day?.am) n++;
    if (day?.pm) n++;
  });
  return n;
}

function D5ShiftCard({ cohort, cIdx, shift }) {
  if (!shift) {
    return (
      <div className={`rail-c${cIdx}`} style={{
        background: "var(--bg-sunk)",
        borderRadius: 10,
        padding: "10px 14px 10px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        opacity: 0.55
      }}>
        <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--ink-mid)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {cohort.name}
        </div>
        <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>— no session —</span>
      </div>
    );
  }

  const { perInstructor, shared } = shift.activities;
  const hasMultiInstructors = shift.instructors.length > 1;
  const hasAssigned = shift.instructors.some(
    ins => (perInstructor[ins.name] || []).length > 0
  );

  return (
    <div className={`rail-c${cIdx}`} style={{
      background: "var(--bg-card)",
      border: "1px solid var(--line)",
      borderRadius: 10,
      padding: "14px 16px 16px 22px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--ink-mid)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {cohort.name}
        </div>
        <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)" }}>{shift.room}</span>
      </div>

      <div className="font-serif" style={{ fontSize: 22, lineHeight: 1.15, marginBottom: 10 }}>
        {shift.title}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Shared material groups, one per activity, above the instructors. */}
        {shared.map((group, gi) => (
          <D5ScenarioGroup key={`shared-${gi}`} label={group.name} scenarios={group.links} />
        ))}

        {/* Instructors: per-instructor blocks when scenarios are assigned,
            otherwise a flat name list (same as a shift with no sheet data). */}
        {hasAssigned ? (
          shift.instructors.map(ins => (
            <D5InstructorBlock
              key={ins.name}
              name={ins.name}
              scenarios={perInstructor[ins.name] || []}
              solo={!hasMultiInstructors}
            />
          ))
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {shift.instructors.map((ins, i) => (
              <div key={i} style={{ fontSize: 13, fontWeight: 500 }}>
                {ins.name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function D5InstructorBlock({ name, scenarios, solo }) {
  return (
    <div>
      <div style={{ marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
      </div>
      {scenarios.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--ink-soft)", fontStyle: "italic", paddingLeft: 2 }}>
          assists on shared scenarios
        </div>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 3 }}>
          {scenarios.map((s, i) => (
            <li key={i} style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "baseline" }}>
              <span style={{ color: "var(--ink-soft)", fontFamily: "var(--font-mono)", fontSize: 10, paddingTop: 2 }}>›</span>
              <a href={s.href} className="scenario-link" style={{ fontSize: 13 }}>{s.label}</a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function D5ScenarioGroup({ label, scenarios }) {
  return (
    <div style={{
      background: "var(--bg-sunk)",
      borderRadius: 7,
      padding: "8px 10px"
    }}>
      {label && (
        <div style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
          {label}
        </div>
      )}
      <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 3 }}>
        {scenarios.map((s, i) => (
          <li key={i} style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "baseline" }}>
            <span style={{ color: "var(--ink-soft)", fontFamily: "var(--font-mono)", fontSize: 10, paddingTop: 2 }}>›</span>
            <a href={s.href} className="scenario-link" style={{ fontSize: 13 }}>{s.label}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}

window.D5MyDay = D5MyDay;
