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
ROS Code Standard pre-commit hook runner.

Invoked as: ros_code_standard <group> [options] [files ...]

Files are pre-filtered by pre-commit's native type detection before arrival.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import pkgutil

from .checker import _GROUPS, CheckerGroup

for _mod in pkgutil.iter_modules([str(Path(__file__).parent / 'checkers')]):
    importlib.import_module(f'.checkers.{_mod.name}', package=__package__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='group', required=True, metavar='GROUP')

    group_map: dict[str, CheckerGroup] = {}
    for group in _GROUPS:
        sub = subs.add_parser(group.name, help=f'Run {group.name} checks')
        group.register_args(sub)
        group_map[group.name] = group

    args = parser.parse_args(argv)
    results = group_map[args.group].run(args)

    failed = [r for r in results if not r.passed and not r.skipped]
    for result in failed:
        result.report()
    return 1 if failed else 0
