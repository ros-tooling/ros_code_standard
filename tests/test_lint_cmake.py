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

"""Tests for the lint_cmake checker: the .cmake.in override, line length 140, hermeticity."""

import argparse
from pathlib import Path

from ros_code_standard.checkers.lint_cmake import LINE_LENGTH, LintCmakeGroup
from ros_code_standard.runner import main

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_FILES = REPO_ROOT / 'test_files'

CMAKELISTS = TEST_FILES / 'cpp_pkg' / 'CMakeLists.txt'
CMAKE_IN = TEST_FILES / 'cmake' / 'example.cmake.in'

# Mixed upper and lower case commands, a readability/mixedcase error.
MIXED_CASE = 'IF(TRUE)\n  message(STATUS "hi")\nendif()\n'


def _run(files, filters=''):
    args = argparse.Namespace(files=[str(f) for f in files], filters=filters)
    return LintCmakeGroup().run(args)[0]


# --- the repository fixtures ---


def test_cmakelists_fixture_passes():
    assert main(['lint_cmake', str(CMAKELISTS)]) == 0


def test_cmake_in_fixture_passes():
    assert main(['lint_cmake', str(CMAKE_IN)]) == 0


def test_both_fixtures_pass_together():
    assert main(['lint_cmake', str(CMAKELISTS), str(CMAKE_IN)]) == 0


# --- failures ---


def test_bad_cmakelists_fails(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    result = _run([path])
    assert not result.passed
    assert 'readability/mixedcase' in result.output


def test_bad_cmake_file_fails(tmp_path):
    path = tmp_path / 'helpers.cmake'
    path.write_text(MIXED_CASE)
    assert main(['lint_cmake', str(path)]) == 1


# --- ament's IsValidFile override: .cmake.in is linted, not skipped ---


def test_bad_cmake_in_file_fails(tmp_path):
    """Upstream cmakelint prints 'Ignoring file' and passes here; ament and this hook do not."""
    path = tmp_path / 'config.cmake.in'
    path.write_text(MIXED_CASE)
    result = _run([path])
    assert not result.passed
    assert 'readability/mixedcase' in result.output
    assert 'Ignoring file' not in result.output


# --- line length is ament's 140, not cmakelint's 80 ---


def test_line_length_is_aments_default():
    assert LINE_LENGTH == 140


def test_line_of_120_characters_passes(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('# ' + 'x' * 118 + '\n')
    assert _run([path]).passed


def test_line_of_150_characters_fails(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('# ' + 'x' * 148 + '\n')
    result = _run([path])
    assert not result.passed
    assert 'linelength' in result.output


# --- filters ---


def test_filters_suppress_a_category(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    assert _run([path], filters='-readability/mixedcase').passed


def test_filters_default_to_nothing_suppressed(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    assert not _run([path], filters='').passed


# --- hermeticity: no .cmakelintrc is read ---


def test_cmakelintrc_in_the_working_directory_is_ignored(tmp_path, monkeypatch):
    """A cmakelint would read ./.cmakelintrc by default; --config=None stops it."""
    (tmp_path / '.cmakelintrc').write_text('filter=-readability/mixedcase\n')
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    monkeypatch.chdir(tmp_path)
    assert not _run([path]).passed


def test_cmakelintrc_in_the_home_directory_is_ignored(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    (home / '.cmakelintrc').write_text('filter=-readability/mixedcase\n')
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    monkeypatch.setenv('HOME', str(home))
    assert not _run([path]).passed


# --- no files ---


def test_no_files_is_a_skip():
    assert main(['lint_cmake']) == 0


def test_no_files_reports_as_skipped():
    result = _run([])
    assert result.skipped
    assert result.passed
