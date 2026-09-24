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
pydocstyle with the ament_pep257 ignore list.

The 'ament' convention is ament_pep257's name for its default ignore list. It
leaves D211 and D213 active, so a class docstring starts on the line after the
class statement and a multi-line docstring starts on the line after the opening
quotes.

Two notes on behaviour:

--match is set to every .py file, as ament does. pydocstyle's default --match
skips files whose name starts with test_, even when the file is named
explicitly on the command line.

The code selection arguments take one comma separated value rather than
ament's space separated list. A space separated list would swallow the file
names that pre-commit appends after the arguments.
"""

import argparse

from ros_code_standard.checker import check_group, CheckerGroup, Result

# ament_pep257's 'ament' convention.
AMENT_IGNORE = (
    'D100',
    'D101',
    'D102',
    'D103',
    'D104',
    'D105',
    'D106',
    'D107',
    'D203',
    'D212',
    'D404',
)

# pydocstyle 6.3's own conventions, plus ament's.
CONVENTIONS = ('ament', 'google', 'numpy', 'pep257')


@check_group
class Pep257Group(CheckerGroup):

    name = 'pep257'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the code selection arguments from ament_pep257."""
        super().register_args(subparser)
        selection = subparser.add_mutually_exclusive_group()
        selection.add_argument(
            '--ignore',
            metavar='CODES',
            help='Comma separated error codes for pydocstyle NOT to check for.',
        )
        selection.add_argument(
            '--select',
            metavar='CODES',
            help='Comma separated error codes for pydocstyle to check for.',
        )
        selection.add_argument(
            '--convention',
            choices=CONVENTIONS,
            default='ament',
            help=f'A preset list of error codes. "ament" means --ignore {",".join(AMENT_IGNORE)}.',
        )
        subparser.add_argument(
            '--add-ignore',
            metavar='CODES',
            help='Comma separated error codes to remove from the selected list.',
        )
        subparser.add_argument(
            '--add-select',
            metavar='CODES',
            help='Comma separated error codes to add to the selected list.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run pydocstyle over the staged Python files."""
        flags = ['--match', r'.*\.py', '--match-dir', r'[^\._].*']
        if args.ignore:
            flags += ['--ignore', args.ignore]
        elif args.select:
            flags += ['--select', args.select]
        elif args.convention == 'ament':
            flags += ['--ignore', ','.join(AMENT_IGNORE)]
        else:
            flags += ['--convention', args.convention]
        if args.add_ignore:
            flags += ['--add-ignore', args.add_ignore]
        if args.add_select:
            flags += ['--add-select', args.add_select]
        return [self._check('pydocstyle', flags, args.files)]
