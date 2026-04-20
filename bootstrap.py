"""Bootstrap launcher for iCloud Mail Manager MCP extension.

This script ensures required Python dependencies are available before starting server.py.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path


REQUIRED_IMPORTS = {
    "dotenv": "python-dotenv>=1.0.1",
    "mcp": "mcp>=1.2.0",
}


def _log(message: str) -> None:
    print(f"[icloud-mail-manager bootstrap] {message}", file=sys.stderr)


def _module_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _install_dependency(pip_spec: str) -> bool:
    _log(f"Installing missing dependency: {pip_spec}")
    cmd = [sys.executable, "-m", "pip", "install", "--user", pip_spec]
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            return True

        # Homebrew Python may block installation due to PEP 668.
        retry_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--break-system-packages",
            pip_spec,
        ]
        _log(f"Retrying installation with --break-system-packages for: {pip_spec}")
        retry = subprocess.run(retry_cmd, check=False)
        if retry.returncode == 0:
            return True

        _log(f"Installation failed for {pip_spec} (exit code {retry.returncode})")
        return False
    except Exception as exc:
        _log(f"Installation error for {pip_spec}: {exc}")
        return False


def _ensure_dependencies() -> bool:
    missing = [(module_name, pip_spec) for module_name, pip_spec in REQUIRED_IMPORTS.items() if not _module_available(module_name)]
    if not missing:
        return True

    _log("Some dependencies are missing. Attempting one-time installation.")

    all_ok = True
    for _, pip_spec in missing:
        ok = _install_dependency(pip_spec)
        all_ok = all_ok and ok

    return all_ok


def main() -> int:
    server_path = Path(__file__).with_name("server.py")
    if not server_path.exists():
        _log(f"server.py not found: {server_path}")
        return 1

    deps_ok = _ensure_dependencies()
    if not deps_ok:
        _log("Unable to install required dependencies automatically.")
        _log("Please install manually with:")
        _log(f"{sys.executable} -m pip install --user mcp python-dotenv")
        return 1

    argv = [sys.executable, str(server_path), *sys.argv[1:]]
    os.execv(sys.executable, argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
