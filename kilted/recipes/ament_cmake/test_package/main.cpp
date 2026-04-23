#include <iostream>
// This header is created by the ament_generate_version_header macro
#include "ament_cmake_test_package/version.h" 

int main() {
    std::cout << "--- Ament CMake Macro Test ---" << std::endl;
    
    // These constants are defined inside the generated version.h
    std::cout << "Project Name: " << "ament_cmake_test_package" << std::endl;
    std::cout << "Version: "      << AMENT_CMAKE_TEST_PACKAGE_VERSION_STR << std::endl;
    std::cout << "Major: "        << AMENT_CMAKE_TEST_PACKAGE_VERSION_MAJOR << std::endl;
    
    return 0;
}
