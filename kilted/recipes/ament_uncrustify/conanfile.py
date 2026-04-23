import os

from conan import ConanFile
from conan.tools.files import copy, get, load, rmdir
from conan.tools.system import PyEnv


class AmentUncrustifyRecipe(ConanFile):
    name = "ament_uncrustify"

    def set_version(self):
        self.version = list(self.conan_data["sources"].keys())[0]

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def package(self):
        copy(self, "*", src=self.source_folder, dst=self.package_folder)

    def package_info(self):
        self.buildenv_info.prepend_path("PYTHONPATH", self.package_folder)
        self.runenv_info.prepend_path("PYTHONPATH", self.package_folder)
        self.buildenv_info.prepend_path("PATH", self.package_folder)
        self.runenv_info.prepend_path("PATH", self.package_folder)

    def finalize(self):
        copy(self, "*", src=self.immutable_package_folder, dst=self.package_folder)
        setup_py_path = os.path.join(self.package_folder, "setup.py")
        if os.path.exists(setup_py_path):
            setup_py = load(self, setup_py_path)
            if "console_scripts" in setup_py:
                pyenv = PyEnv(self)
                self.run(f"{pyenv.env_exe} -m pip install .", cwd=self.package_folder)
                copy(self, "ament_uncrustify*", src=os.path.join(pyenv.env_dir, "Scripts"), dst=self.package_folder)
                #rmdir(self, pyenv.env_dir)  # Removing the pyevn directory causes the console scripts to not run
