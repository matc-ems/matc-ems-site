"""Unit tests for scripts/sync_to_supabase.py — pure-function layer."""
import json
import sys
import tempfile
import unittest
from datetime import date, time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_to_supabase as s


class TestParseTime(unittest.TestCase):
    def test_morning(self):
        self.assertEqual(s.parse_time("08:00AM"), time(8, 0))

    def test_late_morning(self):
        self.assertEqual(s.parse_time("11:55AM"), time(11, 55))

    def test_noon(self):
        # 12:00PM is noon -> 12:00 in 24h.
        self.assertEqual(s.parse_time("12:00PM"), time(12, 0))

    def test_afternoon(self):
        self.assertEqual(s.parse_time("01:00PM"), time(13, 0))

    def test_late_afternoon(self):
        self.assertEqual(s.parse_time("04:55PM"), time(16, 55))


class TestLastName(unittest.TestCase):
    def test_standard_humanity_format(self):
        self.assertEqual(s.last_name("Smith, Scott"), "Smith")

    def test_with_extra_whitespace(self):
        self.assertEqual(s.last_name("Olson,  Michael"), "Olson")

    def test_unexpected_format_returns_input(self):
        # No comma -> can't split. Fall back to the whole string so derive_role
        # still has something deterministic to compare against (and will likely
        # produce "Assist", which is the safe default).
        self.assertEqual(s.last_name("Plain Name"), "Plain Name")


class TestDeriveAmPm(unittest.TestCase):
    def test_eight_am_is_am(self):
        self.assertEqual(s.derive_am_pm(time(8, 0)), "am")

    def test_eleven_fifty_five_is_am(self):
        self.assertEqual(s.derive_am_pm(time(11, 55)), "am")

    def test_noon_is_pm(self):
        # Boundary call: 12:00 counts as PM (afternoon session).
        self.assertEqual(s.derive_am_pm(time(12, 0)), "pm")

    def test_one_pm_is_pm(self):
        self.assertEqual(s.derive_am_pm(time(13, 0)), "pm")


class TestDeriveRole(unittest.TestCase):
    def test_lead_when_last_name_matches(self):
        self.assertEqual(s.derive_role("Dean, John", "Dean"), "Lead")

    def test_assist_when_last_name_differs(self):
        self.assertEqual(s.derive_role("Smith, Bob", "Dean"), "Assist")

    def test_assist_when_name_format_is_unexpected(self):
        # last_name("Plain Name") == "Plain Name" which won't equal "Dean".
        self.assertEqual(s.derive_role("Plain Name", "Dean"), "Assist")

    def test_assist_when_cohort_lead_is_none(self):
        self.assertEqual(s.derive_role("Dean, John", None), "Assist")


class TestNormalizeShift(unittest.TestCase):
    SAMPLE_SHIFT = {
        "date": "2026-05-19",
        "starting_time": "08:00AM",
        "ending_time": "11:55AM",
        "instructors": [
            {"name": "Dean, John"},
            {"name": "Cech, Kevin"},
            {"name": "Nickels, Keith"},
        ],
        "class_id": 918,
        "cohort_number": 3,
        "cohort_lead_last_name": "Dean",
        "equipment_list": [],
        "summary": None,
        "activities": [],
        "reference_material": [],
    }

    def test_top_level_fields(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={918: "Trauma"})
        self.assertEqual(row["shift_date"], "2026-05-19")
        self.assertEqual(row["am_pm"], "am")
        self.assertEqual(row["cohort_number"], 3)
        self.assertEqual(row["class_id"], 918)
        self.assertEqual(row["start_time"], "08:00:00")
        self.assertEqual(row["end_time"], "11:55:00")
        self.assertEqual(row["title"], "Trauma")
        self.assertEqual(row["cohort_lead_last_name"], "Dean")

    def test_missing_class_id_in_lookup_yields_null_title(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={})
        self.assertIsNone(row["title"])

    def test_empty_string_title_in_lookup_normalizes_to_null(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={918: ""})
        self.assertIsNone(row["title"])

    def test_instructors_get_roles(self):
        row = s.normalize_shift(self.SAMPLE_SHIFT, class_titles={})
        self.assertEqual(
            row["instructors"],
            [
                {"name": "Dean, John",    "role": "Lead"},
                {"name": "Cech, Kevin",   "role": "Assist"},
                {"name": "Nickels, Keith","role": "Assist"},
            ],
        )

    def test_pm_shift_derives_pm(self):
        pm = {**self.SAMPLE_SHIFT, "starting_time": "01:00PM", "ending_time": "04:55PM"}
        row = s.normalize_shift(pm, class_titles={})
        self.assertEqual(row["am_pm"], "pm")
        self.assertEqual(row["start_time"], "13:00:00")
        self.assertEqual(row["end_time"], "16:55:00")


