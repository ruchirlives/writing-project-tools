from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from writing_project_tools.mcp_server import editor_command, wait_for_http


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


if __name__ == "__main__":
    unittest.main()
