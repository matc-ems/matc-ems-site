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


class TestGwsGetValues(unittest.TestCase):
    def test_returns_values_on_success(self):
        payload = '{"values": [["date", "x"], ["01-21-26", "y"]]}'
        fake = MagicMock(returncode=0, stdout=payload)
        with patch.object(sa.subprocess, "run", return_value=fake):
            rows = sa.gws_get_values(3)
        self.assertEqual(rows, [["date", "x"], ["01-21-26", "y"]])

    def test_requests_the_cohort_tab(self):
        fake = MagicMock(returncode=0, stdout='{"values": []}')
        with patch.object(sa.subprocess, "run", return_value=fake) as mock_run:
            sa.gws_get_values(3)
        cmd = mock_run.call_args[0][0]
        params = json.loads(cmd[cmd.index("--params") + 1])
        self.assertEqual(params["range"], "'Cohort 3'!A1:N1000")

    def test_nonzero_exit_raises_runtimeerror(self):
        fake = MagicMock(returncode=1, stdout="", stderr="auth expired")
        with patch.object(sa.subprocess, "run", return_value=fake):
            with self.assertRaises(RuntimeError):
                sa.gws_get_values(3)


class TestBuildActivities(unittest.TestCase):
    # Identity resolver so tests are deterministic and gws-free.
    RESOLVE = staticmethod(lambda url: url)

    @staticmethod
    def row(date="01-21-26", start="8:00", title="", slugs="", scen_links="",
            pp_links="", act_links=""):
        # 14-column row (A–N); only the columns build_activities reads matter.
        r = [""] * 14
        r[sa.COL_DATE] = date
        r[sa.COL_START] = start
        r[sa.COL_TITLE] = title
        r[sa.COL_SCENARIO_SLUGS] = slugs
        r[sa.COL_SCENARIO_LINKS] = scen_links
        r[sa.COL_PP_SKILL_LINKS] = pp_links
        r[sa.COL_ACTIVITY_LINKS] = act_links
        return r

    def test_scenarios_round_robin_per_instructor(self):
        rows = [self.row(start="8:00", slugs="s1, s2, s3, s4")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}, {"name": "B"}],
                                  resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "s1", "href": sa.SLUG_BASE_URL + "s1"},
                  {"label": "s3", "href": sa.SLUG_BASE_URL + "s3"}],
            "B": [{"label": "s2", "href": sa.SLUG_BASE_URL + "s2"},
                  {"label": "s4", "href": sa.SLUG_BASE_URL + "s4"}],
        })
        self.assertEqual(out["shared"], [])

    def test_shared_groups_by_activity_title(self):
        rows = [self.row(start="9:00", title="XABC Cards",
                         act_links="http://u1, http://u2")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["shared"], [
            {"name": "XABC Cards",
             "links": [{"label": "http://u1", "href": "http://u1"},
                       {"label": "http://u2", "href": "http://u2"}]}])
        self.assertEqual(out["perInstructor"], {})

    def test_am_pm_split(self):
        rows = [self.row(start="8:00", slugs="morning"),
                self.row(start="13:00", slugs="afternoon")]
        out = sa.build_activities(rows, date(2026, 1, 21), "pm",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "afternoon",
                   "href": sa.SLUG_BASE_URL + "afternoon"}]})

    def test_no_matching_rows_is_empty(self):
        rows = [self.row(date="02-02-26", slugs="x")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out, {"perInstructor": {}, "shared": []})

    def test_partially_filled_rows(self):
        # Title but no links -> no shared group. Links but blank title ->
        # group with name "".
        rows = [self.row(start="8:00", title="Just a title"),
                self.row(start="9:00", title="", pp_links="http://only")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["shared"], [
            {"name": "", "links": [{"label": "http://only",
                                    "href": "http://only"}]}])
        self.assertEqual(out["perInstructor"], {})

    def test_unparseable_row_is_skipped(self):
        rows = [self.row(date="bad-date", start="8:00", slugs="skipme"),
                self.row(date="01-21-26", start="8:00", slugs="keep")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am",
                                  [{"name": "A"}], resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {
            "A": [{"label": "keep", "href": sa.SLUG_BASE_URL + "keep"}]})

    def test_zero_instructors_drops_scenarios(self):
        rows = [self.row(start="8:00", slugs="s1, s2")]
        out = sa.build_activities(rows, date(2026, 1, 21), "am", [],
                                  resolve=self.RESOLVE)
        self.assertEqual(out["perInstructor"], {})


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
