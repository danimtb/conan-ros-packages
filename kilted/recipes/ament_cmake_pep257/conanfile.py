import os

from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import get
from conan.tools.system import PyEnv


class AmentCmakePep257Recipe(ConanFile):
    name = "ament_cmake_pep257"
    settings = "os", "arch", "compiler", "build_type"

    def set_version(self):
        self.version = list(self.conan_data["sources"].keys())[0]

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        if self.conan_data.get("requires"):
            for require in self.conan_data["requires"][self.version]:
                self.requires(require)
        if self.conan_data.get("tool_requires"):
            for tool_require in self.conan_data["tool_requires"][self.version]:
                self.tool_requires(tool_require)

    def generate(self):
        pyenv = PyEnv(self)
        pyenv.install(["catkin-pkg"])
        pyenv.generate()
        tc = CMakeToolchain(self)
        tc.cache_variables["BUILD_TESTING"] = False
        tc.cache_variables["Python_ROOT_DIR"] = pyenv.env_dir
        tc.cache_variables["Python_EXECUTABLE"] = pyenv.env_exe
        tc.cache_variables["Python3_EXECUTABLE"] = pyenv.env_exe
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
        # Extend builddirs if the package installs extra cmake subfolders under share/<name>/cmake/.
        base_dir = os.path.join("share", "ament_cmake_pep257", "cmake")
        self.cpp_info.builddirs = [base_dir]
        self.cpp_info.set_property("cmake_find_mode", "none")
