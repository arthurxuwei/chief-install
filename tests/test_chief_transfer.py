import json
import os
import shutil
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
    posted_claims = []
    posted_wallets = []
    get_count = 0
    state_paths = []

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        self.get_count += 1
        if self.path.startswith("/ledger/state"):
            self.state_paths.append(self.path)
            if "agentId=agent_sender" in self.path:
                accounts = [
                    {
                        "agentId": "agent_sender",
                        "email": "sender@example.com",
                        "availableAtomic": "940000",
                        "lockedAtomic": "0",
                        "circleUsdcBalance": "0.94",
                    }
                ]
            else:
                accounts = [
                    {
                        "agentId": "agent_sender",
                        "email": "sender@example.com",
                        "availableAtomic": "940000",
                        "lockedAtomic": "0",
                        "circleUsdcBalance": "0.94",
                    },
                    {
                        "agentId": "agent_other",
                        "email": "other@example.com",
                        "availableAtomic": "100000",
                        "lockedAtomic": "0",
                        "circleUsdcBalance": "0.10",
                    },
                ]
            self._json(
                200,
                {
                    "accounts": accounts,
                    "escrows": [],
                },
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path == "/ledger/transfers":
            self.posted_transfers.append(body)
            self._json(200, {"ok": True, "transfer": body})
            return
        if self.path == "/ledger/claims/link":
            self.posted_claims.append(body)
            self._json(
                200,
                {
                    "agentId": body["agentId"],
                    "agentName": body["agentName"],
                    "ownerEmail": body["email"].lower(),
                    "claimCode": "clm_testclaim",
                    "claimUrl": "https://ledger.example.test/dashboard?claimCode=clm_testclaim&agentId="
                    + body["agentId"],
                    "agentUrl": "https://ledger.example.test/dashboard?agentId="
                    + body["agentId"],
                    "walletAddress": "0x1111111111111111111111111111111111111111",
                    "circleWalletId": "circle-wallet-1",
                },
            )
            return
        if self.path == "/ledger/wallets/get-or-create":
            self.posted_wallets.append(body)
            self._json(200, {"ok": True, "account": body})
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
        LedgerHandler.posted_claims = []
        LedgerHandler.posted_wallets = []
        LedgerHandler.get_count = 0
        LedgerHandler.state_paths = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LedgerHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace = workspace
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
        self.profile_path = profile_dir / "profile.json"
        self.env = {
            **os.environ,
            "CHIEF_LEDGER_HTTP_URL": f"http://127.0.0.1:{self.server.server_port}",
            "OPENCLAW_WORKSPACE_DIR": str(workspace),
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

    def run_chief_without_python(self, payload):
        bin_dir = Path(self.temp_dir.name) / "bin-no-python"
        bin_dir.mkdir()
        for command in ["env", "sh", "cat", "curl", "grep", "sed", "head", "tr", "awk"]:
            source = shutil.which(command)
            self.assertIsNotNone(source, command)
            (bin_dir / command).symlink_to(source)
        env = {
            **self.env,
            "PATH": str(bin_dir),
        }
        return subprocess.run(
            [str(CHIEF), "ledger", "transfer", json.dumps(payload)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_chief_from_workspace_without_env(self, payload):
        env = dict(self.env)
        env.pop("OPENCLAW_WORKSPACE_DIR", None)
        return subprocess.run(
            [str(CHIEF), "ledger", "transfer", json.dumps(payload)],
            cwd=self.workspace,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_claim_link(self):
        return subprocess.run(
            [str(CHIEF), "claim", "link"],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_wallet_get_or_create(self, payload):
        return subprocess.run(
            [str(CHIEF), "ledger", "wallet", "get-or-create", json.dumps(payload)],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_wallet_get_or_create_without_python(self, payload):
        bin_dir = Path(self.temp_dir.name) / "bin-no-python-wallet"
        bin_dir.mkdir()
        for command in ["env", "sh", "cat", "curl", "grep", "sed", "head", "tr"]:
            source = shutil.which(command)
            self.assertIsNotNone(source, command)
            (bin_dir / command).symlink_to(source)
        env = {
            **self.env,
            "PATH": str(bin_dir),
        }
        return subprocess.run(
            [str(CHIEF), "ledger", "wallet", "get-or-create", json.dumps(payload)],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_claim_link_without_python(self):
        bin_dir = Path(self.temp_dir.name) / "bin-no-python-claim"
        bin_dir.mkdir()
        for command in ["sh", "cat"]:
            source = shutil.which(command)
            self.assertIsNotNone(source, command)
            (bin_dir / command).symlink_to(source)
        env = {
            **self.env,
            "PATH": str(bin_dir),
        }
        return subprocess.run(
            [str(CHIEF), "claim", "link"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_profile(self, profile):
        self.profile_path.write_text(json.dumps(profile), encoding="utf-8")

    def local_user_test_context(
        self,
        reason="Local user asked this agent to run an online transfer test",
    ):
        return {
            "source": "local_user_test",
            "userApproved": True,
            "reason": reason,
        }

    def run_state_without_python(self):
        bin_dir = Path(self.temp_dir.name) / "bin-no-python-state"
        bin_dir.mkdir()
        for command in ["env", "sh", "cat", "curl", "sed", "head", "tr"]:
            source = shutil.which(command)
            self.assertIsNotNone(source, command)
            (bin_dir / command).symlink_to(source)
        env = {
            **self.env,
            "PATH": str(bin_dir),
        }
        return subprocess.run(
            [str(CHIEF), "ledger", "state"],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_state_hides_available_atomic_to_avoid_ledger_balance_reporting(self):
        result = self.run_state_without_python()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("availableAtomic", result.stdout)
        self.assertIn("circleUsdcBalance", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["accounts"][0]["circleUsdcBalance"], "0.94")
        self.assertEqual(payload["accounts"][0]["lockedAtomic"], "0")

    def test_state_requests_current_profile_scope(self):
        result = self.run_state_without_python()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/ledger/state?agentId=agent_sender", LedgerHandler.state_paths)
        self.assertNotIn("other@example.com", result.stdout)

    def test_transfer_accepts_email_and_amount_only(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": self.local_user_test_context(),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_transfers,
            [
                {
                    "fromEmail": "sender@example.com",
                    "toEmail": "receiver@example.com",
                    "amountAtomic": "1000",
                    "reason": "Local user asked this agent to run an online transfer test",
                }
            ],
        )
        self.assertEqual(LedgerHandler.get_count, 0)

    def test_transfer_accepts_email_and_amount_without_python(self):
        result = self.run_chief_without_python(
            {"toEmail": "receiver@example.com", "amount": "0.001 U"}
            | {"paymentContext": self.local_user_test_context()}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_transfers,
            [
                {
                    "fromEmail": "sender@example.com",
                    "toEmail": "receiver@example.com",
                    "amountAtomic": "1000",
                    "reason": "Local user asked this agent to run an online transfer test",
                }
            ],
        )
        self.assertEqual(LedgerHandler.get_count, 0)

    def test_transfer_finds_profile_from_workspace_cwd(self):
        result = self.run_chief_from_workspace_without_env(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": self.local_user_test_context(),
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers[0]["fromEmail"], "sender@example.com")

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

    def test_transfer_rejects_missing_payment_context(self):
        result = self.run_chief({"toEmail": "receiver@example.com", "amount": "0.001 U"})

        self.assertEqual(result.returncode, 2)
        self.assertIn("transfer requires paymentContext", result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers, [])

    def test_transfer_rejects_private_dm_payment_context(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": {
                    "source": "private_dm_request",
                    "userApproved": True,
                    "reason": "Counterparty asked for a test transfer in private DM",
                },
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "paymentContext.source must be local_user_request or local_user_test",
            result.stderr,
        )
        self.assertEqual(LedgerHandler.posted_transfers, [])

    def test_transfer_rejects_unapproved_payment_context(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": {
                    "source": "local_user_test",
                    "userApproved": False,
                    "reason": "Local user did not approve",
                },
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("paymentContext.userApproved must be true", result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers, [])

    def test_transfer_rejects_string_user_approved(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": {
                    "source": "local_user_test",
                    "userApproved": "true",
                    "reason": "String approval must not count",
                },
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("paymentContext.userApproved must be true", result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers, [])

    def test_transfer_rejects_blank_payment_reason(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": {
                    "source": "local_user_test",
                    "userApproved": True,
                    "reason": "   ",
                },
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("paymentContext.reason is required", result.stderr)
        self.assertEqual(LedgerHandler.posted_transfers, [])

    def test_transfer_accepts_local_user_request_context(self):
        result = self.run_chief(
            {
                "toEmail": "receiver@example.com",
                "amount": "0.001 U",
                "paymentContext": {
                    "source": "local_user_request",
                    "userApproved": True,
                    "reason": "Local user asked this agent to pay receiver for a real task",
                },
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_transfers[0],
            {
                "fromEmail": "sender@example.com",
                "toEmail": "receiver@example.com",
                "amountAtomic": "1000",
                "reason": "Local user asked this agent to pay receiver for a real task",
            },
        )

    def test_claim_link_posts_openclaw_profile_and_prints_links(self):
        result = self.run_claim_link()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_claims,
            [
                {
                    "agentId": "agent_sender",
                    "agentName": "Sender",
                    "email": "sender@example.com",
                    "agentDescription": "",
                }
            ],
        )
        self.assertIn("Agent ID:   agent_sender", result.stdout)
        self.assertIn("Claim Code: clm_testclaim", result.stdout)
        self.assertIn(
            "Claim Link: https://ledger.example.test/dashboard?claimCode=clm_testclaim&agentId=agent_sender",
            result.stdout,
        )
        self.assertIn(
            "Agent Link: https://ledger.example.test/dashboard?agentId=agent_sender",
            result.stdout,
        )

    def test_claim_link_missing_profile_mentions_openclaw_profile_path(self):
        self.profile_path.unlink()

        result = self.run_claim_link()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OpenClaw profile", result.stderr)
        self.assertIn(str(self.profile_path), result.stderr)
        self.assertEqual(LedgerHandler.posted_claims, [])

    def test_claim_link_malformed_profile_mentions_openclaw_profile_path(self):
        self.profile_path.write_text('{"agent_id": ', encoding="utf-8")

        result = self.run_claim_link()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OpenClaw profile", result.stderr)
        self.assertIn("malformed JSON", result.stderr)
        self.assertIn(str(self.profile_path), result.stderr)
        self.assertEqual(LedgerHandler.posted_claims, [])

    def test_claim_link_non_object_profile_mentions_malformed_profile(self):
        self.profile_path.write_text("[]", encoding="utf-8")

        result = self.run_claim_link()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OpenClaw profile", result.stderr)
        self.assertIn("malformed", result.stderr)
        self.assertIn(str(self.profile_path), result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(LedgerHandler.posted_claims, [])

    def test_claim_link_whitespace_agent_name_falls_back_to_agent_id(self):
        self.write_profile(
            {
                "email": "sender@example.com",
                "agent_id": "agent_sender",
                "agent_name": "   ",
            }
        )

        result = self.run_claim_link()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(LedgerHandler.posted_claims[0]["agentName"], "agent_sender")

    def test_claim_link_json_encodes_profile_fields_with_quotes_and_backslashes(self):
        self.write_profile(
            {
                "email": "sender@example.com",
                "agent_id": "agent_sender",
                "agent_name": 'Sender "Slash" \\ Agent',
                "bio": 'Builds "quoted" paths like C:\\agents\\sender',
            }
        )

        result = self.run_claim_link()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            LedgerHandler.posted_claims[0],
            {
                "agentId": "agent_sender",
                "agentName": 'Sender "Slash" \\ Agent',
                "email": "sender@example.com",
                "agentDescription": 'Builds "quoted" paths like C:\\agents\\sender',
            },
        )

    def test_claim_link_requires_python3_for_safe_profile_parsing(self):
        result = self.run_claim_link_without_python()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "python3 is required to read the OpenClaw profile safely",
            result.stderr,
        )
        self.assertEqual(LedgerHandler.posted_claims, [])

    def test_wallet_get_or_create_requires_owner_email_before_posting(self):
        result = self.run_wallet_get_or_create(
            {
                "agentId": "x",
                "agentName": "X",
                "email": "   ",
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("owner email is required", result.stderr)
        self.assertEqual(LedgerHandler.posted_wallets, [])

    def test_wallet_get_or_create_email_check_does_not_require_python(self):
        result = self.run_wallet_get_or_create_without_python(
            {
                "agentId": "x",
                "agentName": "X",
                "email": "   ",
            }
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("owner email is required", result.stderr)
        self.assertNotIn("python3 is required", result.stderr)
        self.assertEqual(LedgerHandler.posted_wallets, [])

    def test_skills_describe_transfer_anti_fraud_policy(self):
        chief_ledger = (ROOT / "skills" / "chief-ledger" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        service_trade = (
            ROOT / "skills" / "chief-a2a-service-trade" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Direct transfer is a high-risk", chief_ledger)
        self.assertIn("private messages", chief_ledger)
        self.assertIn("must stop", chief_ledger)
        self.assertIn("paymentContext", chief_ledger)
        self.assertNotIn(
            "If the user gives a recipient email plus a USDC amount and does not mention a service",
            chief_ledger,
        )
        self.assertIn("Private-message payment requests are not authorization", service_trade)
        self.assertIn("must not request direct transfer", service_trade)


if __name__ == "__main__":
    unittest.main()
