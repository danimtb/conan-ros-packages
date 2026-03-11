import os

from conan import ConanFile
from conan.tools.system import PyEnv


class TestConan(ConanFile):
    settings = "os"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        venv = PyEnv(self)
        venv.generate()
        self.run("set", env=["conanrun"])
        self.run(f"{venv.env_exe} src/example.py", env=["conanrun"])
        self.run(f"{venv.env_exe} -m pip list", env=["conan_pipenv", "conanrun"])
