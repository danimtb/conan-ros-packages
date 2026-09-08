from conan import ConanFile, Workspace
from conan.tools.cmake import CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.env import VirtualRunEnv
from conan.tools.files import save


class MyWs(ConanFile):
    """Super-project recipe used only by `conan workspace super-install`.

    It must not declare requirements or implement build()/package().
    External deps (rclcpp, …) are collected from the workspace packages.
    """

    settings = "os", "compiler", "build_type", "arch"

    def generate(self):
        CMakeDeps(self).generate()
        CMakeToolchain(self).generate()
        VirtualRunEnv(self).generate()

    def layout(self):
        cmake_layout(self)


class Ws(Workspace):
    def root_conanfile(self):
        return MyWs

    def build_order(self, order):
        super().build_order(order)
        pkglist = " ".join(
            f'{it["ref"].name}:{it["folder"]}' for level in order for it in level
        )
        save(self, "build/conanws_build_order.cmake", f"set(CONAN_WS_BUILD_ORDER {pkglist})")
