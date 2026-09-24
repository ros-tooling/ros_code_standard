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
mypy with the ament_mypy configuration.

Two deliberate differences from ament_mypy:

--explicit-package-bases is always passed. ament walks one package directory at
a time, while pre-commit hands over every staged file in the repository. A ROS 2
workspace has a setup.py in each package, and without explicit package bases
mypy aborts with "Duplicate module named setup" as soon as two of them are
staged together. Explicit package bases derive module names from the repository
root instead, so the collision cannot happen.

--show-error-context is not passed. ament prints the enclosing function of each
finding for its xUnit report; pre-commit only needs the diagnostics.
"""

import argparse
import importlib.resources
import os

from ros_code_standard.checker import check_group, CheckerGroup, Result

CONFIG_DIR = importlib.resources.files(__package__)


@check_group
class MypyGroup(CheckerGroup):

    name = 'mypy'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the switch to the ament strict profile."""
        super().register_args(subparser)
        subparser.add_argument(
            '--strict',
            action='store_true',
            help='Use ament_mypy_strict.toml instead of ament_mypy.ini.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run mypy over the staged Python files."""
        config = CONFIG_DIR / ('ament_mypy_strict.toml' if args.strict else 'ament_mypy.ini')
        flags = [
            '--config-file',
            str(config),
            # os.devnull is how ament disables the cache, and it keeps mypy from
            # writing a .mypy_cache into the repository being checked.
            '--cache-dir',
            os.devnull,
            '--no-incremental',
            '--no-error-summary',
            '--show-column-numbers',
            '--explicit-package-bases',
        ]
        return [self._check('mypy', flags, args.files)]
