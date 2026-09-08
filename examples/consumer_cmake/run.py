#!/usr/bin/env python3
"""Build consumer_cmake against the kilted index and run the node."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.chdir(HERE)

from examples_tools import PROFILE, PS_CONF, WINDOWS, add_remote, run  # noqa: E402

add_remote()

run(f'conan install . --profile:all "{PROFILE}" --build=missing {PS_CONF}')
run(f'conan build . --profile:all "{PROFILE}"')

if WINDOWS:
    run(r". .\build\generators\conanrun.ps1; .\build\Release\consumer_node.exe")
else:
    run(". ./build/Release/generators/conanrun.sh; ./build/Release/consumer_node")
