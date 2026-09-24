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


"""pyflakes, with no configuration. Mirrors ament_pyflakes."""

import argparse

from ros_code_standard.checker import check_group, CheckerGroup, Result


@check_group
class PyflakesGroup(CheckerGroup):

    name = 'pyflakes'

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run pyflakes over the staged Python files."""
        return [self._check('pyflakes', [], args.files)]
