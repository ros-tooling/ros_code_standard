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

cmake_minimum_required(VERSION 3.22)
project(ros_uncrustify_bin LANGUAGES NONE)

include(ExternalProject)

# The two versions the ROS 2 distributions pin: 0.78.1 is what rolling and jazzy build through
# uncrustify_vendor, 0.72.0 is what Ubuntu 22.04 and humble ship.
set(UNCRUSTIFY_VERSIONS "0.78.1" "0.72.0")
set(UNCRUSTIFY_SHA256_0.78.1
    "ecaf4c0adca14c36dfffa30bc28e69865115ecd602c90eb16a8cddccb41caad2")
set(UNCRUSTIFY_SHA256_0.72.0
    "d6fff70bc7823fac4c77013055333b79a4839909094e8eee8a14ee8f1777374e")

# A wheel binary runs on machines that know nothing about the build image, so the C++ runtime
# travels with it. glibc stays dynamic: manylinux2014 gives it a 2.17 floor, which is older
# than any supported Ubuntu, and macOS has no static libc at all.
# -s drops the symbol table, which a consumer has no use for and which is a quarter of the
# size of the binary.
if(UNIX AND NOT APPLE)
  set(UNCRUSTIFY_LINK_FLAGS "-static-libstdc++ -static-libgcc -s")
else()
  set(UNCRUSTIFY_LINK_FLAGS "")
endif()

# Python is only a build-time dependency of uncrustify, which runs it to generate sources and
# documentation. scikit-build-core hands us the interpreter it is building for.
if(DEFINED Python3_EXECUTABLE)
  set(UNCRUSTIFY_PYTHON "${Python3_EXECUTABLE}")
elseif(DEFINED Python_EXECUTABLE)
  set(UNCRUSTIFY_PYTHON "${Python_EXECUTABLE}")
else()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  set(UNCRUSTIFY_PYTHON "${Python3_EXECUTABLE}")
endif()

foreach(version IN LISTS UNCRUSTIFY_VERSIONS)
  set(target "uncrustify_${version}")
  externalproject_add(${target}
    URL "https://github.com/uncrustify/uncrustify/archive/refs/tags/uncrustify-${version}.tar.gz"
    URL_HASH "SHA256=${UNCRUSTIFY_SHA256_${version}}"
    DOWNLOAD_NO_PROGRESS TRUE
    DOWNLOAD_EXTRACT_TIMESTAMP FALSE
    CMAKE_ARGS
      -DCMAKE_BUILD_TYPE=Release
      -DCMAKE_EXE_LINKER_FLAGS=${UNCRUSTIFY_LINK_FLAGS}
      # ExternalProject passes the generator down but not the tool behind it, and the build
      # backend's ninja lives in a temporary environment that is gone by the next build.
      -DCMAKE_MAKE_PROGRAM=${CMAKE_MAKE_PROGRAM}
      -DPython3_EXECUTABLE=${UNCRUSTIFY_PYTHON}
      # 0.72.0 still uses FindPythonInterp, which reads the old spelling.
      -DPYTHON_EXECUTABLE=${UNCRUSTIFY_PYTHON}
      -DCMAKE_OSX_ARCHITECTURES=${CMAKE_OSX_ARCHITECTURES}
      -DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}
      -DCMAKE_OSX_SYSROOT=${CMAKE_OSX_SYSROOT}
      # uncrustify's own test suite runs the binary, which a cross build cannot do.
      -DBUILD_TESTING=OFF
    BUILD_BYPRODUCTS "<BINARY_DIR>/uncrustify"
    INSTALL_COMMAND ""
    USES_TERMINAL_DOWNLOAD TRUE
    USES_TERMINAL_BUILD TRUE
  )
  externalproject_get_property(${target} BINARY_DIR)
  # PROGRAMS rather than FILES so the executable bit survives into the wheel.
  install(PROGRAMS "${BINARY_DIR}/uncrustify"
          DESTINATION "ros_uncrustify_bin/bin"
          RENAME "uncrustify-${version}")
endforeach()
