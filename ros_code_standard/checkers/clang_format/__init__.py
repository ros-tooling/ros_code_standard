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
clang-format with the ament_clang_format style.

ament_clang_format only prints a diff unless it is asked to reformat. A formatter in
pre-commit is more useful the other way around, so this checker rewrites the files and
fails, which leaves the author to re-stage.
"""

import argparse
import importlib.resources

from ros_code_standard.checker import check_group, CheckerGroup, Result, run, tool

#: The ament .clang-format, shipped as package data beside this module.
CONFIG = importlib.resources.files(__package__) / 'clang-format'

RESTAGE_MESSAGE = '(files have been reformatted, please re-stage and recommit)'


def run_clang_format(files: list[str]) -> Result:
    """Dry-run clang-format, then reformat in place and fail if anything would change."""
    if not files:
        return Result(name='clang-format', passed=True, skipped=True)
    style = '--style=file:%s' % CONFIG
    check = run('clang-format', [tool('clang-format'), '--dry-run', '--Werror', style], files)
    if check.passed:
        return check
    run('clang-format', [tool('clang-format'), '-i', style], files)
    output = '\n'.join(part for part in (check.output, RESTAGE_MESSAGE) if part)
    return Result(name='clang-format', passed=False, output=output, cmd=check.cmd)


@check_group
class ClangFormatGroup(CheckerGroup):

    name = 'clang_format'

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Reformat the staged C and C++ files that do not match the ament style."""
        return [run_clang_format(args.files)]
