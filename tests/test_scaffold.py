import tempfile
import unittest
from pathlib import Path

from writing_project_tools.scaffold import scaffold
from writing_project_tools.assertions_editor import project_root_for


class ScaffoldTests(unittest.TestCase):
    def test_existing_output_register_requires_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outputs").mkdir()
            old = root / "outputs" / "assertions.xlsx"
            old.write_bytes(b"reviewed register")
            for force in (False, True):
                with self.assertRaisesRegex(FileExistsError, "migrate_writing_project"):
                    scaffold(root, force=force)
                self.assertFalse((root / "assertions.xlsx").exists())
                self.assertEqual(old.read_bytes(), b"reviewed register")

    def test_scaffold_does_not_create_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Example Article"
            result = scaffold(root)

            self.assertFalse((root / ".gitignore").exists())
            self.assertNotIn(".gitignore", result["created"])
            self.assertTrue((root / "outputs").is_dir())
            self.assertTrue((root / "sources").is_dir())
            self.assertTrue((root / "sources" / "context.md").is_file())
            self.assertTrue((root / "sources" / "considerations.md").is_file())
            self.assertFalse((root / "context.md").exists())
            self.assertFalse((root / "considerations.md").exists())
            self.assertTrue((root / "assertions.xlsx").is_file())
            self.assertFalse((root / "outputs" / "assertions.xlsx").exists())
            self.assertFalse((root / "assertions.csv").exists())
            self.assertEqual(project_root_for(root / "assertions.xlsx"), root.resolve())


if __name__ == "__main__":
    unittest.main()
