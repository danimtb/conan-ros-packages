from conan import ConanFile


class AmentXmllintTestConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        self.run("ament_xmllint --help", env=["conanrun"])
