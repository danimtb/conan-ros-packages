import os
import glob
import sys

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import get, apply_conandata_patches, copy
from conan.tools.system import PyEnv


class PythonOrocosKdlConan(ConanFile):
    """Third-party CMake recipe, copied from extra/ into the distro index."""

    name = "python_orocos_kdl"
    version = "1.5.1"
    user = "ros-kilted"
    license = 'LGPL-2.1-or-later'
    settings = "os", "compiler", "build_type", "arch"

    options = {"python_version": ["ANY"]}
    default_options = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    exports_sources = "conandata.yml", "patches/*"

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        self.requires(
            "orocos_kdl/1.5.1@ros-kilted",
            transitive_headers=True,
            transitive_libs=True,
            run=True,
        )
        self.requires(
            "pybind11/2.11.1",
            transitive_headers=True,
            transitive_libs=True,
        )
        self.requires(
            "eigen/3.4.0",
            transitive_headers=True,
            transitive_libs=True,
        )
        self.requires(
            "boost/1.83.0",
            transitive_headers=True,
            transitive_libs=True,
        )

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        apply_conandata_patches(self)

    def generate(self):
        pyenv = PyEnv(self, py_version=str(self.options.python_version))
        pyenv.generate()
        CMakeDeps(self).generate()
        tc = CMakeToolchain(self)
        tc.cache_variables["Python3_EXECUTABLE"] = pyenv.env_exe
        tc.cache_variables["CMAKE_INSTALL_RPATH_USE_LINK_PATH"] = True
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=os.path.join(self.source_folder, "python_orocos_kdl"))
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
        self.cpp_info.set_property("cmake_file_name", "python_orocos_kdl")
        self.cpp_info.set_property("cmake_target_name", "python_orocos_kdl::python_orocos_kdl")
        pkg = self.package_folder
        site_packages = [os.path.join(pkg, "Lib", "site-packages")] + sorted(
            glob.glob(os.path.join(pkg, "lib", "python*", "site-packages"))
            + glob.glob(os.path.join(pkg, "lib", "python*", "dist-packages"))
        )
        def _prepend_pythonpath(path):
            if os.path.isdir(path):
                self.runenv_info.prepend_path("PYTHONPATH", path)
                self.buildenv_info.prepend_path("PYTHONPATH", path)
        for site in site_packages:
            _prepend_pythonpath(site)
