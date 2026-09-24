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
pycodestyle with the ament_pycodestyle configuration.

ament_pycodestyle.ini sets ``ignore = ''``. An ini value cannot be empty in a
way configparser reports as empty, so pycodestyle parses the two quote
characters as a single bogus code. The list is therefore non-empty, which stops
pycodestyle from falling back to its DEFAULT_IGNORE, and no real code starts
with a quote, so nothing is actually ignored. The net effect, and the intent in
ament, is that E121, E123, E126, E226, E24, E704, W503, and W504 are all
reported. Verified against pycodestyle 2.15.0.

The configuration is passed by absolute path, and pycodestyle treats --config
as authoritative, so a setup.cfg or tox.ini in the repository being checked is
not read.
"""

import argparse
import importlib.resources

from ros_code_standard.checker import check_group, CheckerGroup, Result

CONFIG = importlib.resources.files(__package__) / 'ament_pycodestyle.ini'


@check_group
class PycodestyleGroup(CheckerGroup):

    name = 'pycodestyle'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the optional line length override from ament_pycodestyle."""
        super().register_args(subparser)
        subparser.add_argument(
            '--linelength',
            metavar='N',
            type=int,
            help='Maximum line length, overriding the ament_pycodestyle configuration.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run pycodestyle over the staged Python files."""
        flags = ['--config', str(CONFIG)]
        if args.linelength is not None:
            flags.append(f'--max-line-length={args.linelength}')
        return [self._check('pycodestyle', flags, args.files)]
