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
Prebuilt uncrustify binaries for the ros_code_standard hooks.

uncrustify has no PyPI package and no upstream Linux release binary, so this distribution
carries binaries built from the pinned upstream sources, one per version that a supported ROS 2
distribution pins.
The wheels are platform specific and the binaries live in ``ros_uncrustify_bin/bin``.
"""

import importlib.resources
from pathlib import Path

__version__ = '0.1.0'

#: Every uncrustify version this distribution builds, newest first.
VERSIONS: tuple[str, ...] = ('0.78.1', '0.72.0')

#: The version ROS 2 rolling and jazzy build through uncrustify_vendor.
DEFAULT_VERSION: str = '0.78.1'

_BIN_DIR = importlib.resources.files(__package__) / 'bin'


def binary(version: str = DEFAULT_VERSION) -> Path:
    """
    Return the path to the bundled uncrustify executable for a version.

    Raises ValueError for a version this distribution does not build, and FileNotFoundError
    when the installed wheel does not carry it, which means the wheel was built for another
    platform or repaired by hand.
    """
    if version not in VERSIONS:
        known = ', '.join(VERSIONS)
        raise ValueError(f"Unknown uncrustify version '{version}', expected one of: {known}")
    path = Path(str(_BIN_DIR / f'uncrustify-{version}'))
    if not path.is_file():
        raise FileNotFoundError(
            f"The installed ros-uncrustify-bin wheel has no uncrustify {version} at '{path}'"
        )
    return path
