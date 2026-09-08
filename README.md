# ROS Conan recipes

Generated [Conan](https://conan.io) recipes for ROS 2 distributions. Each
distribution is a [local recipes index](https://docs.conan.io/2/devops/devops_local_recipes_index.html):

```
kilted/
  distro.yaml            # snapshot, roots, and non-ROS dependency map
  extra/                 # hand-written recipes (orocos_kdl, …)
  packages.lock.yaml
  recipes/               # generated, plus a copy of extra/
```

```bash
conan remote add ros-kilted ./kilted --type=local-recipes-index
conan install --requires=rclcpp/29.5.8@ros-kilted --build=missing -pr:a profiles/ros
```

`profiles/ros` overlays C++17 and CMake 3.29.3 on the detected default profile.

Regenerate a distro with `python tools/gen_ros_recipes.py --distro kilted --lock`.
`distro.yaml` lists the root ROS packages; their complete transitive dependency
closure is generated into `recipes/` and built by CI.
How to add packages: [docs/adding-packages.md](docs/adding-packages.md).

Examples of consuming the index (each is `python run.py`):
[examples/consumer_cmake](examples/consumer_cmake),
[examples/consumer_colcon](examples/consumer_colcon),
[examples/consumer_workspace](examples/consumer_workspace).
