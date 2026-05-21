"""Unit tests for scripts/sheet_activities.py."""
import json
import sys
import unittest
from datetime import date, time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sheet_activities as sa


class TestCell(unittest.TestCase):
    def test_returns_stripped_value(self):
        self.assertEqual(sa.cell(["  hi  ", "x"], 0), "hi")

    def test_short_row_returns_empty(self):
        self.assertEqual(sa.cell(["a"], 5), "")


class TestParseSheetDate(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(sa.parse_sheet_date("01-21-26"), date(2026, 1, 21))

    def test_no_leading_zeros(self):
        self.assertEqual(sa.parse_sheet_date("1-5-26"), date(2026, 1, 5))

    def test_bad_value_raises(self):
        with self.assertRaises(ValueError):
            sa.parse_sheet_date("not-a-date")


class TestParseClock(unittest.TestCase):
    def test_morning_no_leading_zero(self):
        self.assertEqual(sa.parse_clock("8:00"), time(8, 0))

    def test_afternoon(self):
        self.assertEqual(sa.parse_clock("13:30"), time(13, 30))

    def test_bad_value_raises(self):
        with self.assertRaises(ValueError):
            sa.parse_clock("noon")


class TestDeriveAmPm(unittest.TestCase):
    def test_before_noon_is_am(self):
        self.assertEqual(sa.derive_am_pm(time(11, 59)), "am")

    def test_noon_is_pm(self):
        self.assertEqual(sa.derive_am_pm(time(12, 0)), "pm")


class TestSplitCell(unittest.TestCase):
    def test_splits_and_trims(self):
        self.assertEqual(sa.split_cell("a, b ,c"), ["a", "b", "c"])

    def test_drops_empties(self):
        self.assertEqual(sa.split_cell("a, ,,b"), ["a", "b"])

    def test_blank_is_empty_list(self):
        self.assertEqual(sa.split_cell(""), [])


class TestIsNewFormat(unittest.TestCase):
    def test_new_header(self):
        self.assertTrue(sa.is_new_format(list(sa.EXPECTED_HEADER)))

    def test_old_cohort1_header(self):
        old = ["Class Date", "Start Time", "End Time", "Room", "Topic"]
        self.assertFalse(sa.is_new_format(old))

    def test_empty_header(self):
        self.assertFalse(sa.is_new_format([]))


class TestResolveDocTitle(unittest.TestCase):
    def test_non_drive_url_returns_url(self):
        self.assertEqual(sa.resolve_doc_title("https://example.com/x"),
                         "https://example.com/x")

    def test_resolves_doc_title(self):
        url = "https://docs.google.com/document/d/ABC123/edit"
        fake = MagicMock(returncode=0, stdout='{"name": "My Doc"}')
        with patch.object(sa.subprocess, "run", return_value=fake):
            self.assertEqual(sa.resolve_doc_title(url), "My Doc")

    def test_gws_failure_falls_back_to_url(self):
        url = "https://docs.google.com/document/d/ABC123/edit"
        fake = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch.object(sa.subprocess, "run", return_value=fake):
            self.assertEqual(sa.resolve_doc_title(url), url)


class TestEmptyActivities(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(sa.empty_activities(),
                         {"perInstructor": {}, "shared": []})


class TestRoundRobin(unittest.TestCase):
    def test_six_items_three_instructors(self):
        # per = 2: I0 gets items 0,3 · I1 gets 1,4 · I2 gets 2,5.
        self.assertEqual(sa.round_robin([0, 1, 2, 3, 4, 5], 3),
                         [[0, 3], [1, 4], [2, 5]])

    def test_six_items_four_instructors_drops_remainder(self):
        # per = 1: each gets one item; items 4 and 5 are dropped.
        self.assertEqual(sa.round_robin([0, 1, 2, 3, 4, 5], 4),
                         [[0], [1], [2], [3]])

    def test_fewer_items_than_instructors_drops_all(self):
        self.assertEqual(sa.round_robin([0, 1], 3), [[], [], []])

    def test_zero_instructors_returns_empty(self):
        self.assertEqual(sa.round_robin([0, 1, 2], 0), [])

    def test_empty_pool(self):
        self.assertEqual(sa.round_robin([], 3), [[], [], []])


if __name__ == "__main__":
    unittest.main()
