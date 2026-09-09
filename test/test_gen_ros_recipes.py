from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_ros_recipes  # noqa: E402
import ros_pkgxml  # noqa: E402
import rosdistro_index as rdi  # noqa: E402


class ReachableDepsTest(unittest.TestCase):
    """What a recipe needs from cmake_target_names is decided by its whole subtree.

    A target rename belongs in every recipe that generates the CMakeDeps files declaring
    the target, which is not only the package linking the library: a vendor package can
    bake the target name into its exported config and hand the problem to its consumers.
    """

    GRAPH = {
        "rosbag2": {"rosbag2_storage_mcap", "rclcpp"},
        "rosbag2_storage_mcap": {"mcap_vendor"},
        "mcap_vendor": {"mcap", "lz4", "zstd"},
        "rclcpp": {"rcl"},
        "rcl": set(),
    }

    def _reachable(self, package):
        return gen_ros_recipes._reachable_deps(package, self.GRAPH, {})

    def test_a_transitive_consumer_sees_the_dependency(self):
        self.assertIn("lz4", self._reachable("rosbag2"))

    def test_an_unrelated_package_does_not(self):
        self.assertNotIn("lz4", self._reachable("rclcpp"))

    def test_external_dependencies_are_leaves(self):
        self.assertEqual(self._reachable("rcl"), set())

    def test_a_cycle_terminates(self):
        graph = {"a": {"b"}, "b": {"a", "lz4"}}
        self.assertIn("lz4", gen_ros_recipes._reachable_deps("a", graph, {}))


class LockManifestTest(unittest.TestCase):
    def test_records_roots_without_variant_metadata(self):
        config = rdi.DistroConfig(
            name="test",
            root=Path("test"),
            rosdistro_tag="test/tag",
            cache_url="https://example.test/cache.yaml.gz",
            conan_user="ros-test",
            packages=["desktop", "perception"],
        )
        report = {
            "packages": [
                {
                    "name": "desktop",
                    "version": "1.2.3",
                    "build_type": "ament_cmake",
                }
            ],
            "pip_packages": [],
            "extra_packages": [],
        }

        lock = gen_ros_recipes.render_lock(config, report)

        self.assertIn("requested_packages: [desktop, perception]", lock)
        self.assertIn(
            "desktop: {version: 1.2.3, build_type: ament_cmake}",
            lock,
        )
        self.assertNotIn("variant", lock)


class LineEndingsTest(unittest.TestCase):
    """Generated files are byte-identical on Windows and Linux.

    Text written with the platform default would come out CRLF on Windows, so the drift
    check would fail for whoever did not regenerate on the same OS as the last commit.
    """

    SPEC = ros_pkgxml.RecipeSpec(
        name="ament_cmake_core",
        version="2.7.5",
        user="ros-test",
        license="Apache-2.0",
        build_type="ament_cmake",
        from_source=True,
    )

    def test_recipes_are_written_with_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            gen_ros_recipes._write_recipe(
                out, self.SPEC, source={"url": "https://example.test/x.tar.gz", "sha256": "0" * 64}
            )
            written = sorted((out / "recipes").rglob("*"))
            self.assertTrue([p for p in written if p.is_file()])
            for path in written:
                if path.is_file():
                    self.assertNotIn(b"\r", path.read_bytes(), path)

    def test_lock_is_written_with_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packages.lock.yaml"
            gen_ros_recipes._write(path, "a\nb\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")


class ExtraPackagesTest(unittest.TestCase):
    def test_extra_recipes_are_copied_with_the_distro_user(self):
        config = rdi.DistroConfig.load("kilted")
        extras = {package["name"]: package for package in gen_ros_recipes._extra_packages(config)}
        self.assertEqual(set(extras), {"orocos_kdl", "python_orocos_kdl"})
        self.assertEqual(extras["orocos_kdl"]["version"], "1.5.1")
        conanfile = extras["orocos_kdl"]["src"] / "all" / "conanfile.py"
        self.assertIn('user = "ros-kilted"', conanfile.read_text(encoding="utf-8"))
        pykdl = extras["python_orocos_kdl"]["src"] / "all" / "conanfile.py"
        self.assertIn('user = "ros-kilted"', pykdl.read_text(encoding="utf-8"))
        self.assertIn("orocos_kdl/1.5.1@ros-kilted", pykdl.read_text(encoding="utf-8"))
        rosdep_map = gen_ros_recipes.RosDepMap.load(config.rosdep_map_path)
        self.assertIn("python_orocos_kdl", rosdep_map.run_requires)

    def test_copy_extra_replaces_generated_recipe_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            extra = Path(tmp) / "extra" / "orocos_kdl"
            (extra / "all").mkdir(parents=True)
            (extra / "config.yml").write_text(
                "versions:\n  1.5.1:\n    folder: all\n", encoding="utf-8"
            )
            (extra / "all" / "conanfile.py").write_text(
                'user = "ros-kilted"\n', encoding="utf-8"
            )
            leftover = Path(tmp) / "recipes" / "orocos_kdl" / "conanfile.py"
            leftover.parent.mkdir(parents=True)
            leftover.write_text("generated\n", encoding="utf-8")
            gen_ros_recipes._copy_extra_recipes(
                Path(tmp),
                [{"name": "orocos_kdl", "src": extra}],
            )
            self.assertFalse(leftover.exists())
            self.assertTrue(
                (Path(tmp) / "recipes" / "orocos_kdl" / "all" / "conanfile.py").is_file()
            )

    def test_qualify_ref_only_rewrites_index_packages(self):
        self.assertEqual(
            gen_ros_recipes._qualify_ref("orocos_kdl/1.5.1", "ros-kilted", {"orocos_kdl"}),
            "orocos_kdl/1.5.1@ros-kilted",
        )
        self.assertEqual(
            gen_ros_recipes._qualify_ref("eigen/3.4.0", "ros-kilted", {"orocos_kdl"}),
            "eigen/3.4.0",
        )


if __name__ == "__main__":
    unittest.main()
