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
Copyright notice and license header checking, the ament_copyright check.

`ament_copyright` is not a wrapper around another tool: its parser, its license
templates, and its `--add-missing` mode are the tool, so this checker calls it
directly rather than reimplementing the ROS 2 canon.

Two pieces of ament's directory crawler have to be reproduced here, because
pre-commit hands over a file list instead of a directory:

- a `setup.py` beside a `package.xml` is skipped, since ament never checks the
  generated package level `setup.py`,
- the repository level `LICENSE` and `CONTRIBUTING.md` are appended when they
  exist, since ament only looks at them when it walks a repository root.
"""

import argparse
import hashlib
import os
from pathlib import Path

from ament_copyright import CONTRIBUTING_FILENAME, LICENSE_FILENAME

from ros_code_standard.checker import check_group, CheckerGroup, Result

RESTAGE_MESSAGE = 'copyright headers were inserted, please re-stage the files and commit again'


def _digest(path: str) -> str:
    """Return a content hash for a file, or the empty string when it is unreadable."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ''


def _is_package_setup_py(path: str) -> bool:
    """Report whether the path is a package level setup.py, which ament skips."""
    return os.path.basename(path) == 'setup.py' and (Path(path).parent / 'package.xml').is_file()


def select_files(files: list[str]) -> list[str]:
    """
    Turn pre-commit's file list into the paths to hand to ament_copyright.

    Package level `setup.py` files are dropped, and the repository level
    `LICENSE` and `CONTRIBUTING.md` are appended when they exist so that their
    contents are still matched against the known license templates.
    """
    selected = [f for f in files if not _is_package_setup_py(f)]
    seen = {os.path.normpath(f) for f in selected}
    for filename in (LICENSE_FILENAME, CONTRIBUTING_FILENAME):
        if filename not in seen and Path(filename).is_file():
            selected.append(filename)
    return selected


@check_group
class CopyrightGroup(CheckerGroup):

    name = 'copyright'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        super().register_args(subparser)
        subparser.add_argument(
            '--add-missing',
            nargs=2,
            metavar=('COPYRIGHT_NAME', 'LICENSE'),
            help=(
                'Insert a copyright notice and license header into files that have none, '
                'using the given copyright holder and license name, then check. '
                'The hook fails when anything was inserted so the files get re-staged.'
            ),
        )
        subparser.add_argument(
            '--verbose',
            action='store_true',
            help='Report every file checked, not only the ones with errors',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        files = select_files(args.files)
        if not files:
            return [Result(name='copyright', passed=True, skipped=True)]

        extra = ['--verbose'] if args.verbose else []
        results = []
        if args.add_missing:
            results.append(self._add_missing(args.add_missing, extra, files))
        results.append(self._check('ament_copyright', extra, files, name='copyright'))
        return results

    def _add_missing(self, add_missing: list[str], extra: list[str], files: list[str]) -> Result:
        """Insert headers where they are missing, and fail when any file changed."""
        before = {f: _digest(f) for f in files}
        result = self._check(
            'ament_copyright',
            ['--add-missing', *add_missing, *extra],
            files,
            name='copyright (add-missing)',
        )
        if not result.passed:
            return result
        changed = sorted(f for f in files if _digest(f) != before[f])
        if not changed:
            return result
        return Result(
            name='copyright (add-missing)',
            passed=False,
            output='\n'.join([*(f'header inserted: {f}' for f in changed), RESTAGE_MESSAGE]),
        )
