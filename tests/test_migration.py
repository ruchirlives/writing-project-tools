import csv
import tempfile
import unittest
from pathlib import Path

from writing_project_tools.migration import migrate_project
from writing_project_tools.assertions_store import read_assertions


class MigrationTests(unittest.TestCase):
    def test_moves_output_workbook_without_rewriting_and_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outputs").mkdir()
            old = root / "outputs" / "assertions.xlsx"
            # Relocation must preserve the complete file, including custom sheets/styles.
            original = b"workbook bytes that must not be regenerated"
            old.write_bytes(original)
            (root / "README.md").write_text('edit-assertions --workbook "outputs/assertions.xlsx"', encoding="utf-8")

            result = migrate_project(root)

            self.assertTrue(result["assertions_migrated"])
            self.assertEqual((root / "assertions.xlsx").read_bytes(), original)
            self.assertEqual((root / ".writing-project-migration-backup" / "outputs" / "assertions.xlsx").read_bytes(), original)
            self.assertFalse(old.exists())
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), 'edit-assertions --workbook "assertions.xlsx"')
            self.assertIn("outputs/assertions.xlsx", (root / ".writing-project-migration-backup" / "README.md").read_text(encoding="utf-8"))
            second = migrate_project(root)
            self.assertFalse(second["assertions_migrated"])
            self.assertFalse(second["moved_deliverables"])
            self.assertEqual((root / "assertions.xlsx").read_bytes(), original)

    def test_assertions_collisions_leave_all_files_unchanged(self) -> None:
        for legacy in ("outputs/assertions.xlsx", "outputs/assertions.csv", "assertions.csv"):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "assertions.xlsx").write_bytes(b"reviewed root workbook")
                old = root / legacy
                old.parent.mkdir(exist_ok=True)
                old.write_bytes(b"legacy register")
                with self.assertRaises(FileExistsError):
                    migrate_project(root)
                self.assertEqual((root / "assertions.xlsx").read_bytes(), b"reviewed root workbook")
                self.assertEqual(old.read_bytes(), b"legacy register")
                self.assertFalse((root / ".writing-project-migration-backup").exists())

    def test_consolidates_legacy_files_and_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Peatland Action"
            root.mkdir()
            (root / "source-notes.md").write_text("# Notes\n\nEvidence A\n", encoding="utf-8")
            (root / "instructions_for_authors.md").write_text("# Brief\n\nAudience A\n", encoding="utf-8")
            (root / "colleagues.md").write_text("# Colleagues\n\nReviewer A\n", encoding="utf-8")
            (root / "peatland-action-outline.md").write_text("# Outline\n\n- Main point A\n", encoding="utf-8")
            (root / "context.md").write_text("# Context\n\nExisting context\n", encoding="utf-8")
            (root / ".gitignore").write_text("*.docx\n", encoding="utf-8")
            (root / "assertions.csv").write_text(
                "include,id,section,assertion,user_edit,status,evidence_or_check\n"
                "FALSE,A1,Intro,Exact intended wording,Reviewed wording,verified,Source A\n",
                encoding="utf-8",
            )
            (root / "docx_sources.csv").write_text(
                "source,title,subject,output,author\n"
                "peatland-action-plan.md,Plan,Plan,docs/plan.docx,Author\n"
                "peatland-action-outline.md,Outline,Outline,docs/outline.docx,Author\n",
                encoding="utf-8",
            )
            (root / "docs").mkdir()
            (root / "docs" / "plan.docx").write_bytes(b"old word document")
            (root / "docs" / "table.xlsx").write_bytes(b"old spreadsheet")
            (root / "report.html").write_text("<h1>Report</h1>", encoding="utf-8")
            (root / "figures.csv").write_text("label,value\nA,1\n", encoding="utf-8")
            (root / "research.pdf").write_bytes(b"source pdf")
            (root / "correspondence.eml").write_bytes(b"email source")
            (root / "input").mkdir()
            (root / "input" / "notes.docx").write_bytes(b"input document")

            result = migrate_project(root)

            self.assertEqual(len(result["archived_legacy_files"]), 5)
            self.assertIn(".gitignore", result["archived_legacy_files"])
            self.assertFalse((root / ".gitignore").exists())
            self.assertEqual(
                (root / ".writing-project-migration-backup" / ".gitignore").read_text(encoding="utf-8"),
                "*.docx\n",
            )
            self.assertFalse((root / "peatland-action-outline.md").exists())
            self.assertIn("Existing context", (root / "context.md").read_text(encoding="utf-8"))
            self.assertIn("Evidence A", (root / "context.md").read_text(encoding="utf-8"))
            self.assertIn("Audience A", (root / "drafting-instructions.md").read_text(encoding="utf-8"))
            self.assertIn("Reviewer A", (root / "considerations.md").read_text(encoding="utf-8"))
            self.assertIn("Main point A", (root / "peatland-action-plan.md").read_text(encoding="utf-8"))
            row = read_assertions(root / "assertions.xlsx")[0]
            self.assertEqual(row["precis"], "")
            self.assertEqual(row["assertion"], "Exact intended wording")
            self.assertEqual(row["include"], "FALSE")
            self.assertEqual(row["user_edit"], "Reviewed wording")
            config = (root / "docx_sources.csv").read_text(encoding="utf-8")
            self.assertIn("outputs/plan.docx", config)
            self.assertNotIn("outline.md", config)
            self.assertTrue((root / ".writing-project-migration-backup" / "assertions.csv").exists())
            self.assertFalse((root / "assertions.csv").exists())
            self.assertFalse((root / "outputs" / "assertions.csv").exists())
            self.assertFalse((root / "docs").exists())
            self.assertEqual((root / "outputs" / "plan.docx").read_bytes(), b"old word document")
            self.assertEqual((root / "outputs" / "table.xlsx").read_bytes(), b"old spreadsheet")
            self.assertTrue((root / "outputs" / "report.html").exists())
            self.assertTrue((root / "outputs" / "figures.csv").exists())
            self.assertEqual(len(result["moved_deliverables"]), 4)
            self.assertEqual((root / "sources" / "research.pdf").read_bytes(), b"source pdf")
            self.assertEqual((root / "sources" / "correspondence.eml").read_bytes(), b"email source")
            self.assertEqual((root / "sources" / "notes.docx").read_bytes(), b"input document")
            self.assertFalse((root / "input").exists())
            self.assertEqual(len(result["moved_sources"]), 3)

            second = migrate_project(root)
            self.assertFalse(second["updated"])
            self.assertFalse(second["archived_legacy_files"])
            self.assertFalse(second["moved_deliverables"])
            self.assertFalse(second["moved_sources"])
            self.assertEqual((root / "context.md").read_text(encoding="utf-8").count("Evidence A"), 1)

    def test_collision_does_not_modify_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "outputs").mkdir()
            (root / "docs" / "report.docx").write_bytes(b"old")
            (root / "outputs" / "report.docx").write_bytes(b"new")
            (root / "assertions.csv").write_text("include,id,section,assertion,user_edit,status,evidence_or_check\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                migrate_project(root)

            self.assertEqual((root / "docs" / "report.docx").read_bytes(), b"old")
            self.assertEqual((root / "outputs" / "report.docx").read_bytes(), b"new")
            self.assertTrue((root / "assertions.csv").exists())

    def test_converts_assertions_csv_already_in_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outputs").mkdir()
            old_csv = root / "outputs" / "assertions.csv"
            old_csv.write_text(
                "include,id,section,precis,assertion,user_edit,status,evidence_or_check\n"
                "TRUE,A2,Main,Short label,Full intended wording,,verified,Source B\n",
                encoding="utf-8",
            )

            result = migrate_project(root)

            self.assertFalse(old_csv.exists())
            self.assertEqual(read_assertions(root / "assertions.xlsx")[0]["precis"], "Short label")
            self.assertTrue((root / ".writing-project-migration-backup" / "outputs" / "assertions.csv").exists())
            self.assertIn("assertions.xlsx", result["updated"])

    def test_source_collision_does_not_move_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sources").mkdir()
            (root / "brief.pdf").write_bytes(b"new input")
            (root / "sources" / "brief.pdf").write_bytes(b"existing input")

            with self.assertRaises(FileExistsError):
                migrate_project(root)

            self.assertEqual((root / "brief.pdf").read_bytes(), b"new input")
            self.assertEqual((root / "sources" / "brief.pdf").read_bytes(), b"existing input")


if __name__ == "__main__":
    unittest.main()
