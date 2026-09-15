#!/usr/bin/env python3
"""Install the ROS dependencies with Conan, colcon-build the workspace, run the node."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.chdir(HERE)

from examples_tools import PROFILE, WINDOWS, add_remote, run  # noqa: E402

# colcon is the workspace tool, not a ROS package in the kilted index.
# PowerShell treats a leading quoted path as a string, not an invocation.
python = f'& "{sys.executable}"' if WINDOWS else f'"{sys.executable}"'
run(f"{python} -m pip install -q colcon-common-extensions")

add_remote()

# No powershell conf: ROSEnv's conanrosenv.bat calls conanbuild.bat / conanrun.bat.
run(f'conan install . --output-folder=.conan --profile:all "{PROFILE}" --build=missing')

if WINDOWS:
    rosenv = r"call .\.conan\conanrosenv.bat"
    run(rf'cmd /c "{rosenv} && colcon build --symlink-install"')
    run(rf'cmd /c "{rosenv} && call .\install\setup.bat && '
        r'.\install\consumer_node\lib\consumer_node\consumer_node.exe"')
else:
    run(". ./.conan/conanrosenv.sh; colcon build --symlink-install")
    run(". ./.conan/conanrosenv.sh; . ./install/setup.bash; "
        "./install/consumer_node/lib/consumer_node/consumer_node")
