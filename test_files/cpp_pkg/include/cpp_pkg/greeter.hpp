// Copyright 2026 Polymath Robotics, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef CPP_PKG__GREETER_HPP_
#define CPP_PKG__GREETER_HPP_

#include <string>

namespace cpp_pkg
{

/// Build greetings for a fixed name.
class Greeter
{
public:
  /// Construct a greeter for a name, falling back to "world" when it is empty.
  explicit Greeter(const std::string & name);

  /// Return a greeting for the configured name.
  std::string greet() const;

private:
  std::string name_;
};

}  // namespace cpp_pkg

#endif  // CPP_PKG__GREETER_HPP_
