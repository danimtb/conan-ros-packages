cmake_minimum_required(VERSION 3.22)
project(consumer_node CXX)

find_package(dummy_lib CONFIG REQUIRED)
find_package(rclcpp REQUIRED)

add_executable(consumer_node src/main.cpp)
target_link_libraries(consumer_node PRIVATE dummy_lib::dummy_lib rclcpp::rclcpp)

install(TARGETS consumer_node DESTINATION "."
        RUNTIME DESTINATION bin
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib)