class TestCurrentWeekRange(unittest.TestCase):
    def test_monday_returns_same_week(self):
        # 2026-05-18 is a Monday.
        mon, fri = s.current_week_range(today=date(2026, 5, 18))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_tuesday_resolves_back_to_monday(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 19))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_friday_returns_same_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 22))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_saturday_resolves_to_just_ended_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 23))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))

    def test_sunday_resolves_to_just_ended_week(self):
        mon, fri = s.current_week_range(today=date(2026, 5, 24))
        self.assertEqual(mon, date(2026, 5, 18))
        self.assertEqual(fri, date(2026, 5, 22))


class TestParseArgs(unittest.TestCase):
    def test_no_args_returns_defaults(self):
        args = s.parse_args([])
        self.assertIsNone(args.from_date)
        self.assertIsNone(args.to_date)
        self.assertEqual(args.cohorts, "1,2,3,4")
        self.assertIsNone(args.input)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.skip_activities)

    def test_date_range(self):
        args = s.parse_args(["--from", "2026-05-18", "--to", "2026-05-22"])
        self.assertEqual(args.from_date, "2026-05-18")
        self.assertEqual(args.to_date, "2026-05-22")

    def test_cohorts_subset(self):
        args = s.parse_args(["--cohorts", "1,3"])
        self.assertEqual(args.cohorts, "1,3")

    def test_input_path(self):
        args = s.parse_args(["--input", "/tmp/shifts.json"])
        self.assertEqual(args.input, "/tmp/shifts.json")

    def test_dry_run(self):
        args = s.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)

    def test_skip_activities_defaults_false(self):
        self.assertFalse(s.parse_args([]).skip_activities)

    def test_skip_activities_flag(self):
        self.assertTrue(s.parse_args(["--skip-activities"]).skip_activities)

    def test_from_without_to_errors(self):
        with self.assertRaises(SystemExit):
            s.parse_args(["--from", "2026-05-18"])

    def test_to_without_from_errors(self):
        with self.assertRaises(SystemExit):
            s.parse_args(["--to", "2026-05-22"])


