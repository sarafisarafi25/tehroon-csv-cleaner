import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from app import clean_file


class CleanerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rows, name="input.csv", encoding="utf-8-sig", delimiter=","):
        path = self.root / name
        with path.open("w", encoding=encoding, newline="") as handle:
            csv.writer(handle, delimiter=delimiter).writerows(rows)
        return path

    def test_text_integrity_reconciliation_and_source_preservation(self):
        source = self.write([[" id ", "note"], ["001", " علی "], ["001", "علی"], [], ["", " "], ["002", "first\nsecond"], ["003", "<script>alert(1)</script>"]])
        before = source.read_bytes()
        folder, stats = clean_file(source)
        with (folder / "cleaned.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows, [["id", "note"], ["001", "علی"], ["002", "first\nsecond"], ["003", "<script>alert(1)</script>"]])
        self.assertEqual(stats["input_rows"], stats["output_rows"] + stats["removed_empty_rows"] + stats["removed_duplicate_rows"])
        self.assertEqual(stats["removed_empty_rows"], 2)
        self.assertEqual(stats["removed_duplicate_rows"], 1)
        self.assertEqual(before, source.read_bytes())
        self.assertEqual(stats["source_sha256"], hashlib.sha256(before).hexdigest())
        self.assertNotIn("<script>", (folder / "report.html").read_text())
        with (folder / "removed_rows.csv").open(encoding="utf-8-sig", newline="") as handle:
            self.assertEqual(len(list(csv.reader(handle))), 4)

    def test_options_and_repeat_runs(self):
        source = self.write([["id", "note"], ["001", " x "], ["001", " x "]])
        a, stats = clean_file(source, trim=False, deduplicate=False)
        b, _ = clean_file(source)
        self.assertNotEqual(a, b)
        self.assertEqual(stats["output_rows"], 2)
        self.assertEqual(stats["trimmed_cells"], 0)
        self.assertIn(" x ", (a / "cleaned.csv").read_text(encoding="utf-8-sig"))

    def test_ragged_or_invalid_header_stops_without_outputs(self):
        for rows in [[["id", "note"], ["001", "x", "extra"]], [["id", " id "], ["1", "2"]]]:
            with self.subTest(rows=rows):
                source = self.write(rows)
                with self.assertRaises(ValueError):
                    clean_file(source)
                self.assertEqual(list(self.root.glob("*-cleaned-*")), [])

    def test_explicit_legacy_encoding_semicolon_and_unicode_bom(self):
        source = self.write([["id", "şehir"], ["001", "İzmir"]], encoding="cp1254", delimiter=";")
        folder, stats = clean_file(source, encoding="cp1254", delimiter="semicolon")
        self.assertEqual(stats["output_rows"], 1)
        self.assertIn("İzmir", (folder / "cleaned.csv").read_text(encoding="utf-8-sig"))
        source = self.write([["id", "note"], ["001", "سلام"]], name="utf16.csv", encoding="utf-16")
        folder, _ = clean_file(source)
        self.assertIn("سلام", (folder / "cleaned.csv").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
