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

`ament_lint_cmake` vendors a modified fork of cmakelint, not the upstream
release, so calling PyPI cmakelint with ament's flags does not reproduce ament's
findings.
The fork differs in at least four ways: it allows a closing parenthesis to sit
at the indentation level of the opening line, it ignores an over-long line when
that line holds nothing but a single string, it parses filters differently, and
it has its own in-file pragma implementation.
It also widens `IsValidFile` so `*.cmake.in` templates are linted instead of
silently skipped, and it defaults the line length to 140.

So this checker wraps the `ament_lint_cmake` console script directly, the same
way the copyright checker wraps `ament_copyright`.
Findings match `colcon test` exactly, and the line length and the `.cmake.in`
handling come from ament rather than from anything spelled out here.

One known non-hermetic behavior is kept for that parity: ament, like upstream
cmakelint, reads `.cmakelintrc` from the working directory, from
`$XDG_CONFIG_DIR`, and from the developer's home directory when no `--config`
is given, so a developer's rc file can change the result.
Suppressing that would be a divergence from ament, so it is left alone for now
and tracked as an improvement for a later phase.
"""

import argparse

from ros_code_standard.checker import check_group, CheckerGroup, Result


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
                'passed through to ament_lint_cmake. Same meaning as the FILTERS argument '
                'of the ament_lint_cmake CMake macro. A value that starts with a dash has '
                'to be written as --filters=-category, since argparse would otherwise read '
                'it as an option.'
            ),
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        extra = [f'--filters={args.filters}'] if args.filters else []
        return [self._check('ament_lint_cmake', extra, args.files, name='lint_cmake')]
