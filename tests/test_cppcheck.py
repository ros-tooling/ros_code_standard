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

import argparse
from pathlib import Path

from ros_code_standard.checkers.cppcheck import CppcheckGroup
from ros_code_standard.runner import main

CPP_PKG = Path(__file__).parent.parent / 'test_files' / 'cpp_pkg'
HEADER = str(CPP_PKG / 'include' / 'cpp_pkg' / 'greeter.hpp')
SOURCE = str(CPP_PKG / 'src' / 'greeter.cpp')

OUT_OF_BOUNDS = """\
int main()
{
  int values[3] = {0, 1, 2};
  return values[5];
}
"""


def _args(files: list[str], **overrides) -> argparse.Namespace:
    defaults = {'files': files, 'language': None, 'libraries': None, 'include_dirs': None}
    return argparse.Namespace(**{**defaults, **overrides})


def test_fixture_package_passes():
    assert main(['cppcheck', HEADER, SOURCE]) == 0


def test_out_of_bounds_access_fails(tmp_path):
    path = tmp_path / 'bad.cpp'
    path.write_text(OUT_OF_BOUNDS)
    result = CppcheckGroup().run(_args([str(path)]))[0]
    assert not result.passed
    assert 'arrayIndexOutOfBounds' in result.output


def test_finding_is_reported_as_one_line_per_error(tmp_path):
    path = tmp_path / 'bad.cpp'
    path.write_text(OUT_OF_BOUNDS)
    result = CppcheckGroup().run(_args([str(path)]))[0]
    assert result.output.startswith('%s:4: (error: arrayIndexOutOfBounds)' % path)


def test_optional_arguments_reach_the_command_line():
    include_dirs = '%s,%s' % (CPP_PKG / 'include', CPP_PKG / 'src')
    result = CppcheckGroup().run(
        _args([SOURCE], language='c++', libraries='posix,gnu', include_dirs=include_dirs))[0]
    assert result.passed
    assert '--language=c++' in result.cmd
    assert '--library=posix' in result.cmd
    assert '--library=gnu' in result.cmd
    included = [result.cmd[i + 1] for i, arg in enumerate(result.cmd) if arg == '-I']
    assert included == [str(CPP_PKG / 'include'), str(CPP_PKG / 'src')]


def test_list_arguments_do_not_consume_the_file_names(tmp_path):
    path = tmp_path / 'bad.cpp'
    path.write_text(OUT_OF_BOUNDS)
    assert main(['cppcheck', '--libraries', 'posix', str(path)]) == 1
    include_dir = str(CPP_PKG / 'include')
    assert main(['cppcheck', '--include-dirs', include_dir, SOURCE]) == 0


def test_no_files_is_skipped():
    result = CppcheckGroup().run(_args([]))[0]
    assert result.skipped
