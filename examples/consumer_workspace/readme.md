# consumer_workspace

A [Conan workspace](https://docs.conan.io/2/tutorial/developing_packages/workspaces.html)
with two local packages: `dummy_lib` and `consumer_node`. Workspace packages are
treated as editables. ROS dependencies (`rclcpp`) come from the generated Kilted
recipes.

This is the Conan equivalent of [consumer_colcon](../consumer_colcon): local
packages live in the workspace, while ROS comes from Conan. There is no colcon
and no `ament_cmake`. Workspaces are experimental in Conan 2.

Needs a C++17 compiler, CMake ≥ 3.22 and Conan 2. The script registers
`./kilted` as a local recipes index and uses `profiles/ros`.

```bash
python run.py
```

Expected log lines:

```text
[dummy_lib] hello from workspace library
[INFO] [...] [conan_workspace_consumer_node]: Conan workspace consumer_node: rclcpp linked and node started.
```

Optional: `conan workspace super-install` plus the generated CMake presets, if
you want a single super-build instead of the orchestrated per-package build
the script runs.
