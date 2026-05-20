"""Unit tests for scripts/sync_to_supabase.py — pure-function layer."""
import sys
import unittest
from datetime import date, time
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
