from copy import deepcopy
import json
from pathlib import Path
import re
import tempfile
import unittest

from writing_project_tools.editable_table import generate_table


class EditableTableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.columns = [{"key": "topic", "label": "Topic"}, {"key": "status", "label": "State", "type": "select", "options": ["Not agreed", "Complete"]}]
        self.rows = [{"id": "ONE", "values": {"topic": "Fictional example"}, "sourceIds": ["S1"]}]
        self.sources = [{"id": "S1", "title": "Synthetic note", "excerpt": "An example only."}]

    def generate(self, **kwargs):
        return generate_table(self.root, kwargs.pop("title", "Example"), kwargs.pop("columns", self.columns), kwargs.pop("rows", self.rows), kwargs.pop("sources", self.sources), **kwargs)

    def test_pair_matches_schema_and_preserves_original_values(self):
        result = self.generate()
        data = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
        html = Path(result["html"]).read_text(encoding="utf-8")
        embedded = re.search(r'<script type="application/json" id="initial">(.*?)</script>', html, re.S)
        self.assertEqual(json.loads(embedded[1]), data)
        self.assertEqual(data["rows"][0]["values"], {"topic": "Fictional example", "status": "Not agreed"})
        self.assertEqual(data["rows"][0]["original"], data["rows"][0]["values"])
        self.assertEqual(data["rows"][0]["sourceIds"], ["S1"])
        self.assertEqual(Path(result["html"]).parent, self.root / "outputs")
        self.assertEqual(self.columns[0], {"key": "topic", "label": "Topic"})

    def test_unrelated_fields_and_empty_register(self):
        result = self.generate(title="Inventory", columns=[{"key": "item", "label": "Item"}, {"key": "count", "label": "Count", "type": "number"}, {"key": "due", "label": "Due", "type": "date"}], rows=[], sources=[])
        self.assertEqual(result["columns"], 3)
        self.assertEqual(result["rows"], 0)

    def test_numeric_and_date_values_will_not_be_silently_lost_by_inputs(self):
        cols = [{"key": "amount", "label": "Amount", "type": "number"}, {"key": "due", "label": "Due", "type": "date"}]
        result = self.generate(columns=cols, rows=[{"values": {"amount": "12.5", "due": "2026-10-29"}}], sources=[])
        self.assertEqual(json.loads(Path(result["json"]).read_text())["rows"][0]["values"]["amount"], "12.5")
        for values in [{"amount": "unknown"}, {"amount": "1e999"}, {"due": "2026-02-30"}, {"due": "29/10/2026"}]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.generate(columns=cols, rows=[{"values": values}], sources=[], output="outputs/invalid.html")

    def test_source_ranges_are_exact_and_links_encode_spaces(self):
        (self.root / "notes and sources.md").write_text("Heading\nFirst fact\nSecond fact\n", encoding="utf-8")
        sources = [{"id": "S1", "title": "Notes", "path": "notes and sources.md", "lineStart": 2, "lineEnd": 3}]
        result = self.generate(sources=sources)
        source = json.loads(Path(result["json"]).read_text(encoding="utf-8"))["sources"][0]
        self.assertEqual(source["excerpt"], "First fact\nSecond fact")
        self.assertEqual(source["href"], "../notes%20and%20sources.md")

    def test_script_injection_is_only_inert_json(self):
        text = '</script><script>alert("x")</script>&'
        result = self.generate(title=text, rows=[{"values": {"topic": text}, "sourceIds": []}])
        html = Path(result["html"]).read_text(encoding="utf-8")
        self.assertNotIn(text, html)
        self.assertEqual(json.loads(Path(result["json"]).read_text(encoding="utf-8"))["title"], text)

    def test_refuses_either_existing_output_without_mutation(self):
        (self.root / "outputs").mkdir()
        (self.root / "outputs/editable-table.json").write_text("Keep edited data", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.generate()
        self.assertFalse((self.root / "outputs/editable-table.html").exists())
        self.assertEqual((self.root / "outputs/editable-table.json").read_text(), "Keep edited data")

    def test_explicit_overwrite_backs_up_both_files(self):
        first = self.generate()
        originals = {p: Path(first[p]).read_bytes() for p in ["html", "json"]}
        second = self.generate(overwrite=True, title="Changed title")
        self.assertEqual(len(second["backups"]), 2)
        self.assertEqual({Path(p).suffix: Path(p).read_bytes() for p in second["backups"]}, {".html": originals["html"], ".json": originals["json"]})

    def test_invalid_data_does_not_overwrite_existing_pair(self):
        result = self.generate()
        before = Path(result["json"]).read_bytes()
        with self.assertRaises(ValueError):
            self.generate(rows=[{"values": {"status": "Unknown"}}], overwrite=True)
        self.assertEqual(Path(result["json"]).read_bytes(), before)

    def test_rejects_escape_and_duplicate_identifiers(self):
        for output in ["../escape.html", str(self.root.parent / "escape.html")]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.generate(output=output)
        with self.assertRaises(ValueError):
            self.generate(columns=self.columns + [deepcopy(self.columns[0])])
        with self.assertRaises(ValueError):
            self.generate(rows=self.rows + self.rows)
        with self.assertRaises(ValueError):
            self.generate(rows=[{"values": {}, "sourceIds": ["missing"]}])

    def test_rejects_invalid_source_ranges_and_source_overwrite(self):
        (self.root / "note.md").write_text("One line", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.generate(sources=[{"id": "S1", "path": "note.md", "lineStart": 1, "lineEnd": 2}])
        (self.root / "outputs").mkdir(exist_ok=True)
        (self.root / "outputs/editable-table.json").write_text("Source", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.generate(sources=[{"id": "S1", "path": "outputs/editable-table.json"}], overwrite=True)
        self.assertEqual((self.root / "outputs/editable-table.json").read_text(), "Source")

    def test_mcp_wrapper_exposes_generator(self):
        from writing_project_tools.mcp_server import generate_editable_table, get_workflow_summary
        result = generate_editable_table(str(self.root), "Example", self.columns, self.rows, self.sources)
        self.assertTrue(Path(result["json"]).is_file())
        self.assertIn("generate_editable_table", get_workflow_summary()["helpers"])


if __name__ == "__main__":
    unittest.main()
