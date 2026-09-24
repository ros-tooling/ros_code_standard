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
flake8 with the ament_flake8 plugin set and configuration.

The configuration is passed by absolute path. flake8 treats --config as
authoritative, so a setup.cfg, tox.ini, or .flake8 in the repository being
checked is not read and cannot weaken the ROS 2 style.
"""

import argparse
import importlib.resources

from ros_code_standard.checker import check_group, CheckerGroup, Result

CONFIG = importlib.resources.files(__package__) / 'ament_flake8.ini'


@check_group
class Flake8Group(CheckerGroup):

    name = 'flake8'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the optional line length override from ament_flake8."""
        super().register_args(subparser)
        subparser.add_argument(
            '--linelength',
            metavar='N',
            type=int,
            help='Maximum line length, overriding the ament_flake8 configuration.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run flake8 over the staged Python files."""
        flags = ['--config', str(CONFIG)]
        if args.linelength is not None:
            flags.append(f'--max-line-length={args.linelength}')
        return [self._check('flake8', flags, args.files)]
