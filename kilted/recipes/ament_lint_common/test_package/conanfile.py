from conan import ConanFile


class AmentLintCommonTestConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        for cmd in ["ament_copyright --help", "ament_cppcheck --help", "ament_cpplint --help", "ament_xmllint --help", "ament_uncrustify --help"]:
            self.run(cmd, env=["conanrun"])
