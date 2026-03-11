cmake_minimum_required(VERSION 3.15)
project(ament_cmake_core CXX)




add_library(ament_cmake_core src/ament_cmake_core.cpp)
target_include_directories(ament_cmake_core PUBLIC include)



set_target_properties(ament_cmake_core PROPERTIES PUBLIC_HEADER "include/ament_cmake_core.h")
install(TARGETS ament_cmake_core)
