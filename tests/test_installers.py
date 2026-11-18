"""Run installers with fake system commands: no sudo, installs, or downloads."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_COMMAND = r'''
import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["COMMAND_LOG"], "a") as log:
    log.write(json.dumps([name, *args]) + "\n")
if name == "uname":
    print("Linux" if "-s" in args else os.getenv("TEST_ARCH", "aarch64"))
elif name == "nvidia-smi":
    if os.getenv("TEST_DRIVER_BROKEN"): sys.exit(1)
    print("NVIDIA-SMI | CUDA Version: 13.0")
elif name == "sudo":
    if args == ["-v"]: sys.exit(0)
    sys.exit(subprocess.run(args).returncode)
elif name == "uv" and args[:1] == ["sync"]:
    if os.getenv("TEST_UV_SYNC_FAIL"): sys.exit(1)
elif name == "dpkg":
    print("arm64")
elif name == "dpkg-deb":
    print(os.getenv("TEST_CODE_ARCH", "arm64"))
elif name == "curl":
    content = "fake package"
    if "https://astral.sh/uv/install.sh" in args:
        content = """#!/bin/sh
set -e
mkdir -p "$UV_INSTALL_DIR"
cp "$FAKE_UV_SOURCE" "$UV_INSTALL_DIR/uv"
chmod +x "$UV_INSTALL_DIR/uv"
"""
    pathlib.Path(args[args.index("-o") + 1]).write_text(content)
'''


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "scripts", self.root / "scripts")
        self.bin = self.root / "fake-bin"
        self.bin.mkdir()
        self.log = self.root / "commands.jsonl"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "COMMAND_LOG": str(self.log),
            "UV_INSTALL_DIR": str(self.root / "installed-uv"),
            "FAKE_UV_SOURCE": str(self.bin / "uv-source"),
        }
        for name in ["uname", "nvidia-smi", "sudo", "apt-get", "uv", "uv-source", "ollama", "code", "systemctl", "dpkg", "dpkg-deb", "curl"]:
            self.stub(name)

    def stub(self, name):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + FAKE_COMMAND)
        path.chmod(0o755)

    def run_script(self, name="setup.sh", *args):
        result = subprocess.run(
            ["bash", str(self.root / "scripts" / name), *args],
            env=self.env, text=True, capture_output=True,
        )
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        return result, calls

    def test_existing_installations_reused_and_requested_models_pulled(self):
        result, calls = self.run_script("setup.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("curl", [c[0] for c in calls])
        self.assertEqual([c[2] for c in calls if c[:2] == ["ollama", "pull"]],
                         ["gemma4:e4b", "gemma4:26b"])
        self.assertFalse(any("upgrade" in c for c in calls))
        self.assertFalse(any("nvidia-driver" in " ".join(c) for c in calls))

    def test_python_only_makes_no_system_or_model_calls(self):
        result, calls = self.run_script("setup.sh", "--python-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all(c[0] == "uv" for c in calls), calls)
        self.assertIn(["uv", "sync", "--locked", "--project", str(self.root)], calls)

    def test_missing_uv_is_installed_and_used_in_the_same_setup(self):
        (self.bin / "uv").unlink()
        result, calls = self.run_script("setup.sh", "--python-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((Path(self.env["UV_INSTALL_DIR"]) / "uv").is_file())
        self.assertTrue(any(c[0] == "curl" and "https://astral.sh/uv/install.sh" in c for c in calls))
        self.assertIn(["uv", "sync", "--locked", "--project", str(self.root)], calls)
        self.assertNotIn("sudo", [c[0] for c in calls])

    def test_failed_sync_stops_before_model_downloads(self):
        self.env["TEST_UV_SYNC_FAIL"] = "1"
        result, calls = self.run_script("setup.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[:2] == ["ollama", "pull"] for c in calls))

    def test_bad_architecture_stops_before_system_changes(self):
        self.env["TEST_ARCH"] = "x86_64"
        result, calls = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sudo", [c[0] for c in calls])

    def test_broken_driver_stops_before_system_changes(self):
        self.env["TEST_DRIVER_BROKEN"] = "1"
        result, calls = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("sudo", [c[0] for c in calls])

    def test_skip_options_leave_existing_server_and_models_alone(self):
        result, calls = self.run_script("setup.sh", "--skip-ollama", "--skip-models", "--skip-vscode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue({"nvidia-smi", "ollama", "systemctl", "curl", "code"}.isdisjoint(c[0] for c in calls))

    def test_vscode_download_is_arm64_and_wrong_package_is_rejected(self):
        # Ensure any actual host code command is hidden from command -v.
        (self.bin / "code").unlink()
        script = self.root / "scripts" / "install-vscode.sh"
        script.write_text(script.read_text().replace("command -v code >/dev/null", "false"))
        self.env["TEST_CODE_ARCH"] = "amd64"
        result, calls = self.run_script("install-vscode.sh")
        self.assertNotEqual(result.returncode, 0)
        curl_call = next(c for c in calls if c[0] == "curl")
        self.assertIn("https://update.code.visualstudio.com/latest/linux-deb-arm64/stable", curl_call)
        self.assertNotIn("apt-get", [c[0] for c in calls])


if __name__ == "__main__":
    unittest.main()
