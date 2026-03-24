from conan import ConanFile
from conan.tools.system import PyEnv


class AmentPackageTestConan(ConanFile):
    settings = "os"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        venv = PyEnv(self)
        venv.generate()
        self.run(f"{venv.env_exe} src/example.py", env=["conanrun"])
