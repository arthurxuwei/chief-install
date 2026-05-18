import json
import os
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHIEF = ROOT / "bin" / "chief"


class LedgerHandler(BaseHTTPRequestHandler):
    posted_transfers = []
    get_count = 0

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        self.get_count += 1
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path == "/ledger/transfers":
            self.posted_transfers.append(body)
            self._json(200, {"ok": True, "transfer": body})
            return
        self.send_response(404)
        self.end_headers()

    def _json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class ChiefTransferTests(unittest.TestCase):
    def setUp(self):
        LedgerHandler.posted_transfers = []
        LedgerHandler.get_count = 0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LedgerHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        profile_dir = workspace / ".eigenflux" / "servers" / "eigenflux"
        profile_dir.mkdir(parents=True)
        (profile_dir / "profile.json").write_text(
            json.dumps(
                {
                    "email": "sender@example.com",
                    "agent_id": "agent_sender",
                    "agent_name": "Sender",
                }
            ),
            encoding="utf-8",
        )
        self.env = {
            **os.environ,
            "CHIEF_LEDGER_HTTP_URL": f"http://127.0.0.1:{self.server.server_port}",
            "ZEROCLAW_WORKSPACE": str(workspace),
        }

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp_dir.cleanup()

    def run_chief(self, payload):
        return subprocess.run(
            [str(CHIEF), "ledger", "transfer", json.dumps(payload)],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_transfer_accepts_email_and_amount_only(self):
        result = self.run_chief({"toEmail": "receiver@example.com", "amount": "0.001 U"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_transfers,
            [
                {
                    "fromEmail": "sender@example.com",
                    "toEmail": "receiver@example.com",
                    "amountAtomic": "1000",
                    "reason": "direct transfer to receiver@example.com",
                }
            ],
        )
        self.assertEqual(LedgerHandler.get_count, 0)

    def test_transfer_rejects_agent_id_payloads(self):
        result = self.run_chief(
            {
                "fromAgentId": "agent_sender",
                "toAgentId": "agent_receiver",
                "amountAtomic": "1000",
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("fromAgentId/toAgentId are internal", result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers, [])


if __name__ == "__main__":
    unittest.main()
