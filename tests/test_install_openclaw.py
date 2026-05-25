import os
import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


class ClaimLedgerHandler(BaseHTTPRequestHandler):
    posted_claims = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if self.path != "/ledger/claims/link":
            self.send_response(404)
            self.end_headers()
            return
        self.__class__.posted_claims.append(payload)
        agent_id = payload["agentId"]
        response = {
            "agentId": agent_id,
            "claimCode": f"clm_{agent_id}",
            "claimUrl": f"https://ledger.example.test/dashboard?claimCode=clm_{agent_id}&agentId={agent_id}",
            "agentUrl": f"https://ledger.example.test/dashboard?agentId={agent_id}",
        }
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class OpenClawInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.create_openclaw_workspaces()

    def create_openclaw_workspaces(self):
        for name in ["runtime-openclaw-x", "runtime-openclaw-y"]:
            workspace = self.root / name / "workspace"
            profile = workspace / ".eigenflux" / "servers" / "eigenflux" / "profile.json"
            profile.parent.mkdir(parents=True)
            profile.write_text(
                '{"email":"owner@example.com","agent_id":"' + name + '","agent_name":"' + name + '"}',
                encoding="utf-8",
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_install(self, extra_env=None):
        env = {**os.environ, "CHIEF_LEDGER_HTTP_URL": "http://127.0.0.1:9"}
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [str(INSTALL)],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_installs_into_all_openclaw_workspaces_and_keeps_link_failure_nonfatal(self):
        result = self.run_install()

        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ["runtime-openclaw-x", "runtime-openclaw-y"]:
            workspace = self.root / name / "workspace"
            self.assertTrue((workspace / ".local" / "bin" / "chief").exists())
            self.assertTrue((workspace / "skills" / "chief-ledger" / "SKILL.md").exists())
            self.assertTrue((workspace / "skills" / "chief-a2a-service-trade" / "SKILL.md").exists())
            self.assertIn(f"OPENCLAW_WORKSPACE_DIR={workspace}", result.stdout)
        self.assertIn("Claim link unavailable", result.stdout)

    def test_explicit_openclaw_workspace_installs_only_that_workspace(self):
        target = self.root / "runtime-openclaw-x" / "workspace"
        result = self.run_install({"OPENCLAW_WORKSPACE_DIR": str(target)})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / ".local" / "bin" / "chief").exists())
        other = self.root / "runtime-openclaw-y" / "workspace"
        self.assertFalse((other / ".local" / "bin" / "chief").exists())

    def test_install_prints_claim_code_and_link_when_ledger_is_available(self):
        ClaimLedgerHandler.posted_claims = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), ClaimLedgerHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(lambda: thread.join(timeout=5))
        self.addCleanup(server.shutdown)
        target = self.root / "runtime-openclaw-x" / "workspace"

        result = self.run_install(
            {
                "OPENCLAW_WORKSPACE_DIR": str(target),
                "CHIEF_LEDGER_HTTP_URL": f"http://127.0.0.1:{server.server_port}",
            }
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            ClaimLedgerHandler.posted_claims,
            [
                {
                    "agentId": "runtime-openclaw-x",
                    "agentName": "runtime-openclaw-x",
                    "email": "owner@example.com",
                    "agentDescription": "",
                }
            ],
        )
        self.assertIn("Claim Code: clm_runtime-openclaw-x", result.stdout)
        self.assertIn(
            "Claim Link: https://ledger.example.test/dashboard?claimCode=clm_runtime-openclaw-x&agentId=runtime-openclaw-x",
            result.stdout,
        )

    def test_install_fails_when_no_openclaw_workspace_exists(self):
        shutil.rmtree(self.root / "runtime-openclaw-x")
        shutil.rmtree(self.root / "runtime-openclaw-y")

        result = self.run_install()

        self.assertEqual(result.returncode, 2)
        self.assertIn("No OpenClaw workspace found", result.stderr)

    def test_retry_command_is_pasteable_when_workspace_path_contains_spaces(self):
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory(prefix="chief install ")
        self.root = Path(self.temp_dir.name)
        self.create_openclaw_workspaces()

        result = self.run_install()

        self.assertEqual(result.returncode, 0, result.stderr)
        retry_commands = [
            line
            for previous, line in zip(result.stdout.splitlines(), result.stdout.splitlines()[1:])
            if previous == "Retry:"
        ]
        self.assertEqual(len(retry_commands), 2, result.stdout)

        first_retry = retry_commands[0]
        self.assertIn("OPENCLAW_WORKSPACE_DIR=", first_retry)
        self.assertIn("\\ ", first_retry)

        retry_result = subprocess.run(
            first_retry,
            cwd=self.root,
            env={**os.environ, "CHIEF_LEDGER_HTTP_URL": "http://127.0.0.1:9"},
            text=True,
            capture_output=True,
            shell=True,
            check=False,
        )
        self.assertNotEqual(retry_result.returncode, 0)
        self.assertNotEqual(retry_result.returncode, 127, retry_result.stderr)

    def test_agent_wallet_onboarding_docs_point_to_claim_link(self):
        skill = (ROOT / "skills" / "chief-ledger" / "SKILL.md").read_text(encoding="utf-8")
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")

        self.assertIn("chief claim link", skill)
        self.assertIn("chief claim link", install)
        self.assertIn("owner email", skill)
        self.assertIn("owner email", install)
        self.assertNotIn("chief ledger wallet get-or-create", skill)
        self.assertNotIn("chief ledger wallet get-or-create", install)

    def test_chief_ledger_skill_runs_claim_link_after_install_or_claim_code_requests(self):
        skill = (ROOT / "skills" / "chief-ledger" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("installation has just completed", skill)
        self.assertIn("reinstall", skill)
        self.assertIn("claimCode", skill)
        self.assertIn("chief claim link", skill)
