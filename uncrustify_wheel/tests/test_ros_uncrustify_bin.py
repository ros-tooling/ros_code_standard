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
Tests for the ros_uncrustify_bin wheel.

They exercise an installed wheel, not a source tree, so a run from the ros_code_standard
repository, where the wheel is not a dependency, skips them.
"""

import os
import subprocess

import pytest

ros_uncrustify_bin = pytest.importorskip(
    'ros_uncrustify_bin',
    reason='install a ros-uncrustify-bin wheel to run these tests',
)


def report_version(version: str) -> str:
    """Return the first line that `uncrustify --version` prints for a bundled binary."""
    binary = ros_uncrustify_bin.binary(version)
    assert binary.is_file(), binary
    assert os.access(binary, os.X_OK), f'{binary} is not executable'
    proc = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def test_versions() -> None:
    """The advertised versions and the default are the ones the hook selects between."""
    assert ros_uncrustify_bin.VERSIONS == ('0.78.1', '0.72.0')
    assert ros_uncrustify_bin.DEFAULT_VERSION == '0.78.1'
    assert ros_uncrustify_bin.DEFAULT_VERSION in ros_uncrustify_bin.VERSIONS


def test_default_binary_is_the_default_version() -> None:
    """binary() with no argument is binary(DEFAULT_VERSION)."""
    assert ros_uncrustify_bin.binary() == ros_uncrustify_bin.binary('0.78.1')


@pytest.mark.parametrize('version', ros_uncrustify_bin.VERSIONS)
def test_binary_reports_its_version(version: str) -> None:
    """Each bundled binary runs and prints the version it was built from."""
    # uncrustify appends a build flavor, as in 'Uncrustify-0.78.1_f'.
    assert report_version(version).startswith(f'Uncrustify-{version}')


def test_unknown_version() -> None:
    """A version this distribution does not build is a ValueError, not a missing file."""
    with pytest.raises(ValueError, match='9.9.9'):
        ros_uncrustify_bin.binary('9.9.9')
