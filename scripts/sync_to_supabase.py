"""Sync Humanity workflow JSON into the Supabase `shifts` table.

Run from the repo root:
    ~/.claude/skills/matc-humanity/.venv/bin/python scripts/sync_to_supabase.py

Reads SUPABASE_URL and SUPABASE_SERVICE_KEY from .env (repo root). The
matc-humanity skill must already have a valid bearer token saved on this
machine (`humanity_agent.py --set-token "..."`).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import requests
from dotenv import load_dotenv

from datetime import date, time, timedelta


def parse_time(humanity_time: str) -> time:
    """Convert Humanity's "08:00AM" / "01:00PM" / "12:00PM" into a `time`.

    Humanity emits 12-hour clock strings with no separator before AM/PM.
    """
    hh, rest = humanity_time[:2], humanity_time[2:]
    mm = rest[1:3]  # rest is ":MMxM" -> skip the leading ":"
    suffix = rest[3:].upper()
    hour = int(hh)
    minute = int(mm)
    if suffix == "AM":
        if hour == 12:
            hour = 0
    elif suffix == "PM":
        if hour != 12:
            hour += 12
    else:
        raise ValueError(f"Unrecognized AM/PM suffix in {humanity_time!r}")
    return time(hour, minute)


def last_name(humanity_name: str) -> str:
    """Humanity returns instructor names as "Last, First". Return the "Last".

    If the format is unexpected (no comma), return the original string so
    downstream comparisons remain deterministic.
    """
    if "," not in humanity_name:
        return humanity_name
    return humanity_name.split(",", 1)[0].strip()


def derive_am_pm(t: time) -> str:
    """Return 'am' for times strictly before noon, 'pm' for noon and after."""
    return "am" if t.hour < 12 else "pm"


def derive_role(instructor_name: str, cohort_lead_last_name: str | None) -> str:
    """Return 'Lead' iff the instructor's last name matches the cohort lead.

    Everything else (including unknown name formats and a missing cohort lead)
    falls through to 'Assist'.
    """
    if not cohort_lead_last_name:
        return "Assist"
    return "Lead" if last_name(instructor_name) == cohort_lead_last_name else "Assist"


def normalize_shift(shift: dict, *, class_titles: dict[int, str]) -> dict:
    """Transform one Humanity workflow shift into a row ready for Supabase.

    Returns a dict matching the `shifts` table columns the v1 sync writes.
    `type` and `room` are not set here — they default to NULL in the table.
    """
    start = parse_time(shift["starting_time"])
    end = parse_time(shift["ending_time"])
    lead_last = shift.get("cohort_lead_last_name")
    raw_title = class_titles.get(shift["class_id"], "")
    title = raw_title or None  # empty string -> NULL

    return {
        "shift_date": shift["date"],
        "am_pm": derive_am_pm(start),
        "cohort_number": shift["cohort_number"],
        "class_id": shift["class_id"],
        "start_time": start.strftime("%H:%M:%S"),
        "end_time": end.strftime("%H:%M:%S"),
        "title": title,
        "instructors": [
            {"name": i["name"], "role": derive_role(i["name"], lead_last)}
            for i in shift["instructors"]
        ],
        "cohort_lead_last_name": lead_last,
    }


def current_week_range(*, today: date | None = None) -> tuple[date, date]:
    """Return (Monday, Friday) of the ISO calendar week containing `today`.

    Sat/Sun resolve to the week that just ended (the most recent Mon-Fri).
    If `today` is omitted, uses `date.today()`. Pass an explicit date in tests.
    """
    if today is None:
        today = date.today()
    # date.weekday(): Monday=0 .. Sunday=6
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse sync_to_supabase.py CLI args.

    `--from` and `--to` are independent of the Humanity agent's `--from`/`--to`
    even though they have the same names; the sync forwards them when calling
    the agent.
    """
    p = argparse.ArgumentParser(description="Sync Humanity shifts into Supabase.")
    p.add_argument("--from", dest="from_date",
                   help="Inclusive range start (YYYY-MM-DD). Must be paired with --to.")
    p.add_argument("--to", dest="to_date",
                   help="Inclusive range end (YYYY-MM-DD). Must be paired with --from.")
    p.add_argument("--cohorts", default="1,2,3,4",
                   help="Comma-separated cohort numbers. Default: 1,2,3,4.")
    p.add_argument("--input",
                   help="Path to a pre-fetched workflow JSON. Skips the Humanity call.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print rows that would be upserted; make no Supabase call.")
    p.add_argument("--skip-activities", action="store_true",
                   help="Skip the activity-sheet pull (shifts only; no gws needed).")
    args = p.parse_args(argv)
    if bool(args.from_date) ^ bool(args.to_date):
        p.error("--from and --to must be provided together")
    return args


# Path to the Humanity skill's bundled CLI + venv interpreter.
HUMANITY_PY = os.path.expanduser("~/.claude/skills/matc-humanity/.venv/bin/python")
HUMANITY_AGENT = os.path.expanduser("~/.claude/skills/matc-humanity/humanity_agent.py")


def run_humanity_workflow(*, from_date: str, to_date: str, cohorts: str) -> str:
    """Shell out to humanity_agent.py --workflow and return the output JSON path.

    The agent prints only the file path to stdout in --workflow mode.
    On non-zero exit, prints stderr and aborts the sync (likely a 401 token
    expiry; the agent's own message tells the user how to refresh).
    """
    cmd = [
        HUMANITY_PY, HUMANITY_AGENT,
        "--workflow",
        "--from", from_date,
        "--to", to_date,
        "--cohorts", cohorts,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr or "humanity_agent.py failed with no stderr.\n")
        sys.exit(1)
    return result.stdout.strip()


