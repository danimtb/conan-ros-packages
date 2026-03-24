from conan import ConanFile
from conan.tools.files import copy, get


class AmentPackageRecipe(ConanFile):
    name = "ament_package"

    def set_version(self):
        self.version = list(self.conan_data["sources"].keys())[0]

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def package(self):
        copy(self, "*", src=self.source_folder, dst=self.package_folder)

    def package_info(self):
        self.buildenv_info.prepend_path("PYTHONPATH", self.package_folder)
        self.runenv_info.prepend_path("PYTHONPATH", self.package_folder)

    def finalize(self):
        copy(self, "*", src=self.immutable_package_folder, dst=self.package_folder)
