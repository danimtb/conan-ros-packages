# consumer_cmake

A plain CMake application that depends on `rclcpp` from the generated Kilted
recipes. There is no colcon and no `ament_cmake` in this project.

Needs a C++17 compiler, CMake ≥ 3.22 and Conan 2. The script registers
`./kilted` as a local recipes index and uses `profiles/ros`.

```bash
python run.py
```

Expected log line:

```text
[INFO] [...] [conan_test_package_node]: Conan consumer_node: rclcpp linked and node started.
```
