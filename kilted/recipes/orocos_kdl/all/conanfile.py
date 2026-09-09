import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import get, replace_in_file, copy


class OrocosKdlConan(ConanFile):
    """Third-party CMake recipe, copied from extra/ into the distro index."""

    name = "orocos_kdl"
    version = "1.5.1"
    user = "ros-kilted"
    license = 'LGPL-2.1-or-later'
    settings = "os", "compiler", "build_type", "arch"

    options = {
        "shared": [True, False],
    }
    default_options = {
        "shared": True,
    }

    def config_options(self):
        if self.settings.get_safe("os") == "Windows":
            self.options.shared = False

    def validate(self):
        if self.options.shared and self.settings.os == "Windows":
            raise ConanInvalidConfiguration(
                "orocos_kdl: shared is not supported on Windows"
            )

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        self.requires(
            "eigen/3.4.0",
            transitive_headers=True,
            transitive_libs=True,
        )
        self.requires(
            "boost/1.83.0",
            transitive_headers=True,
            transitive_libs=True,
            options={"without_python": False},
        )

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.16 <4]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        replace_in_file(
            self,
            os.path.join(self.source_folder, 'orocos_kdl/src/CMakeLists.txt'),
            'ELSE(MSVC)\n    SET(LIB_TYPE SHARED)\nENDIF(MSVC)',
            'ELSE(MSVC)\n    if(BUILD_SHARED_LIBS)\n        SET(LIB_TYPE SHARED)\n    else()\n        SET(LIB_TYPE STATIC)\n    endif()\nENDIF(MSVC)',
        )

    def generate(self):
        CMakeDeps(self).generate()
        tc = CMakeToolchain(self)
        tc.cache_variables["BUILD_SHARED_LIBS"] = self.options.shared
        tc.cache_variables["ENABLE_TESTS"] = False
        tc.cache_variables["ENABLE_EXAMPLES"] = False
        tc.cache_variables["KDL_USE_NEW_TREE_INTERFACE"] = False
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(self.source_folder, "orocos_kdl"))
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

        copy(
            self,
            "COPYING",
            os.path.join(self.source_folder, "orocos_kdl"),
            os.path.join(self.package_folder, "licenses"),
        )

    def package_info(self):
        self.cpp_info.set_property("cmake_file_name", "orocos_kdl")
        self.cpp_info.set_property("cmake_target_name", "orocos-kdl")
        self.cpp_info.libs = ['orocos-kdl']
        self.cpp_info.requires = ['eigen::eigen', 'boost::boost']
