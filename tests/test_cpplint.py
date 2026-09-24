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

from ros_code_standard.checkers.cpplint import CpplintGroup
from ros_code_standard.runner import main

CPP_PKG = Path(__file__).parent.parent / 'test_files' / 'cpp_pkg'
HEADER = str(CPP_PKG / 'include' / 'cpp_pkg' / 'greeter.hpp')
SOURCE = str(CPP_PKG / 'src' / 'greeter.cpp')

COPYRIGHT = '// Copyright 2026 Polymath Robotics, Inc.\n'


def _args(files: list[str], **overrides) -> argparse.Namespace:
    defaults = {'files': files, 'filters': None, 'linelength': None, 'root': None}
    return argparse.Namespace(**{**defaults, **overrides})


def _make_repo(tmp_path: Path) -> Path:
    """Create a directory that looks like a repository root to cpplint."""
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    return repo


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(COPYRIGHT + content)
    return str(path)


def _header(guard: str, body: str = 'int foo();\n') -> str:
    return (
        '\n'
        f'#ifndef {guard}\n'
        f'#define {guard}\n'
        '\n'
        f'{body}'
        '\n'
        f'#endif  // {guard}\n'
    )


# --- the checked-in fixture package ---


def test_fixture_package_passes():
    assert main(['cpplint', HEADER, SOURCE]) == 0


def test_no_files_is_skipped():
    # ament_cpplint would otherwise walk the current directory.
    result = CpplintGroup().run(_args([]))[0]
    assert result.skipped
    assert result.cmd is None


# --- the ROS header guard convention ---


def test_double_underscore_header_guard_passes(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    assert main(['cpplint', path]) == 0


def test_single_underscore_header_guard_fails(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG_FOO_HPP_'))
    assert main(['cpplint', path]) == 1


def test_two_packages_each_get_their_own_root(tmp_path):
    repo = _make_repo(tmp_path)
    one = _write(repo / 'one' / 'include' / 'one' / 'foo.hpp', _header('ONE__FOO_HPP_'))
    two = _write(repo / 'two' / 'include' / 'two' / 'foo.hpp', _header('TWO__FOO_HPP_'))
    assert main(['cpplint', one, two]) == 0


# --- checks cpplint 2.0 added that the ament style does not satisfy ---


def test_cpp17_header_and_compact_return_pass(tmp_path):
    repo = _make_repo(tmp_path)
    body = (
        '#include <filesystem>\n'
        '#include <memory>\n'
        '#include <mutex>\n'
        '\n'
        'class Guard\n'
        '{\n'
        'public:\n'
        '  void release()\n'
        '  {\n'
        '    if (!mutex_) {return;}\n'
        '    mutex_.reset();\n'
        '  }\n'
        '\n'
        '  std::filesystem::path path() const {return path_;}\n'
        '\n'
        'private:\n'
        '  std::shared_ptr<std::mutex> mutex_;\n'
        '  std::filesystem::path path_;\n'
        '};\n'
    )
    path = _write(repo / 'include' / 'pkg' / 'guard.hpp', _header('PKG__GUARD_HPP_', body))
    assert main(['cpplint', path]) == 0


# --- optional arguments ---


def test_filters_reaches_the_command_line():
    result = CpplintGroup().run(_args([SOURCE], filters='-build/include_order'))[0]
    assert '--filters=-build/include_order' in result.cmd
    assert result.passed


def test_filters_suppresses_a_finding(tmp_path):
    repo = _make_repo(tmp_path)
    long_line = '\nint foo() {return %s;}\n' % ('0' * 100)
    path = _write(repo / 'src' / 'foo.cpp', long_line)
    assert main(['cpplint', path]) == 1
    assert main(['cpplint', '--filters=-whitespace/line_length', path]) == 0


def test_linelength_reaches_the_command_line():
    result = CpplintGroup().run(_args([SOURCE], linelength=120))[0]
    assert result.cmd[result.cmd.index('--linelength') + 1] == '120'
    assert result.passed


def test_linelength_raises_the_limit(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'src' / 'foo.cpp', '\nint foo() {return %s;}\n' % ('0' * 100))
    assert main(['cpplint', path]) == 1
    assert main(['cpplint', '--linelength', '200', path]) == 0


def test_root_reaches_the_command_line():
    include_dir = str(CPP_PKG / 'include')
    result = CpplintGroup().run(_args([HEADER], root=include_dir))[0]
    assert result.cmd[result.cmd.index('--root') + 1] == include_dir
    assert result.passed


def test_root_overrides_the_computed_root(tmp_path):
    repo = _make_repo(tmp_path)
    # 'inc' is not one of the directory names ament_cpplint roots on, so the guard is
    # expected to carry the whole repository path until --root says otherwise.
    path = _write(repo / 'inc' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    assert main(['cpplint', path]) == 1
    assert main(['cpplint', '--root', str(repo / 'inc'), path]) == 0
