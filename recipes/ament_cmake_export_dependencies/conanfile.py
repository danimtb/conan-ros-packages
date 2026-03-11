import os

from conan import ConanFile
from conan.tools.files import get
from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps


class ament_cmakeecipe(ConanFile):
    name = "ament_cmake_export_dependencies"
    package_type = "build-scripts"
    settings = "os", "arch", "compiler", "build_type"

    def set_version(self):
        self.version = list(self.conan_data["sources"].keys())[0]

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.tool_requires("ament_cmake_core/2.7.4")
        self.tool_requires("ament_cmake_libraries/2.7.4")

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

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
        self.cpp_info.build_dirs = [os.path.join("share", "ament_cmake_core", "cmake")]
