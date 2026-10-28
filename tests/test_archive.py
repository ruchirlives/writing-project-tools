import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from writing_project_tools.archive import archive_project
from writing_project_tools.scaffold import scaffold


class ArchiveTests(unittest.TestCase):
    def test_archives_sources_and_removes_working_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Example Project"
            scaffold(root)
            (root / "sources" / "emails").mkdir()
            (root / "sources" / "emails" / "note.eml").write_bytes(b"email")
            (root / "sources" / "report.pdf").write_bytes(b"pdf")
            (root / "outputs" / "final.docx").write_bytes(b"finished")
            (root / "custom.dat").write_bytes(b"unrelated")

            result = archive_project(root)

            self.assertFalse((root / "sources").exists())
            self.assertFalse((root / "context.md").exists())
            self.assertFalse((root / "example-project-plan.md").exists())
            self.assertFalse((root / "docx_sources.csv").exists())
            self.assertFalse((root / "README.md").exists())
            self.assertTrue((root / "assertions.xlsx").exists())
            self.assertEqual((root / "outputs" / "final.docx").read_bytes(), b"finished")
            self.assertEqual((root / "custom.dat").read_bytes(), b"unrelated")
            self.assertIn("custom.dat", result["kept_other_entries"])
            with ZipFile(root / "sources.zip") as zipped:
                self.assertIn("sources/context.md", zipped.namelist())
                self.assertIn("sources/considerations.md", zipped.namelist())
                self.assertEqual(zipped.read("sources/emails/note.eml"), b"email")
                self.assertEqual(zipped.read("sources/report.pdf"), b"pdf")

            second = archive_project(root)
            self.assertEqual(second["deleted_intermediate_files"], [])

    def test_existing_archive_prevents_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sources").mkdir()
            (root / "sources" / "note.eml").write_bytes(b"email")
            (root / "sources.zip").write_bytes(b"old archive")
            (root / "context.md").write_text("draft", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                archive_project(root)

            self.assertTrue((root / "sources" / "note.eml").exists())
            self.assertTrue((root / "context.md").exists())
            self.assertEqual((root / "sources.zip").read_bytes(), b"old archive")
