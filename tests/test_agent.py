"""Check that the starter's file tools stay inside the chosen workspace."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workspace_tools as tools


class WorkspaceToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.override = patch.object(tools, "WORKSPACE", self.workspace)
        self.override.start()
        self.addCleanup(self.override.stop)

    def test_list_and_read_own_text_files(self):
        (self.workspace / "notes.txt").write_text("My research notes", encoding="utf-8")
        (self.workspace / ".gitkeep").touch()
        self.assertEqual(tools.list_files(), ["notes.txt"])
        self.assertEqual(tools.read_file("notes.txt")["content"], "My research notes")

    def test_paths_and_symlinks_cannot_read_outside_workspace(self):
        outside = self.root / "outside.txt"
        outside.write_text("Outside the workspace", encoding="utf-8")
        (self.workspace / "link.txt").symlink_to(outside)
        self.assertEqual(tools.list_files(), [])
        for name in ["../outside.txt", str(outside), "link.txt"]:
            with self.subTest(name=name):
                self.assertIn("error", tools.read_file(name))
                self.assertIn("error", tools.inspect_csv(name))

    def test_large_file_is_explicitly_truncated(self):
        (self.workspace / "long.txt").write_text("a" * 30_000, encoding="utf-8")
        result = tools.read_file("long.txt")
        self.assertEqual(result["content"], "a" * 20_000)
        self.assertTrue(result["truncated"])

    def test_missing_file_returns_feedback_for_agent(self):
        self.assertIn("error", tools.read_file("missing.txt"))

    def test_notes_search_reports_file_and_line(self):
        (self.workspace / "notes.md").write_text("Notes\nLatency matters\n", encoding="utf-8")
        matches = tools.search_notes("LATENCY")["matches"]
        self.assertEqual(matches, [{"filename": "notes.md", "line": 2, "text": "Latency matters"}])

    def test_csv_summary_reports_invalid_and_missing_values(self):
        (self.workspace / "data.csv").write_text("value,label\n1,a\n3,b\n,c\nno,d\nnan,e\ninf,f\n", encoding="utf-8")
        summary = tools.summarise_csv("data.csv", "value")
        self.assertEqual(summary["row_count"], 6)
        self.assertEqual(summary["numeric_count"], 2)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["invalid_count"], 3)
        self.assertEqual(summary["mean"], 2)
        self.assertEqual(summary["median"], 2)
        self.assertAlmostEqual(summary["sample_stddev"], 2 ** 0.5)

    def test_csv_preview_handles_bom_and_quoted_commas(self):
        (self.workspace / "data.csv").write_text('\ufeffname,value\n"a,b",2\n', encoding="utf-8")
        result = tools.inspect_csv("data.csv")
        self.assertEqual(result["columns"], ["name", "value"])
        self.assertEqual(result["preview"], [{"name": "a,b", "value": "2"}])

    def test_malformed_csv_and_unknown_column_report_errors(self):
        (self.workspace / "data.csv").write_text("a,b\n1\n", encoding="utf-8")
        self.assertIn("error", tools.inspect_csv("data.csv"))
        (self.workspace / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        self.assertIn("error", tools.summarise_csv("data.csv", "missing"))

    def test_csv_without_numeric_values_has_no_fake_statistics(self):
        (self.workspace / "data.csv").write_text("a\ntext\n", encoding="utf-8")
        result = tools.summarise_csv("data.csv", "a")
        self.assertIsNone(result["mean"])
        self.assertIsNone(result["sample_stddev"])


if __name__ == "__main__":
    unittest.main()
