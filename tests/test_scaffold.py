import tempfile
import unittest
from pathlib import Path

from writing_project_tools.scaffold import scaffold


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_does_not_create_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Example Article"
            result = scaffold(root)

            self.assertFalse((root / ".gitignore").exists())
            self.assertNotIn(".gitignore", result["created"])
            self.assertTrue((root / "outputs").is_dir())


if __name__ == "__main__":
    unittest.main()
