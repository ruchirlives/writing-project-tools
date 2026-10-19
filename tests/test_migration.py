import csv
import tempfile
import unittest
from pathlib import Path

from writing_project_tools.migration import migrate_project


class MigrationTests(unittest.TestCase):
    def test_consolidates_legacy_files_and_is_repeatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Peatland Action"
            root.mkdir()
            (root / "source-notes.md").write_text("# Notes\n\nEvidence A\n", encoding="utf-8")
            (root / "instructions_for_authors.md").write_text("# Brief\n\nAudience A\n", encoding="utf-8")
            (root / "colleagues.md").write_text("# Colleagues\n\nReviewer A\n", encoding="utf-8")
            (root / "peatland-action-outline.md").write_text("# Outline\n\n- Main point A\n", encoding="utf-8")
            (root / "context.md").write_text("# Context\n\nExisting context\n", encoding="utf-8")
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

            result = migrate_project(root)

            self.assertEqual(len(result["archived_legacy_files"]), 4)
            self.assertFalse((root / "peatland-action-outline.md").exists())
            self.assertIn("Existing context", (root / "context.md").read_text(encoding="utf-8"))
            self.assertIn("Evidence A", (root / "context.md").read_text(encoding="utf-8"))
            self.assertIn("Audience A", (root / "drafting-instructions.md").read_text(encoding="utf-8"))
            self.assertIn("Reviewer A", (root / "considerations.md").read_text(encoding="utf-8"))
            self.assertIn("Main point A", (root / "peatland-action-plan.md").read_text(encoding="utf-8"))
            with (root / "assertions.csv").open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["precis"], "")
            self.assertEqual(row["assertion"], "Exact intended wording")
            self.assertEqual(row["include"], "FALSE")
            self.assertEqual(row["user_edit"], "Reviewed wording")
            config = (root / "docx_sources.csv").read_text(encoding="utf-8")
            self.assertIn("outputs/plan.docx", config)
            self.assertNotIn("outline.md", config)
            self.assertTrue((root / ".writing-project-migration-backup" / "assertions.csv").exists())

            second = migrate_project(root)
            self.assertFalse(second["updated"])
            self.assertFalse(second["archived_legacy_files"])
            self.assertEqual((root / "context.md").read_text(encoding="utf-8").count("Evidence A"), 1)


if __name__ == "__main__":
    unittest.main()
