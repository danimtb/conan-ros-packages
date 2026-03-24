from conan import ConanFile


class {{test_recipe_class}}(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        self.run({{command_repr}}, env=["conanrun"])
