from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
import unittest
from unittest.mock import patch, sentinel

from writing_project_tools.assertions_editor import FIELDNAMES, read_assertions, write_assertions
from writing_project_tools.mcp_server import (
    editor_command,
    launch_editor_process,
    read_project_assertions,
    write_project_assertions,
    prepare_draft_inputs,
    prepare_project_refresh,
    apply_project_refresh,
    get_project_editor_status,
    stop_project_editor,
    merge_assertion_review_state,
    wait_for_http,
)
from writing_project_tools.llm_context import build_llm_context


class RootAssertionsTests(unittest.TestCase):
    def test_default_helpers_share_root_register_and_preserve_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            row = {"include": "FALSE", "id": "ROOT-1", "section": "Intro", "precis": "Label", "assertion": "Exact document wording.", "user_edit": "Reviewed final wording.", "status": "verified", "evidence_or_check": "Source A"}
            write_project_assertions(str(root), [row])
            self.assertTrue((root / "assertions.xlsx").is_file())
            self.assertEqual(read_project_assertions(str(root))["rows"], [row])
            self.assertEqual(prepare_draft_inputs(str(root))["assertions"]["rows"], [row])
            self.assertEqual(prepare_project_refresh(str(root))["targets"]["assertions_workbook"], "assertions.xlsx")
            self.assertIn("Reviewed final wording.", build_llm_context(root))
            result = apply_project_refresh(str(root), "# Revised plan", [{**row, "include": "TRUE", "user_edit": ""}])
            self.assertEqual(result["assertions_workbook"], str(root / "assertions.xlsx"))
            self.assertEqual(read_project_assertions(str(root))["rows"], [row])
            self.assertFalse((root / "outputs" / "assertions.xlsx").exists())
            with patch("writing_project_tools.mcp_server.find_editor_processes", return_value=[]) as find:
                get_project_editor_status(str(root))
                stop_project_editor(str(root))
            self.assertEqual([call.args[0] for call in find.call_args_list], [root / "assertions.xlsx"] * 2)


class EditorCommandTests(unittest.TestCase):
    def test_denied_breakaway_retries_without_it(self) -> None:
        denied = PermissionError("Access denied")
        denied.winerror = 5
        with patch("writing_project_tools.mcp_server.os.name", "nt"), patch(
            "writing_project_tools.mcp_server.editor_creationflags", return_value=0x1000208
        ), patch("writing_project_tools.mcp_server.subprocess.CREATE_BREAKAWAY_FROM_JOB", 0x1000000, create=True), patch(
            "writing_project_tools.mcp_server.subprocess.Popen", side_effect=[denied, sentinel.process]
        ) as popen:
            result = launch_editor_process(["python"], cwd="project")
        self.assertIs(result, sentinel.process)
        self.assertEqual(popen.call_args_list[0].kwargs["creationflags"], 0x1000208)
        self.assertEqual(popen.call_args_list[1].kwargs["creationflags"], 0x208)
        self.assertEqual(popen.call_args_list[1].kwargs["cwd"], "project")

    def test_other_launch_errors_are_not_retried(self) -> None:
        with patch("writing_project_tools.mcp_server.subprocess.Popen", side_effect=FileNotFoundError("python")) as popen:
            with self.assertRaises(FileNotFoundError):
                launch_editor_process(["python"])
        popen.assert_called_once()

    def test_csv_path_with_spaces_stays_one_argument(self) -> None:
        csv_path = Path(r"E:\Writing\Session - Staff Conference\assertions.csv")

        command = editor_command(csv_path, "127.0.0.1", 8765, open_browser=False)

        csv_index = command.index("--csv") + 1
        self.assertEqual(command[csv_index], str(csv_path))
        self.assertNotIn("Session", command)
        self.assertNotIn(r"-", command)
        self.assertIn("--no-open", command)


class WaitForHttpTests(unittest.TestCase):
    def test_wait_for_http_reaches_local_server(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            self.assertTrue(wait_for_http(f"http://{host}:{port}/", timeout=2))
        finally:
            server.shutdown()
            server.server_close()


class AssertionMergeTests(unittest.TestCase):
    def test_precis_is_separate_from_wording_and_does_not_reset_review(self) -> None:
        existing = [{"include": "TRUE", "id": "A1", "section": "Intro", "precis": "Old label", "assertion": "Full intended wording.", "user_edit": "", "status": "verified", "evidence_or_check": "Source 1"}]
        incoming = [{**existing[0], "precis": "Better label"}]

        merged = merge_assertion_review_state(existing, incoming)

        self.assertEqual(merged[0]["precis"], "Better label")
        self.assertEqual(merged[0]["assertion"], "Full intended wording.")
        self.assertEqual(merged[0]["status"], "verified")

    def test_workbook_roundtrip_preserves_precis_and_wording(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assertions.xlsx"
            write_assertions(path, [{"include": "TRUE", "id": "A1", "section": "Intro", "precis": "Short label", "assertion": "Full wording", "status": "verify", "evidence_or_check": "Source 1"}])
            rows = read_assertions(path)
            self.assertEqual(rows[0]["precis"], "Short label")
            self.assertEqual(rows[0]["assertion"], "Full wording")
            self.assertEqual(list(rows[0]), FIELDNAMES)

    def test_matching_id_preserves_review_state(self) -> None:
        existing = [{
            "include": "FALSE",
            "id": "A1",
            "section": "Intro",
            "assertion": "Old wording",
            "user_edit": "Reviewed wording",
            "status": "planned",
            "evidence_or_check": "Old evidence",
        }]
        incoming = [{
            "include": "TRUE",
            "id": "A1",
            "section": "Intro",
            "assertion": "Old wording",
            "user_edit": "",
            "status": "verify",
            "evidence_or_check": "Old evidence",
        }]

        merged = merge_assertion_review_state(existing, incoming)

        self.assertEqual(merged[0]["include"], "FALSE")
        self.assertEqual(merged[0]["user_edit"], "Reviewed wording")
        self.assertEqual(merged[0]["status"], "planned")

    def test_changed_matching_id_is_marked_verify(self) -> None:
        existing = [{
            "include": "TRUE",
            "id": "A1",
            "section": "Intro",
            "assertion": "Old wording",
            "user_edit": "",
            "status": "planned",
            "evidence_or_check": "",
        }]
        incoming = [{
            "include": "TRUE",
            "id": "A1",
            "section": "Intro",
            "assertion": "New wording",
            "user_edit": "",
            "status": "planned",
            "evidence_or_check": "",
        }]

        merged = merge_assertion_review_state(existing, incoming)

        self.assertEqual(merged[0]["status"], "verify")

    def test_missing_existing_assertion_is_retained_as_removed(self) -> None:
        existing = [{
            "include": "TRUE",
            "id": "A1",
            "section": "Intro",
            "assertion": "Removed claim",
            "user_edit": "",
            "status": "planned",
            "evidence_or_check": "",
        }]

        merged = merge_assertion_review_state(existing, [])

        self.assertEqual(merged[0]["include"], "FALSE")
        self.assertEqual(merged[0]["status"], "removed")


if __name__ == "__main__":
    unittest.main()
