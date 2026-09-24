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
Google style checking for C and C++, the ament_cpplint check.

This calls `ament_cpplint` itself rather than PyPI cpplint, because the two do not
agree. ament vendors a modified fork of cpplint 1.5.5: it adds clang-analyzer NOLINT
categories, treats `.hh` as a project header, excepts `std::literals` and
`std::placeholders` from the using-namespace rule, and tweaks the namespace comment
rules. cpplint 2.0 then added checks that ament's own style does not satisfy, so
running the PyPI release over a package that passes `colcon test` reports
`build/c++17`, `whitespace/newline` and a wider `build/include_what_you_use`.
Calling ament_cpplint keeps the findings identical to `colcon test`.

ament_cpplint brings its own filter set, line length of 100, `--root` grouping by the
nearest `include`, `src` or `test` ancestor, and the ROS header guard convention, so
there is nothing to reproduce here.
"""

import argparse

from ros_code_standard.checker import check_group, CheckerGroup, Result


@check_group
class CpplintGroup(CheckerGroup):

    name = 'cpplint'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the options that mirror the ament_cpplint CMake parameters."""
        super().register_args(subparser)
        subparser.add_argument(
            '--filters',
            metavar='FILTER,FILTER,...',
            help='Comma separated category filters to append to the ament_cpplint defaults. '
                 'Spell it --filters=-category, since a filter starts with a dash.',
        )
        subparser.add_argument(
            '--linelength',
            metavar='N',
            type=int,
            help='The maximum line length. ament_cpplint uses 100.',
        )
        subparser.add_argument(
            '--root',
            metavar='PATH',
            help='Use this cpplint --root for every file instead of the one ament_cpplint '
                 'computes from the path.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run ament_cpplint over the staged C and C++ files."""
        cpplint_args = ['--quiet']
        if args.filters:
            cpplint_args.append('--filters=%s' % args.filters)
        if args.linelength:
            cpplint_args += ['--linelength', str(args.linelength)]
        if args.root:
            cpplint_args += ['--root', args.root]
        # An empty file list has to stay a skip: ament_cpplint defaults its paths to the
        # current directory, so with no files it would walk the whole repository.
        return [self._check('ament_cpplint', cpplint_args, args.files, name='cpplint')]
