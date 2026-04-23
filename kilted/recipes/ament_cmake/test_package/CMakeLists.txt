cmake_minimum_required(VERSION 3.8)
project(ament_cmake_test_package)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_gen_version_h REQUIRED)

add_executable(main main.cpp)

ament_generate_version_header(main)
ament_index_register_resource("special_demo_resource")

install(TARGETS main
  DESTINATION lib/${PROJECT_NAME})
ament_package()

