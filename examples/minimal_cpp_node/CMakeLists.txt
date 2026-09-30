cmake_minimum_required(VERSION 3.22)
project(minimal_cpp_node CXX)

find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

add_executable(minimal_cpp_node src/main.cpp)

# Message packages ship ament config files, not a Conan CMakeDeps target.
# geometry_msgs_TARGETS and std_msgs_TARGETS are the interface libraries those
# configs export (typesupport included).
target_link_libraries(minimal_cpp_node PRIVATE
    rclcpp::rclcpp
    ${geometry_msgs_TARGETS}
    ${std_msgs_TARGETS})
