"""Sanity checks on the class_id → title lookup."""
import sys
import unittest
from pathlib import Path

# Make scripts/ importable without packaging it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from class_titles import CLASS_TITLES


class TestClassTitles(unittest.TestCase):
    def test_known_ids_present(self):
        # 912-921 except 917 are the EMS lab class IDs (per matc-generate-week).
        expected_ids = {912, 913, 914, 915, 916, 918, 919, 920, 921}
        self.assertEqual(set(CLASS_TITLES.keys()), expected_ids)

    def test_917_intentionally_absent(self):
        self.assertNotIn(917, CLASS_TITLES)

    def test_values_are_strings(self):
        for cid, title in CLASS_TITLES.items():
            self.assertIsInstance(title, str, f"title for {cid} is not a str")


if __name__ == "__main__":
    unittest.main()
