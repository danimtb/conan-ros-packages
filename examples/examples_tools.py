"""Shared helpers for the example run.py scripts.

Each example is a linear list of the commands its readme documents. The only
platform difference is the shell: PowerShell on Windows, because a ROS graph
does not fit in the environment cmd.exe gives to a .bat activation script.
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

WINDOWS = platform.system() == "Windows"
REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "kilted"
PROFILE = REPO / "profiles" / "ros"
# Ask Conan for .ps1 activation scripts instead of the default .bat ones.
PS_CONF = "-c tools.env.virtualenv:powershell=powershell.exe" if WINDOWS else ""


def run(cmd: str) -> None:
    """Run one shell command in the current directory, echoing it first."""
    print(f"\n$ {cmd}", flush=True)
    if WINDOWS:
        shell = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-Command", f"{cmd}; exit $LASTEXITCODE"]
    else:
        shell = ["bash", "-c", f"set -e; {cmd}"]
    subprocess.run(shell, check=True)


def add_remote() -> None:
    """Register this repository as the ros-kilted local-recipes-index."""
    run("conan profile detect --exist-ok")
    run(f'conan remote add ros-kilted "{INDEX}" --type=local-recipes-index --force')
