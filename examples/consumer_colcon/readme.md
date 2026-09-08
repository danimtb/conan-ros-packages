# consumer_colcon

A small colcon workspace: `dummy_lib` and `consumer_node`. ROS dependencies
come from the generated Kilted recipes through a hand-written `conanfile.txt`.

Needs a C++17 compiler, CMake ≥ 3.22, Conan 2 and Python. The script installs
colcon if needed, registers `./kilted` as a local recipes index and uses
`profiles/ros`. On Windows it generates PowerShell env scripts (the graph is
too large for cmd.exe).

```bash
python run.py
```

`dummy_lib` is workspace-local. `ament_cmake` and `rclcpp` resolve from `ros-kilted`.
