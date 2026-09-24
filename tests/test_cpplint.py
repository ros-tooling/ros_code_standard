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

import os
from pathlib import Path

import cpplint

from ros_code_standard.checkers.cpplint import (
    custom_get_header_guard_cpp_variable,
    get_file_groups,
)
from ros_code_standard.runner import main

CPP_PKG = Path(__file__).parent.parent / 'test_files' / 'cpp_pkg'
HEADER = str(CPP_PKG / 'include' / 'cpp_pkg' / 'greeter.hpp')
SOURCE = str(CPP_PKG / 'src' / 'greeter.cpp')

COPYRIGHT = '// Copyright 2026 Polymath Robotics, Inc.\n'


def _make_repo(tmp_path: Path) -> Path:
    """Create a directory that looks like a repository root to cpplint."""
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    return repo


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(COPYRIGHT + content)
    return str(path)


def _header(guard: str) -> str:
    return (
        '\n'
        f'#ifndef {guard}\n'
        f'#define {guard}\n'
        '\n'
        'int foo();\n'
        '\n'
        f'#endif  // {guard}\n'
    )


# --- the checked-in fixture package ---


def test_fixture_package_passes():
    assert main(['cpplint', HEADER, SOURCE]) == 0


def test_non_cpp_files_are_ignored():
    assert get_file_groups(['README.md', 'setup.py']) == {}


# --- header guard convention ---


def test_double_underscore_header_guard_passes(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    assert main(['cpplint', path]) == 0


def test_single_underscore_header_guard_fails(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG_FOO_HPP_'))
    assert main(['cpplint', path]) == 1


def test_header_guard_strips_the_root(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    monkeypatch.setattr(cpplint, '_root', str(repo / 'include'))
    assert custom_get_header_guard_cpp_variable(path) == 'PKG__FOO_HPP_'


def test_header_guard_keeps_the_repository_path_without_a_root(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    monkeypatch.setattr(cpplint, '_root', None)
    assert custom_get_header_guard_cpp_variable(path) == 'INCLUDE__PKG__FOO_HPP_'


# --- root grouping ---


def test_include_and_src_are_separate_groups(tmp_path):
    repo = _make_repo(tmp_path)
    header = _write(repo / 'include' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    source = _write(repo / 'src' / 'foo.cpp', '\nint foo() {return 0;}\n')
    assert get_file_groups([header, source]) == {
        'include': [header],
        'src': [source],
    }


def test_two_packages_share_no_group(tmp_path):
    repo = _make_repo(tmp_path)
    one = _write(repo / 'one' / 'include' / 'one' / 'foo.hpp', _header('ONE__FOO_HPP_'))
    two = _write(repo / 'two' / 'include' / 'two' / 'foo.hpp', _header('TWO__FOO_HPP_'))
    assert get_file_groups([one, two]) == {
        os.path.join('one', 'include'): [one],
        os.path.join('two', 'include'): [two],
    }
    assert main(['cpplint', one, two]) == 0


def test_longest_root_wins(tmp_path):
    repo = _make_repo(tmp_path)
    nested = repo / 'src' / 'vendor' / 'include' / 'pkg' / 'foo.hpp'
    path = _write(nested, _header('PKG__FOO_HPP_'))
    assert list(get_file_groups([path])) == [os.path.join('src', 'vendor', 'include')]
    assert main(['cpplint', path]) == 0


def test_file_without_a_root_subfolder_keeps_its_repository_path(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'inc' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    assert list(get_file_groups([path])) == ['']
    assert main(['cpplint', path]) == 1


# --- optional arguments ---


def test_root_argument_overrides_the_computed_root(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'inc' / 'pkg' / 'foo.hpp', _header('PKG__FOO_HPP_'))
    assert main(['cpplint', '--root', str(repo / 'inc'), path]) == 0


def test_line_length_defaults_to_100(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'src' / 'foo.cpp', '\nint foo() {return %s;}\n' % ('0' * 100))
    assert main(['cpplint', path]) == 1


def test_line_length_argument_raises_the_limit(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'src' / 'foo.cpp', '\nint foo() {return %s;}\n' % ('0' * 100))
    assert main(['cpplint', '--linelength', '200', path]) == 0


def test_filters_argument_is_appended_to_the_defaults(tmp_path):
    repo = _make_repo(tmp_path)
    path = _write(repo / 'src' / 'foo.cpp', '\nint foo() {return %s;}\n' % ('0' * 100))
    assert main(['cpplint', '--filters=-whitespace/line_length', path]) == 0
