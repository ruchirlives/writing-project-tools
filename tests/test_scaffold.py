import tempfile
import unittest
from pathlib import Path

from writing_project_tools.scaffold import scaffold
from writing_project_tools.assertions_editor import project_root_for


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_does_not_create_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Example Article"
            result = scaffold(root)

            self.assertFalse((root / ".gitignore").exists())
            self.assertNotIn(".gitignore", result["created"])
            self.assertTrue((root / "outputs").is_dir())
            self.assertTrue((root / "sources").is_dir())
            self.assertTrue((root / "outputs" / "assertions.xlsx").is_file())
            self.assertFalse((root / "assertions.csv").exists())
            self.assertEqual(project_root_for(root / "outputs" / "assertions.xlsx"), root.resolve())


if __name__ == "__main__":
    unittest.main()
