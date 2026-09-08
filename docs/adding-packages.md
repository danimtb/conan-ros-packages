# Adding packages

Coverage starts from the root packages in `<distro>/distro.yaml`. The
generator includes those packages and everything their `package.xml`
dependencies pull in. Adding a package is a pull request that edits the list
and regenerates the lock and recipes.

Everything a distro needs lives in `<distro>/`. Commands take `--distro`.

## Add a ROS package

1. Add it to the `packages` list in `<distro>/distro.yaml`.
2. Regenerate:

```bash
python tools/gen_ros_recipes.py --distro kilted --lock
```

3. If the generator stops on unmapped keys, add them to the same
   `distro.yaml` (`requires`, `tool_requires`, `pip_packages`, `ignore`, or
   `skip_packages`) and run `--lock` again.
4. Commit `distro.yaml`, `packages.lock.yaml` and the generated `recipes/`.

`packages.lock.yaml` is the reviewable diff: one line per package, with
version and build type. Its `requested_packages` field records the roots whose
transitive closure produced the recipes.

CI regenerates the index to detect drift, then installs all requested roots as
one Conan graph. That builds the complete generated dependency closure.

Do not commit hidden outputs: `.downloads/`, `.generated/`, `.report.json`,
`.build/`.

## Add a third-party CMake package

Libraries that are not ROS packages (for example Orocos KDL) go in
`<distro>/extra/<name>/` as a local-recipes-index recipe (`config.yml` plus
`all/conanfile.py`). Set `user` to the distro Conan user (for kilted,
`ros-kilted`). The generator copies them into `recipes/` on `--lock`. Map
any keys that should consume them in `distro.yaml`.

## Consume the index

```bash
conan remote add ros-kilted ./kilted --type=local-recipes-index
conan install --requires=rclcpp/29.5.8@ros-kilted --build=missing -pr:a profiles/ros
```

See `examples/consumer_cmake`, `examples/consumer_colcon` and
`examples/consumer_workspace`. Each example is run with `python run.py`.

## Add a distro

Create `<repo>/<distro>/` with `distro.yaml`. Third-party CMake libraries that
are not ROS packages go in `<distro>/extra/<name>/`. Then:

```bash
python tools/gen_ros_recipes.py --distro jazzy --lock
conan remote add ros-jazzy ./jazzy --type=local-recipes-index
```
