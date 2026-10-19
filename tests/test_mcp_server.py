from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import csv
import tempfile
import threading
import unittest

from writing_project_tools.assertions_editor import FIELDNAMES, read_assertions, write_assertions
from writing_project_tools.mcp_server import (
    editor_command,
    merge_assertion_review_state,
    wait_for_http,
)


class EditorCommandTests(unittest.TestCase):
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

    def test_legacy_csv_gains_blank_precis_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assertions.csv"
            path.write_text("include,id,section,assertion,user_edit,status,evidence_or_check\nTRUE,A1,Intro,Full wording,,verify,Source 1\n", encoding="utf-8")

            rows = read_assertions(path)
            self.assertEqual(rows[0]["precis"], "")
            write_assertions(path, rows)
            with path.open(encoding="utf-8", newline="") as handle:
                saved = csv.DictReader(handle)
                self.assertEqual(saved.fieldnames, FIELDNAMES)
                self.assertEqual(next(saved)["assertion"], "Full wording")

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
