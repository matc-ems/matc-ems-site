"""Unit tests for scripts/sync_to_supabase.py — pure-function layer."""
import sys
import unittest
from datetime import time
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


if __name__ == "__main__":
    unittest.main()
