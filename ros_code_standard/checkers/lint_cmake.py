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

"""
CMake style checking, the ament_lint_cmake check.

`ament_lint_cmake` vendors cmakelint and drives it in process so that it can
override two things.
This checker keeps both overrides and diverges on a third:

- `cmakelint.IsValidFile` rejects anything that is not `CMakeLists.txt` or
  `*.cmake`, and quietly skips the file instead of failing.
  ament replaces that function so `*.cmake.in` templates are linted too.
  There is no command line option for it, so the checker runs cmakelint in a
  child interpreter with the same one line override rather than through its
  console script.
- the line length is 140, ament's default, not cmakelint's own 80.
- cmakelint and ament both read `~/.cmakelintrc` (and `./.cmakelintrc`, and
  `$XDG_CONFIG_HOME/cmakelintrc`) when no `--config` is given, which would make
  the result depend on the developer's machine.
  The checker passes `--config=None`, the spelling cmakelint understands as
  "read no configuration file", so the standard is the standard everywhere.
"""

import argparse
import sys

from ros_code_standard.checker import check_group, CheckerGroup, Result, run

# ament_lint_cmake's default, and the ROS 2 CMake line length.
LINE_LENGTH = 140

# Run cmakelint's own main() with IsValidFile widened so .cmake.in is linted.
BOOTSTRAP = (
    'import sys; import cmakelint.main as cmakelint; '
    'cmakelint.IsValidFile = lambda filename: True; '
    'sys.exit(cmakelint.main())'
)


@check_group
class LintCmakeGroup(CheckerGroup):

    name = 'lint_cmake'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        super().register_args(subparser)
        subparser.add_argument(
            '--filters',
            default='',
            metavar='FILTERS',
            help=(
                'Comma separated cmakelint category filters, each prefixed with + or -, '
                'for example "-readability/mixedcase,-convention/filename". '
                'Same meaning as the FILTERS argument of ament_lint_cmake.'
            ),
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        cmd = [
            sys.executable,
            '-I',
            '-c',
            BOOTSTRAP,
            '--config=None',
            f'--linelength={LINE_LENGTH}',
        ]
        if args.filters:
            cmd.append(f'--filter={args.filters}')
        return [run('lint_cmake', cmd, args.files)]
