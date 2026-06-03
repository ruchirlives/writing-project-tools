from pathlib import Path
import unittest

from writing_project_tools.mcp_server import editor_command


class EditorCommandTests(unittest.TestCase):
    def test_csv_path_with_spaces_stays_one_argument(self) -> None:
        csv_path = Path(r"E:\Writing\Session - Staff Conference\assertions.csv")

        command = editor_command(csv_path, "127.0.0.1", 8765, open_browser=False)

        csv_index = command.index("--csv") + 1
        self.assertEqual(command[csv_index], str(csv_path))
        self.assertNotIn("Session", command)
        self.assertNotIn(r"-", command)
        self.assertIn("--no-open", command)


if __name__ == "__main__":
    unittest.main()
