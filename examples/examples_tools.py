"""Shared helpers for the example run.py scripts.

Each example is a linear list of the commands its readme documents. The only
platform difference is the shell: PowerShell on Windows, because a ROS graph
does not fit in the environment cmd.exe gives to a .bat activation script.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS = platform.system() == "Windows"
REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "kilted"
PROFILE = REPO / "profiles" / "ros"
# Ask Conan for .ps1 activation scripts instead of the default .bat ones.
PS_CONF = "-c tools.env.virtualenv:powershell=powershell.exe" if WINDOWS else ""


def _windows_base_path() -> str:
    """A PATH short enough that conanrun.ps1 can prepend every package bindir.

    GitHub-hosted runners start with several KB of tool PATH. VirtualRunEnv then
    prepends `bin` for every `run=True` requirement. `set PATH=` is capped at
    8191 characters; the assignment fails, rclcpp.dll stays invisible, and the
    process exits 0xC0000135 (STATUS_DLL_NOT_FOUND).
    """
    py = Path(sys.executable).resolve().parent
    parts = [r"C:\Windows\system32", r"C:\Windows", str(py)]
    scripts = py / "Scripts"
    if scripts.is_dir():
        parts.append(str(scripts))
    cmake = shutil.which("cmake")
    if cmake:
        parts.append(str(Path(cmake).resolve().parent))
    return ";".join(dict.fromkeys(parts))


def run(cmd: str, *, reset_path: bool = False) -> None:
    """Run one shell command in the current directory, echoing it first."""
    if WINDOWS and reset_path:
        cmd = f"$env:PATH = '{_windows_base_path()}'; {cmd}"
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
