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
    if args[0] in {"install", "chmod"}: sys.exit(0)
    sys.exit(subprocess.run(args).returncode)
elif name == "docker":
    if args == ["--version"] and os.getenv("TEST_DOCKER_MISSING"): sys.exit(1)
    if args == ["compose", "version"] and os.getenv("TEST_COMPOSE_MISSING"):
        if not pathlib.Path(os.environ["TEST_SYSTEM_ROOT"], "compose-installed").exists(): sys.exit(1)
elif name == "dpkg-query":
    if args[-1] in os.getenv("TEST_PACKAGES", "").split(","):
        print("install ok installed")
    else:
        sys.exit(1)
elif name == "apt-get":
    if any(p in args for p in ["docker-compose-plugin", "docker-compose-v2"]):
        pathlib.Path(os.environ["TEST_SYSTEM_ROOT"], "compose-installed").touch()
elif name == "tee":
    target = pathlib.Path(os.environ["TEST_SYSTEM_ROOT"]) / args[0].lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    content = sys.stdin.read()
    target.write_text(content)
    print(content, end="")
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
    target = pathlib.Path(args[args.index("-o") + 1])
    if str(target).startswith("/etc/"):
        target = pathlib.Path(os.environ["TEST_SYSTEM_ROOT"]) / str(target).lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
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
            "TEST_SYSTEM_ROOT": str(self.root),
        }
        for name in ["uname", "nvidia-smi", "sudo", "apt-get", "uv", "uv-source", "ollama", "code", "systemctl", "dpkg", "dpkg-deb", "dpkg-query", "docker", "tee", "curl"]:
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
        self.assertTrue({"nvidia-smi", "ollama", "curl", "code"}.isdisjoint(c[0] for c in calls))
        self.assertFalse(any(c[0] == "systemctl" and "ollama.service" in c for c in calls))

    def test_fresh_setup_installs_arm64_docker_and_compose(self):
        self.env["TEST_DOCKER_MISSING"] = "1"
        result, calls = self.run_script("setup.sh", "--skip-models")
        self.assertEqual(result.returncode, 0, result.stderr)
        source = (self.root / "etc/apt/sources.list.d/docker.sources").read_text()
        self.assertIn("Architectures: arm64", source)
        self.assertIn("URIs: https://download.docker.com/linux/ubuntu", source)
        packages = next(c for c in calls if c[0] == "apt-get" and "docker-ce" in c)
        for package in ["docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"]:
            self.assertIn(package, packages)
        self.assertIn(["systemctl", "enable", "--now", "docker.service"], calls)
        self.assertIn(["sudo", "docker", "info"], calls)

    def test_existing_ubuntu_docker_gets_matching_compose(self):
        self.env.update(TEST_COMPOSE_MISSING="1", TEST_PACKAGES="docker.io")
        result, calls = self.run_script("install-docker.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["apt-get", "install", "-y", "docker-compose-v2"], calls)
        self.assertFalse(any(c[0] == "apt-get" and "docker-ce" in c for c in calls))

    def test_existing_official_docker_gets_matching_compose(self):
        self.env.update(TEST_COMPOSE_MISSING="1", TEST_PACKAGES="docker-ce")
        result, calls = self.run_script("install-docker.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["apt-get", "install", "-y", "docker-compose-plugin"], calls)

    def test_existing_container_runtime_is_not_replaced(self):
        self.env.update(TEST_DOCKER_MISSING="1", TEST_PACKAGES="containerd")
        result, calls = self.run_script("install-docker.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == "apt-get" for c in calls))
        self.assertFalse(any(c[0] == "curl" for c in calls))

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
