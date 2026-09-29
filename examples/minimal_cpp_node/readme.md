# minimal_cpp_node

A reduced [gopigo-ros-robot](https://github.com/danimtb/gopigo-ros-robot) node:
plain CMake, no colcon, no hardware. The program publishes `std_msgs/String`
and subscribes to `geometry_msgs/Twist`. The Conan file and `CMakeLists.txt`
are the whole integration; `src/main.cpp` only exercises those libraries.

`rclcpp`, `geometry_msgs` and `std_msgs` come from the generated Kilted
recipes. Their dependency closure is what a C++ node needs.

Needs a C++17 compiler, CMake ≥ 3.22 and Conan 2. The script registers
`./kilted` as a local recipes index and uses `profiles/ros`.

```bash
python run.py
```

Expected log line:

```text
[INFO] [...] [minimal_cpp_node]: minimal C++ node: publishing /status, subscribing /cmd_vel
```
