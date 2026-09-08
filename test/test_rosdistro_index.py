from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import rosdistro_index as rdi  # noqa: E402


class DistroConfigTest(unittest.TestCase):
    def _write_distro(self, root: Path, packages: str) -> None:
        distro = root / "test"
        distro.mkdir()
        (distro / "distro.yaml").write_text(
            "\n".join(
                [
                    "rosdistro_tag: test/tag",
                    "cache_url: https://example.test/cache.yaml.gz",
                    "conan_user: ros-test",
                    packages,
                ]
            ),
            encoding="utf-8",
        )

    def test_loads_root_packages_in_declaration_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_distro(root, "packages: [desktop, perception]")

            config = rdi.DistroConfig.load("test", root)

            self.assertEqual(config.packages, ["desktop", "perception"])

    def test_kilted_input_file_holds_packages_and_requires(self):
        config = rdi.DistroConfig.load("kilted")
        self.assertEqual(config.packages, ["desktop", "perception"])
        data = rdi._read_yaml(config.rosdep_map_path)
        self.assertIn("liborocos-kdl-dev", data["requires"])
        self.assertFalse(config.root.joinpath("rosdep.yaml").exists())

    def test_rejects_an_empty_package_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_distro(root, "packages: []")

            with self.assertRaisesRegex(rdi.DistroError, "non-empty packages list"):
                rdi.DistroConfig.load("test", root)

    def test_rejects_duplicate_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_distro(root, "packages: [desktop, desktop]")

            with self.assertRaisesRegex(rdi.DistroError, "duplicate package names"):
                rdi.DistroConfig.load("test", root)


class ClosureTest(unittest.TestCase):
    def test_includes_all_transitive_dependencies_of_every_root(self):
        xmls = {
            "desktop": "<package><depend>common</depend></package>",
            "perception": "<package><exec_depend>vision</exec_depend></package>",
            "common": "<package><build_depend>foundation</build_depend></package>",
            "vision": "<package/>",
            "foundation": "<package/>",
        }

        packages = rdi.closure(["desktop", "perception"], xmls)

        self.assertEqual(
            packages,
            {"desktop", "perception", "common", "vision", "foundation"},
        )


if __name__ == "__main__":
    unittest.main()
