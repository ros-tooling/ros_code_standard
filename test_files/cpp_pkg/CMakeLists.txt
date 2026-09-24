# Copyright 2026 Polymath Robotics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

cmake_minimum_required(VERSION 3.16)
project(cpp_pkg)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

add_library(cpp_pkg src/greeter.cpp)
target_compile_features(cpp_pkg PUBLIC cxx_std_17)
target_include_directories(cpp_pkg PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include/cpp_pkg>")
ament_target_dependencies(cpp_pkg PUBLIC rclcpp)

install(DIRECTORY include/ DESTINATION include/cpp_pkg)
install(
  TARGETS cpp_pkg
  EXPORT export_cpp_pkg
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)

# The ament_lint_auto block that normally lives here is gone on purpose: the
# linters run as pre-commit hooks instead. See the repository README.

ament_export_targets(export_cpp_pkg HAS_LIBRARY_TARGET)
ament_export_dependencies(rclcpp)
ament_package()
