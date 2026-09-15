#!/usr/bin/env python3
"""Install the ROS dependencies with Conan, colcon-build the workspace, run the node."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.chdir(HERE)

from examples_tools import PROFILE, PS_CONF, WINDOWS, add_remote, run  # noqa: E402

# colcon is the workspace tool, not a ROS package in the kilted index.
# PowerShell treats a leading quoted path as a string, not an invocation.
python = f'& "{sys.executable}"' if WINDOWS else f'"{sys.executable}"'
run(f"{python} -m pip install -q colcon-common-extensions")

add_remote()

run(f'conan install . --output-folder=.conan --profile:all "{PROFILE}" --build=missing {PS_CONF}')

if WINDOWS:
    # ROSEnv only emits conanrosenv.bat, which hits cmd's 8191-character PATH cap.
    # Same wrapper as the .bat, using the PowerShell env scripts Conan already wrote.
    toolchain = (HERE / ".conan" / "conan_toolchain.cmake").as_posix()
    (HERE / ".conan" / "conanrosenv.ps1").write_text(
        f'$env:CMAKE_TOOLCHAIN_FILE = "{toolchain}"\n'
        '$env:CMAKE_BUILD_TYPE = "Release"\n'
        '. "$PSScriptRoot\\conanbuild.ps1"\n'
        '. "$PSScriptRoot\\conanrun.ps1"\n',
        encoding="utf-8",
        newline="\n",
    )
    run(r". .\.conan\conanrosenv.ps1; colcon build --symlink-install")
    run(r". .\.conan\conanrosenv.ps1; . .\install\setup.ps1; "
        r".\install\consumer_node\lib\consumer_node\consumer_node.exe")
else:
    run(". ./.conan/conanrosenv.sh; colcon build --symlink-install")
    run(". ./.conan/conanrosenv.sh; . ./install/setup.bash; "
        "./install/consumer_node/lib/consumer_node/consumer_node")
