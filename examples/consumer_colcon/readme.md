# consumer_colcon

A small colcon workspace: `dummy_lib` and `consumer_node`. ROS dependencies
come from the generated Kilted recipes through a hand-written `conanfile.txt`
and Conan's `ROSEnv` generator. Source `conanrosenv.sh` before `colcon build`.

Needs a C++17 compiler, CMake ≥ 3.22, Conan 2 and Python. colcon is not part of
the kilted recipe index; the script installs it from PyPI. It registers `./kilted`
as a local recipes index and uses `profiles/ros`.

On Windows, `conanrosenv.bat` cannot be used: `cmd.exe` truncates `PATH` at 8191
characters, which this graph exceeds (`The input line is too long`). The script
writes the same wrapper as a `.ps1` over Conan's PowerShell env files.

```bash
python run.py
```

`dummy_lib` is workspace-local. `ament_cmake` and `rclcpp` resolve from `ros-kilted`.
