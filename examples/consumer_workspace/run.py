#!/usr/bin/env python3
"""Build the Conan workspace against the kilted index and run the node."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.chdir(HERE)

from examples_tools import PROFILE, PS_CONF, WINDOWS, add_remote, run  # noqa: E402

add_remote()

run(f'conan workspace build --profile:all "{PROFILE}" --build=missing {PS_CONF}')

if WINDOWS:
    run(r". .\consumer_node\build\generators\conanrun.ps1; "
        r".\consumer_node\build\Release\consumer_node.exe")
else:
    run(". ./consumer_node/build/Release/generators/conanrun.sh; "
        "./consumer_node/build/Release/consumer_node")
