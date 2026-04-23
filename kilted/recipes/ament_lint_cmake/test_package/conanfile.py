from conan import ConanFile


class AmentLintCmakeTestConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        for cmd in ["ament_lint_cmake --help"]:
            self.run(cmd, env=["conanrun"])
