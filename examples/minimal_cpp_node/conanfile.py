from conan import ConanFile
from conan.tools.cmake import cmake_layout


class MinimalCppNodeConan(ConanFile):
    """Consumer for a C++ node. The requirements are the whole ROS surface."""

    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"

    def layout(self):
        cmake_layout(self)

    def requirements(self):
        self.requires("rclcpp/29.5.8@ros-kilted")
        self.requires("geometry_msgs/5.5.2@ros-kilted")
        self.requires("std_msgs/5.5.2@ros-kilted")
