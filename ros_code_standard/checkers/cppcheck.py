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
cppcheck static analysis with the ament_cppcheck flag set.

ament_cppcheck refuses to run on cppcheck 1.88 and every 2.x release because they are
too slow over a whole package. A pre-commit hook only sees the staged files, so this
checker drops that version gate and always runs.
"""

import argparse
import os

from ros_code_standard.checker import check_group, CheckerGroup, Result

#: The ament_cppcheck flag set, minus the XML output it parses for its xUnit report.
AMENT_FLAGS = (
    '-f',
    '--inline-suppr',
    '-q',
    '-rp',
    '--suppress=internalAstError',
    '--suppress=unknownMacro',
)

#: One line per finding, in place of the XML report ament_cppcheck parses.
TEMPLATE = '{file}:{line}: ({severity}: {id}) {message}'


def split_list(value: str | None) -> list[str]:
    """Split one comma separated option value into its entries."""
    return [entry for entry in (value or '').split(',') if entry]


@check_group
class CppcheckGroup(CheckerGroup):

    name = 'cppcheck'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the options that mirror the ament_cppcheck CMake parameters."""
        super().register_args(subparser)
        subparser.add_argument(
            '--language', choices=['c', 'c++'],
            help='Force cppcheck to treat every file as this language.')
        subparser.add_argument(
            '--libraries', metavar='NAMES',
            help='Comma separated library configurations to load in addition to the '
                 'standard C and C++ ones.')
        subparser.add_argument(
            '--include-dirs', metavar='DIRS',
            help='Comma separated include directories for the files being checked.')

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run cppcheck over the staged C and C++ files."""
        return [self._check('cppcheck', self._cppcheck_args(args), args.files)]

    @staticmethod
    def _cppcheck_args(args: argparse.Namespace) -> list[str]:
        """Build the cppcheck command line without the file names."""
        cppcheck_args = list(AMENT_FLAGS)
        # ament parses XML instead; a template plus an exit code keeps the hook simple.
        cppcheck_args += ['--template=%s' % TEMPLATE, '--error-exitcode=1']
        if args.language:
            cppcheck_args.append('--language=%s' % args.language)
        for library in split_list(args.libraries):
            cppcheck_args.append('--library=%s' % library)
        for include_dir in split_list(args.include_dirs):
            cppcheck_args += ['-I', include_dir]
        jobs = os.cpu_count()
        if jobs:
            cppcheck_args += ['-j', str(jobs)]
        return cppcheck_args
