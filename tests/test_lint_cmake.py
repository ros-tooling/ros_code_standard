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

"""Tests for the lint_cmake checker, a thin wrapper over the ament_lint_cmake console script."""

import argparse
from pathlib import Path

from ros_code_standard.checkers.lint_cmake import LintCmakeGroup
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


def test_line_over_140_characters_fails(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('# ' + 'x' * 148 + '\n')
    result = _run([path])
    assert not result.passed
    assert 'linelength' in result.output


def test_line_of_120_characters_passes(tmp_path):
    """Upstream cmakelint defaults to 80; ament_lint_cmake defaults the line length to 140."""
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('# ' + 'x' * 118 + '\n')
    assert _run([path]).passed


# --- ament's IsValidFile widening: .cmake.in is linted, not silently skipped ---


def test_bad_cmake_in_file_fails(tmp_path):
    """Upstream cmakelint prints 'Ignoring file' and exits 0 here; the ament fork does not."""
    path = tmp_path / 'config.cmake.in'
    path.write_text(MIXED_CASE)
    result = _run([path])
    assert not result.passed
    assert 'readability/mixedcase' in result.output
    assert 'Ignoring file' not in result.output


# --- fork behaviors that upstream cmakelint 1.4.3 does not have ---


def test_over_long_line_holding_only_a_string_is_allowed(tmp_path):
    """
    A regression test for one of the ament fork's own rules.

    The fork exempts an over-long line from the line length check when the line
    holds nothing but a single string, on the grounds that a string cannot be
    split. Upstream cmakelint 1.4.3 reports linelength here, so this passing is
    proof that the hook is running ament's fork and not the PyPI release.
    """
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('set(LONG_STRING\n  "' + 'x' * 150 + '")\n')
    assert _run([path]).passed


def test_over_long_message_string_is_still_reported(tmp_path):
    """The same fork rule makes an exception for message(), whose strings can be split."""
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('message(STATUS\n  "' + 'x' * 150 + '")\n')
    result = _run([path])
    assert not result.passed
    assert 'linelength' in result.output


def test_closing_parenthesis_at_the_opening_indentation_is_allowed(tmp_path):
    """
    The fork allows a closing parenthesis at the indentation of the opening line.

    Upstream cmakelint 1.4.3 has since grown its own fix for this, so it is not
    a divergence any more, but it is still the ROS 2 house style and has to pass.
    """
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('if(TRUE)\n  install(TARGETS foo\n    DESTINATION lib\n  )\nendif()\n')
    assert _run([path]).passed


# --- filters ---


def test_filters_reach_the_command_line(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    result = _run([path], filters='-readability/mixedcase')
    assert '--filters=-readability/mixedcase' in result.cmd


def test_filters_suppress_a_category(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    assert _run([path], filters='-readability/mixedcase').passed


def test_no_filters_argument_is_passed_when_the_option_is_unused(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    result = _run([path])
    assert not any(arg.startswith('--filters') for arg in result.cmd)


def test_filters_default_to_nothing_suppressed(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text(MIXED_CASE)
    assert not _run([path], filters='').passed


def test_a_leading_dash_filters_value_needs_the_equals_form():
    """A bare -category looks like an option to argparse, so the value has to be attached."""
    argv = ['lint_cmake', '--filters=-readability/mixedcase']
    assert main(argv) == 0


# --- no files ---


def test_no_files_is_a_skip():
    """ament_lint_cmake would default to crawling '.', so an empty list must not reach it."""
    assert main(['lint_cmake']) == 0


def test_no_files_reports_as_skipped_without_running_the_tool():
    result = _run([])
    assert result.skipped
    assert result.passed
    assert result.cmd is None
