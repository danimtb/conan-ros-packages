from conan import ConanFile


class AmentLintCmakeTestConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        self.run("ament_lint_cmake --help", env=["conanrun"])