def load_workflow_json(path: str) -> list[dict]:
    """Read a Humanity workflow JSON file; expected to be a list of shifts."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a list of shifts in {path}, got {type(data).__name__}")
    return data


def attach_activities(rows, *, get_values=None, resolve=None):
    """Attach an `activities` blob to every shift row, in place.

    Fetches each cohort's sheet tab once (cached). A cohort whose tab is missing
    or still in the old format gets `empty_activities()` for all its shifts,
    with a warning. `get_values` / `resolve` are injectable for tests; they
    default to the gws-backed functions in sheet_activities.
    """
    import sheet_activities as sa

    if get_values is None:
        get_values = sa.gws_get_values
    if resolve is None:
        resolve = sa.resolve_doc_title

    tab_cache = {}  # cohort_number -> data rows (None means an unusable tab)

    def cohort_data(cohort_number):
        if cohort_number not in tab_cache:
            values = get_values(cohort_number)
            if values and sa.is_new_format(values[0]):
                tab_cache[cohort_number] = values[1:]
            else:
                sys.stderr.write(
                    f"warning: Cohort {cohort_number} sheet tab is empty or "
                    f"not the 14-column activity format; no activities for it\n"
                )
                tab_cache[cohort_number] = None
        return tab_cache[cohort_number]

    for row in rows:
        data_rows = cohort_data(row["cohort_number"])
        if data_rows is None:
            row["activities"] = sa.empty_activities()
            continue
        row["activities"] = sa.build_activities(
            data_rows,
            date.fromisoformat(row["shift_date"]),
            row["am_pm"],
            row["instructors"],
            resolve=resolve,
        )


def upsert_to_supabase(rows: list[dict], *, supabase_url: str, service_key: str) -> None:
    """POST rows to Supabase PostgREST as an upsert keyed on the unique index.

    No-op when rows is empty. On 4xx/5xx, prints the response body and exits 2.
    """
    if not rows:
        return
    url = (
        f"{supabase_url.rstrip('/')}/rest/v1/shifts"
        "?on_conflict=shift_date,cohort_number,start_time"
    )
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    resp = requests.post(url, headers=headers, json=rows)
    if resp.status_code >= 400:
        sys.stderr.write(f"Supabase {resp.status_code}: {resp.text}\n")
        sys.exit(2)


def _read_secrets() -> tuple[str, str]:
    """Load .env and return (SUPABASE_URL, SUPABASE_SERVICE_KEY). Exits if missing."""
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if not url:
        sys.stderr.write("Missing SUPABASE_URL in .env\n")
        sys.exit(3)
    if not key:
        sys.stderr.write("Missing SUPABASE_SERVICE_KEY in .env\n")
        sys.exit(3)
    return url, key


def main(argv: list[str] | None = None) -> None:
    from class_titles import CLASS_TITLES

    args = parse_args(argv)

    # Resolve date range.
    if args.from_date:
        from_date, to_date = args.from_date, args.to_date
    else:
        mon, fri = current_week_range()
        from_date, to_date = mon.isoformat(), fri.isoformat()

    # Get workflow JSON.
    if args.input:
        json_path = args.input
    else:
        json_path = run_humanity_workflow(
            from_date=from_date, to_date=to_date, cohorts=args.cohorts
        )
    shifts = load_workflow_json(json_path)

    # Normalize.
    rows: list[dict] = []
    missing_titles: set[int] = set()
    for shift in shifts:
        rows.append(normalize_shift(shift, class_titles=CLASS_TITLES))
        if shift["class_id"] not in CLASS_TITLES or not CLASS_TITLES[shift["class_id"]]:
            missing_titles.add(shift["class_id"])

    # Attach activity-sheet data (unless skipped).
    if not args.skip_activities:
        try:
            attach_activities(rows)
        except RuntimeError as exc:
            sys.stderr.write(
                f"{exc}\n\n"
                "The activity-sheet pull needs the `gws` CLI authenticated.\n"
                "Run `gws auth login` and retry, or pass --skip-activities to "
                "sync shifts only.\n"
            )
            sys.exit(4)

    # Report per-shift.
    for r in rows:
        n_inst = len(r["instructors"])
        acts = r.get("activities") or {}
        n_shared = len(acts.get("shared", []))
        n_scn = sum(len(v) for v in acts.get("perInstructor", {}).values())
        print(
            f"{r['shift_date']} {r['am_pm'].upper():2} "
            f"C{r['cohort_number']} #{r['class_id']} — "
            f"{n_inst} instructor{'s' if n_inst != 1 else ''}, "
            f"{n_shared} shared, {n_scn} scenario{'s' if n_scn != 1 else ''}"
        )

    if missing_titles:
        sys.stderr.write(
            f"warning: class_ids without titles in CLASS_TITLES: "
            f"{sorted(missing_titles)} (stored as NULL)\n"
        )

    if args.dry_run:
        print(f"\nDRY RUN — would upsert {len(rows)} rows. Nothing sent.")
        return

    supabase_url, service_key = _read_secrets()
    upsert_to_supabase(rows, supabase_url=supabase_url, service_key=service_key)
    print(f"\nUpserted {len(rows)} shifts into Supabase.")


if __name__ == "__main__":
    main()
