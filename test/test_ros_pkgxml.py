from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ros_pkgxml  # noqa: E402


def _write_pkg(
    root: Path,
    name: str,
    build_type: str | None = "ament_cmake",
    cmake: str = "",
    setup: str = "",
) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        '<?xml version="1.0"?>',
        '<package format="3">',
        f"  <name>{name}</name>",
        "  <version>0.0.0</version>",
        "  <license>MIT</license>",
    ]
    if build_type:
        lines.append(f"  <export><build_type>{build_type}</build_type></export>")
    lines.append("</package>")
    (pkg_dir / "package.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if cmake:
        (pkg_dir / "CMakeLists.txt").write_text(cmake, encoding="utf-8")
    if setup:
        (pkg_dir / "setup.py").write_text(setup, encoding="utf-8")
    return pkg_dir


class TestRosPkgXml(unittest.TestCase):
    def test_parse_and_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _write_pkg(Path(tmp), "foo", build_type="ament_cmake_python")
            manifest = ros_pkgxml.parse_package_manifest(pkg / "package.xml")
            self.assertEqual(manifest.build_type, ros_pkgxml.AMENT_CMAKE)

    def test_build_type_inferred_from_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cmake = _write_pkg(root, "lib", build_type=None)
            (cmake / "CMakeLists.txt").write_text("project(lib)\n", encoding="utf-8")
            self.assertEqual(
                ros_pkgxml.parse_package_manifest(cmake / "package.xml").build_type,
                ros_pkgxml.CMAKE,
            )
            py = _write_pkg(root, "mod", build_type=None)
            (py / "setup.py").write_text("from setuptools import setup\nsetup()\n", encoding="utf-8")
            self.assertEqual(
                ros_pkgxml.parse_package_manifest(py / "package.xml").build_type,
                ros_pkgxml.PYTHON,
            )

    def test_render_recipe_from_source(self):
        spec = ros_pkgxml.RecipeSpec(
            name="ament_cmake_core",
            version="2.7.5",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="ament_cmake",
            from_source=True,
            requires=[ros_pkgxml.RecipeRequire("ament_package/0.17.3@ros-kilted", run=True)],
            tool_requires=["cmake/3.29.3"],
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn('get(self, **self.conan_data["sources"][self.version]', text)
        self.assertIn('cmake_layout(self, src_folder="src")', text)
        self.assertIn('self.tool_requires("cmake/3.29.3")', text)
        self.assertIn('tc.variables["BUILD_TESTING"] = False', text)
        self.assertNotIn("exports_sources", text)
        self.assertIn("CMAKE_PREFIX_PATH", text)
        self.assertNotIn("self.buildenv_info.prepend_path(\"CMAKE_PREFIX_PATH\"", text)

    def test_render_recipe_without_requires(self):
        spec = ros_pkgxml.RecipeSpec(
            name="ament_package",
            version="0.17.3",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="ament_python",
            from_source=True,
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertNotIn("def requirements", text)
        self.assertIn("AMENT_PREFIX_PATH", text)

    def test_render_pip_recipe(self):
        spec = ros_pkgxml.RecipeSpec(
            name="catkin_pkg",
            version="1.1.0",
            user="ros-kilted",
            license="unknown",
            build_type=ros_pkgxml.PIP,
            pip_install="catkin_pkg==1.1.0",
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("pip install catkin_pkg==1.1.0", text)
        self.assertIn("PYTHONPATH", text)
        self.assertNotIn("CMakeToolchain", text)

    def test_pkg_config_and_vendored_prefix(self):
        spec = ros_pkgxml.RecipeSpec(
            name="theora_image_transport",
            version="0.0.0",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="ament_cmake",
            from_source=True,
            pkg_config=True,
            vendored_prefix=True,
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("PkgConfigDeps", text)
        self.assertIn('os.path.join(pkg, "opt", self.name)', text)

    def test_patches_are_applied_in_source(self):
        spec = ros_pkgxml.RecipeSpec(
            name="foo",
            version="1.0.0",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="cmake",
            from_source=True,
            patches=[{"file": "CMakeLists.txt", "search": "OLD", "replace": "NEW"}],
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("replace_in_file", text)
        self.assertIn("OLD", text)

    def test_cmake_none_project_is_arch_independent(self):
        self.assertTrue(ros_pkgxml.cmake_declares_no_languages("project(foo NONE)\n"))
        self.assertFalse(ros_pkgxml.cmake_declares_no_languages("project(rcutils)\n"))

    def test_arch_independent_cmake_recipe_drops_compiler_settings(self):
        spec = ros_pkgxml.RecipeSpec(
            name="ament_cmake_core",
            version="2.7.5",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="ament_cmake",
            from_source=True,
            arch_independent=True,
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("del self.info.settings.compiler", text)
        self.assertIn("del self.info.settings.arch", text)

    def test_python_extension_recipe_pins_the_interpreter(self):
        spec = ros_pkgxml.RecipeSpec(
            name="rclpy",
            version="1.0.0",
            user="ros-kilted",
            license="Apache-2.0",
            build_type="ament_python",
            from_source=True,
            python_extension=True,
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("python_version", text)

    def test_detectors_read_package_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = _write_pkg(
                Path(tmp),
                "macros",
                cmake="project(macros NONE)\n",
            )
            read = ros_pkgxml.package_file_reader(pkg)
            self.assertTrue(ros_pkgxml.is_arch_independent("ament_cmake", read))
            vendor = _write_pkg(
                Path(tmp),
                "vendor",
                cmake="project(vendor)\nament_vendor(foo)\n",
            )
            self.assertTrue(
                ros_pkgxml.installs_vendored_prefix(
                    "ament_cmake", ros_pkgxml.package_file_reader(vendor)
                )
            )

    def test_external_cmake_recipe_configures_a_subdir(self):
        spec = ros_pkgxml.RecipeSpec(
            name="orocos_kdl",
            version="1.5.1",
            user="ros-kilted",
            license="LGPL-2.1-or-later",
            build_type=ros_pkgxml.EXTERNAL_CMAKE,
            from_source=True,
            shared_option=True,
            build_folder="orocos_kdl",
            license_file="orocos_kdl/COPYING",
            cmake_variables={"ENABLE_TESTS": "False"},
            cmake_file_name="orocos_kdl",
            cmake_target_name="orocos-kdl",
            libs=["orocos-kdl"],
            patches=[{"file": "orocos_kdl/src/CMakeLists.txt", "search": "OLD", "replace": "NEW"}],
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("class ExternalCMakeConan", text)
        self.assertIn('build_script_folder=os.path.join(self.source_folder, "orocos_kdl")', text)
        self.assertIn("BUILD_SHARED_LIBS", text)
        self.assertIn("replace_in_file", text)
        self.assertIn("orocos-kdl", text)
        self.assertNotIn("AMENT_PREFIX_PATH", text)

    def test_external_cmake_python_extension_uses_pyenv(self):
        spec = ros_pkgxml.RecipeSpec(
            name="python_orocos_kdl",
            version="1.5.1",
            user="ros-kilted",
            license="LGPL-2.1-or-later",
            build_type=ros_pkgxml.EXTERNAL_CMAKE,
            from_source=True,
            python_extension=True,
            pyenv=True,
            pythonpath=True,
            file_patches=[{"patch_file": "patches/0001.patch", "patch_description": "x"}],
        )
        text = ros_pkgxml.render_recipe(spec)
        self.assertIn("apply_conandata_patches", text)
        self.assertIn("PyEnv", text)
        self.assertIn("python_version", text)
        self.assertIn("PYTHONPATH", text)
        self.assertIn("exports_sources", text)


if __name__ == "__main__":
    unittest.main()
