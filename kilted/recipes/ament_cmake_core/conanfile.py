import os

from conan import ConanFile
from conan.tools.files import get
from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps


class ament_cmake_coreRecipe(ConanFile):
    name = "ament_cmake_core"
    package_type = "build-scripts"
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeToolchain", "VirtualRunEnv"

    def set_version(self):
        self.version = list(self.conan_data["sources"].keys())[0]

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        for require in self.conan_data["requires"]["version"]:
            self.requires(require, visible=True)
        for tool_require in self.conan_data["tool_requires"]["version"]:
            self.tool_requires(tool_require, visible=True)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_id(self):
        self.info.clear()

    def package_info(self):
        base_dir = os.path.join("share", "ament_cmake_core", "cmake")
        self.cpp_info.builddirs = [base_dir]
        for folder in ["core", "environment", "environment_hooks", "index",
                       "package_templates", "symlink_install", "uninstall_target"]:
            self.cpp_info.builddirs.append(os.path.join(base_dir, folder))