class TestRunHumanityWorkflow(unittest.TestCase):
    def test_calls_subprocess_with_expected_args(self):
        fake_stdout = "/tmp/fake-shifts.json\n"
        with patch.object(s.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout=fake_stdout, returncode=0)
            path = s.run_humanity_workflow(
                from_date="2026-05-18", to_date="2026-05-22", cohorts="1,2,3,4"
            )
        self.assertEqual(path, "/tmp/fake-shifts.json")
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertIn("--workflow", cmd)
        self.assertIn("--from", cmd)
        self.assertIn("2026-05-18", cmd)
        self.assertIn("--to", cmd)
        self.assertIn("2026-05-22", cmd)
        self.assertIn("--cohorts", cmd)
        self.assertIn("1,2,3,4", cmd)

    def test_nonzero_exit_raises(self):
        with patch.object(s.subprocess, "run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=1, stderr="boom")
            with self.assertRaises(SystemExit):
                s.run_humanity_workflow(
                    from_date="2026-05-18", to_date="2026-05-22", cohorts="1"
                )

    def test_load_workflow_json_reads_file(self):
        sample = [{"date": "2026-05-18", "class_id": 918}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            path = f.name
        loaded = s.load_workflow_json(path)
        self.assertEqual(loaded, sample)


class TestUpsertToSupabase(unittest.TestCase):
    SAMPLE_ROWS = [
        {
            "shift_date": "2026-05-18", "am_pm": "pm", "cohort_number": 3,
            "class_id": 918, "start_time": "13:00:00", "end_time": "16:55:00",
            "title": None, "instructors": [{"name": "Dean, John", "role": "Lead"}],
            "cohort_lead_last_name": "Dean",
        }
    ]

    def test_posts_to_correct_url(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        args, kwargs = mock_post.call_args
        self.assertEqual(
            args[0],
            "https://abc.supabase.co/rest/v1/shifts"
            "?on_conflict=shift_date,cohort_number,start_time",
        )

    def test_sends_correct_headers(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        _, kwargs = mock_post.call_args
        headers = kwargs["headers"]
        self.assertEqual(headers["apikey"], "svc-xyz")
        self.assertEqual(headers["Authorization"], "Bearer svc-xyz")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertIn("resolution=merge-duplicates", headers["Prefer"])

    def test_sends_rows_as_json(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(status_code=201, text="[]")
            s.upsert_to_supabase(
                self.SAMPLE_ROWS,
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], self.SAMPLE_ROWS)

    def test_4xx_raises_systemexit(self):
        with patch.object(s.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400, text='{"message":"bad row"}'
            )
            with self.assertRaises(SystemExit):
                s.upsert_to_supabase(
                    self.SAMPLE_ROWS,
                    supabase_url="https://abc.supabase.co",
                    service_key="svc-xyz",
                )

    def test_empty_rows_noop(self):
        with patch.object(s.requests, "post") as mock_post:
            s.upsert_to_supabase(
                [],
                supabase_url="https://abc.supabase.co",
                service_key="svc-xyz",
            )
        mock_post.assert_not_called()


class TestAttachActivities(unittest.TestCase):
    HEADER = [
        "date", "start_time", "end_time", "activity_type", "activity_id",
        "activity_title", "activity_description", "scenario_slugs",
        "scenario_links", "pp_skill_links", "activity_links",
    ]

    def _row(self, sheet_date, start, slugs=""):
        # 11-column row: date(0), start_time(1), scenario_slugs(7).
        r = [""] * 11
        r[0] = sheet_date
        r[1] = start
        r[7] = slugs
        return r

    def _shift_row(self, cohort, shift_date, am_pm):
        return {
            "shift_date": shift_date, "am_pm": am_pm, "cohort_number": cohort,
            "class_id": 916, "instructors": [{"name": "A", "role": "Lead"}],
        }

    def test_attaches_built_activities(self):
        tab = [self.HEADER, self._row("05-20-26", "8:00", "scn1")]
        rows = [self._shift_row(3, "2026-05-20", "am")]
        s.attach_activities(rows, get_values=lambda c: tab, resolve=lambda u: u)
        self.assertEqual(
            rows[0]["activities"]["perInstructor"],
            {"A": [{"label": "scn1",
                    "href": "https://matc-ems.github.io/scenarios/main-lab/scn1"}]},
        )

    def test_old_format_tab_yields_empty(self):
        old_tab = [["Class Date", "Start Time", "End Time", "Room", "Topic"]]
        rows = [self._shift_row(1, "2026-05-20", "am")]
        s.attach_activities(rows, get_values=lambda c: old_tab,
                            resolve=lambda u: u)
        self.assertEqual(rows[0]["activities"],
                         {"perInstructor": {}, "shared": []})

    def test_tab_fetched_once_per_cohort(self):
        calls = []

        def fake_get(cohort):
            calls.append(cohort)
            return [self.HEADER]

        rows = [self._shift_row(3, "2026-05-20", "am"),
                self._shift_row(3, "2026-05-20", "pm")]
        s.attach_activities(rows, get_values=fake_get, resolve=lambda u: u)
        self.assertEqual(calls, [3])  # one fetch despite two cohort-3 shifts


if __name__ == "__main__":
    unittest.main()
