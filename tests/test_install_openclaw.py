import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"


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
        self.assertNotIn("chief ledger wallet get-or-create", skill)
        self.assertNotIn("chief ledger wallet get-or-create", install)
