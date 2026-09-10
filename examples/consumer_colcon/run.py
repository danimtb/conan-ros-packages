#!/usr/bin/env python3
"""Install the ROS dependencies with Conan, colcon-build the workspace, run the node."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.chdir(HERE)

from examples_tools import PROFILE, PS_CONF, WINDOWS, add_remote, run  # noqa: E402

run(f'"{sys.executable}" -m pip install -q colcon-common-extensions')
add_remote()

run(f'conan install . --output-folder=.conan --profile:all "{PROFILE}" --build=missing {PS_CONF}')

toolchain = (HERE / ".conan" / "conan_toolchain.cmake").as_posix()

if WINDOWS:
    run(rf'. .\.conan\conanbuild.ps1; . .\.conan\conanrun.ps1; '
        rf'colcon build --symlink-install --cmake-args "-DCMAKE_TOOLCHAIN_FILE={toolchain}"',
        reset_path=True)
    run(r". .\.conan\conanrun.ps1; . .\install\setup.ps1; "
        r".\install\consumer_node\lib\consumer_node\consumer_node.exe",
        reset_path=True)
else:
    run(f'. ./.conan/conanbuild.sh; . ./.conan/conanrun.sh; '
        f'colcon build --symlink-install --cmake-args "-DCMAKE_TOOLCHAIN_FILE={toolchain}"')
    run(". ./.conan/conanrun.sh; . ./install/setup.bash; "
        "./install/consumer_node/lib/consumer_node/consumer_node")
