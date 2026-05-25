import os
import json
import platform
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
TEST_ASSET_DIR = None
CHIEF_ASSET = None


def current_chief_asset_name():
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine, machine)
    if system not in {"darwin", "linux"} or arch not in {"amd64", "arm64"}:
        raise RuntimeError(f"unsupported test platform: {system}/{machine}")
    return f"chief_{system}_{arch}"


def setUpModule():
    global TEST_ASSET_DIR, CHIEF_ASSET
    TEST_ASSET_DIR = tempfile.TemporaryDirectory()
    CHIEF_ASSET = Path(TEST_ASSET_DIR.name) / current_chief_asset_name()
    subprocess.run(
        [str(ROOT / "scripts" / "build-chief.sh"), str(CHIEF_ASSET)],
        cwd=ROOT,
        check=True,
    )
    with CHIEF_ASSET.open("ab") as asset:
        asset.write(b"\nchief-install-test-asset\n")
    if not CHIEF_ASSET.is_file() or not os.access(CHIEF_ASSET, os.X_OK):
        raise AssertionError(f"local chief test asset is not executable: {CHIEF_ASSET}")


def tearDownModule():
    if TEST_ASSET_DIR is not None:
        TEST_ASSET_DIR.cleanup()


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


class BinaryAssetHandler(BaseHTTPRequestHandler):
    asset_name = ""
    asset_bytes = b""
    requested_paths = []

    def log_message(self, format, *args):
        return

    def do_GET(self):
        self.__class__.requested_paths.append(self.path)
        if self.path != f"/{self.__class__.asset_name}":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.__class__.asset_bytes)))
        self.end_headers()
        self.wfile.write(self.__class__.asset_bytes)


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

    def hide_local_dist_asset(self, asset_name):
        dist_asset = ROOT / "dist" / asset_name
        if not dist_asset.exists():
            return

        backup_dir = tempfile.TemporaryDirectory(prefix="chief-dist-backup-")
        backup = Path(backup_dir.name) / asset_name
        dist_asset.replace(backup)

        self.addCleanup(backup_dir.cleanup)

        def restore():
            dist_asset.parent.mkdir(exist_ok=True)
            backup.replace(dist_asset)

        self.addCleanup(restore)

    def run_install(self, extra_env=None):
        env = {
            **os.environ,
            "CHIEF_INSTALL_BIN_DIR": str(CHIEF_ASSET.parent),
            "CHIEF_LEDGER_HTTP_URL": "http://127.0.0.1:9",
        }
        if extra_env:
            for key, value in extra_env.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
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
            chief = workspace / ".local" / "bin" / "chief"
            self.assertTrue(chief.exists())
            self.assertTrue(os.access(chief, os.X_OK))
            self.assertEqual(chief.read_bytes(), CHIEF_ASSET.read_bytes())
            version = subprocess.run(
                [str(chief), "version"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertRegex(version.stdout, r"^chief \d{4}\.\d{2}\.\d{2}\.\d+\n$")
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

    def test_install_fails_clearly_on_unsupported_platform(self):
        bin_dir = self.root / "fake-bin"
        bin_dir.mkdir()
        uname = bin_dir / "uname"
        uname.write_text(
            "#!/usr/bin/env sh\n"
            "case \"$1\" in\n"
            "  -s) echo Plan9 ;;\n"
            "  -m) echo riscv64 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        uname.chmod(0o755)

        result = self.run_install({"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"})

        self.assertEqual(result.returncode, 2)
        self.assertIn("Unsupported platform: Plan9/riscv64", result.stderr)

    def test_downloads_binary_asset_from_binary_base_url(self):
        asset_name = "chief_linux_amd64"
        self.hide_local_dist_asset(asset_name)
        BinaryAssetHandler.asset_name = asset_name
        BinaryAssetHandler.asset_bytes = CHIEF_ASSET.read_bytes()
        BinaryAssetHandler.requested_paths = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), BinaryAssetHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(lambda: thread.join(timeout=5))
        self.addCleanup(server.shutdown)

        bin_dir = self.root / "fake-bin"
        bin_dir.mkdir()
        uname = bin_dir / "uname"
        uname.write_text(
            "#!/usr/bin/env sh\n"
            "case \"$1\" in\n"
            "  -s) echo Linux ;;\n"
            "  -m) echo x86_64 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        uname.chmod(0o755)
        target = self.root / "runtime-openclaw-x" / "workspace"

        result = self.run_install(
            {
                "OPENCLAW_WORKSPACE_DIR": str(target),
                "CHIEF_INSTALL_BIN_DIR": None,
                "CHIEF_INSTALL_BASE_URL": "http://127.0.0.1:9/not-used",
                "CHIEF_INSTALL_BIN_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            }
        )

        chief = target / ".local" / "bin" / "chief"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(BinaryAssetHandler.requested_paths, [f"/{asset_name}"])
        self.assertEqual(chief.read_bytes(), CHIEF_ASSET.read_bytes())

    def test_installs_binary_asset_from_local_dist_before_download(self):
        asset_name = "chief_linux_arm64"
        dist_asset = ROOT / "dist" / asset_name
        dist_asset.parent.mkdir(exist_ok=True)
        had_original = dist_asset.exists()
        original_bytes = dist_asset.read_bytes() if had_original else None
        original_mode = dist_asset.stat().st_mode if had_original else None
        dist_asset.write_bytes(CHIEF_ASSET.read_bytes())
        dist_asset.chmod(0o755)

        def restore_dist_asset():
            if had_original:
                dist_asset.write_bytes(original_bytes)
                dist_asset.chmod(original_mode)
            else:
                dist_asset.unlink(missing_ok=True)

        self.addCleanup(restore_dist_asset)

        bin_dir = self.root / "fake-bin"
        bin_dir.mkdir()
        uname = bin_dir / "uname"
        uname.write_text(
            "#!/usr/bin/env sh\n"
            "case \"$1\" in\n"
            "  -s) echo Linux ;;\n"
            "  -m) echo aarch64 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        uname.chmod(0o755)
        target = self.root / "runtime-openclaw-x" / "workspace"

        result = self.run_install(
            {
                "OPENCLAW_WORKSPACE_DIR": str(target),
                "CHIEF_INSTALL_BIN_DIR": None,
                "CHIEF_INSTALL_BIN_BASE_URL": "http://127.0.0.1:9/not-used",
                "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            }
        )

        chief = target / ".local" / "bin" / "chief"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(chief.read_bytes(), CHIEF_ASSET.read_bytes())

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
            env={
                **os.environ,
                "CHIEF_INSTALL_BIN_DIR": str(CHIEF_ASSET.parent),
                "CHIEF_LEDGER_HTTP_URL": "http://127.0.0.1:9",
            },
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
