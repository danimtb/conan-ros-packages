cmake_minimum_required(VERSION 3.22)
project(dummy_lib CXX)

add_library(dummy_lib src/print.cpp)
target_include_directories(dummy_lib PUBLIC include)

install(TARGETS dummy_lib)
install(DIRECTORY include/ DESTINATION include)
