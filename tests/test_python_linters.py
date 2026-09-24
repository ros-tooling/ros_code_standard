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
Tests for the five Python linter hooks.

Passing cases use the fixtures under test_files/python. Failing cases are
written into tmp_path, so nothing the repository's own hooks lint has a
deliberate violation in it.
"""

from pathlib import Path
import subprocess

import pytest

from ros_code_standard import runner
from ros_code_standard.checker import _GROUPS, tool

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = PROJECT_ROOT / 'test_files' / 'python'
FIXTURES = [str(path) for path in sorted(FIXTURE_DIR.glob('*.py'))]

GROUPS = ('flake8', 'pep257', 'pycodestyle', 'pyflakes', 'mypy')

# Every plugin ament_flake8 depends on. flake8 --version wraps long names across
# lines at a hyphen, so the output is compared with all whitespace removed.
PLUGINS = (
    'flake8-blind-except',
    'flake8-builtins',
    'flake8-class-newline',
    'flake8-comprehensions',
    'flake8-deprecated',
    'flake8-quotes',
    'flake8_import_order',
)

# A multi-line docstring whose summary sits on the opening quote line. D213 is
# left active by the ament ignore list, so pep257 rejects this.
D213_SOURCE = (
    'def report() -> int:\n'
    '    """Return one.\n'
    '\n'
    '    More detail on the next line.\n'
    '    """\n'
    '    return 1\n'
)


def write(path: Path, content: str) -> str:
    """Write content to path and return the path as a string."""
    path.write_text(content, encoding='utf-8')
    return str(path)


def flake8_version_text() -> str:
    """Return flake8 --version output with all whitespace removed."""
    proc = subprocess.run([tool('flake8'), '--version'], capture_output=True, text=True)
    return ''.join(proc.stdout.split())


def test_all_python_groups_are_registered():
    registered = {group.name for group in _GROUPS}
    assert set(GROUPS) <= registered


@pytest.mark.parametrize('group', GROUPS)
def test_fixtures_pass(group):
    assert runner.main([group] + FIXTURES) == 0


@pytest.mark.parametrize('group', GROUPS)
def test_no_files_is_a_skip(group):
    assert runner.main([group]) == 0


# --- flake8 ---


def test_flake8_loads_every_ament_plugin():
    version = flake8_version_text()
    assert [plugin for plugin in PLUGINS if plugin not in version] == []


def test_flake8_rejects_double_quotes(tmp_path):
    source = write(tmp_path / 'quotes.py', 'MESSAGE = "double"\n')
    assert runner.main(['flake8', source]) == 1


def test_flake8_rejects_unsorted_imports(tmp_path):
    source = write(tmp_path / 'imports.py', 'import sys\nimport os\n\nprint(os, sys)\n')
    assert runner.main(['flake8', source]) == 1


def test_flake8_config_beats_repository_setup_cfg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / 'setup.cfg', '[flake8]\nextend-ignore = Q000,E501\n')
    write(tmp_path / 'tox.ini', '[flake8]\nextend-ignore = Q000,E501\n')
    source = write(tmp_path / 'quotes.py', 'MESSAGE = "double"\n')
    assert runner.main(['flake8', source]) == 1


def test_flake8_linelength_overrides_the_config(tmp_path):
    source = write(tmp_path / 'wide.py', "VALUE = 'x' * 40\n")
    assert runner.main(['flake8', source]) == 0
    assert runner.main(['flake8', '--linelength', '10', source]) == 1


# --- pep257 ---


def test_pep257_rejects_a_summary_on_the_opening_quote_line(tmp_path):
    source = write(tmp_path / 'docs.py', D213_SOURCE)
    assert runner.main(['pep257', source]) == 1


def test_pep257_checks_test_prefixed_files(tmp_path):
    source = write(tmp_path / 'test_docs.py', D213_SOURCE)
    assert runner.main(['pep257', source]) == 1


def test_pep257_allows_missing_docstrings(tmp_path):
    source = write(tmp_path / 'bare.py', 'def report():\n    return 1\n')
    assert runner.main(['pep257', source]) == 0


def test_pep257_add_ignore_extends_the_ament_list(tmp_path):
    source = write(tmp_path / 'docs.py', D213_SOURCE)
    assert runner.main(['pep257', '--add-ignore', 'D213', source]) == 0


def test_pep257_ignore_replaces_the_ament_list(tmp_path):
    source = write(tmp_path / 'bare.py', 'def report():\n    return 1\n')
    assert runner.main(['pep257', '--ignore', 'D213', source]) == 1


def test_pep257_select_and_ignore_are_mutually_exclusive(tmp_path):
    source = write(tmp_path / 'docs.py', D213_SOURCE)
    with pytest.raises(SystemExit):
        runner.main(['pep257', '--ignore', 'D213', '--select', 'D205', source])


# --- pycodestyle ---


@pytest.mark.parametrize(
    'name,source',
    [
        # Each of these codes is in pycodestyle's DEFAULT_IGNORE, and the
        # ament configuration clears that list.
        ('w503.py', 'A = 1\nB = 2\nC = (A\n     + B)\n'),
        ('w504.py', 'A = 1\nB = 2\nC = (A +\n     B)\n'),
        ('e226.py', 'A = 2\nB = A*3\n'),
        ('e704.py', 'def report() -> int: return 1\n'),
    ],
)
def test_pycodestyle_reports_the_default_ignore_list(tmp_path, name, source):
    assert runner.main(['pycodestyle', write(tmp_path / name, source)]) == 1


def test_pycodestyle_config_beats_repository_setup_cfg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path / 'setup.cfg', '[pycodestyle]\nignore = W503,W504,E226,E704\n')
    source = write(tmp_path / 'e226.py', 'A = 2\nB = A*3\n')
    assert runner.main(['pycodestyle', source]) == 1


def test_pycodestyle_linelength_overrides_the_config(tmp_path):
    source = write(tmp_path / 'wide.py', "VALUE = 'x' * 40\n")
    assert runner.main(['pycodestyle', source]) == 0
    assert runner.main(['pycodestyle', '--linelength', '10', source]) == 1


# --- pyflakes ---


def test_pyflakes_rejects_an_unused_import(tmp_path):
    source = write(tmp_path / 'unused.py', 'import os\n')
    assert runner.main(['pyflakes', source]) == 1


def test_pyflakes_rejects_an_undefined_name(tmp_path):
    source = write(tmp_path / 'undefined.py', 'VALUE = missing_name\n')
    assert runner.main(['pyflakes', source]) == 1


# --- mypy ---


def test_mypy_rejects_an_incompatible_return(tmp_path):
    source = write(tmp_path / 'typed.py', "def report() -> int:\n    return 'one'\n")
    assert runner.main(['mypy', source]) == 1


def test_mypy_allows_an_unannotated_function_by_default(tmp_path):
    source = write(tmp_path / 'bare.py', 'def report():\n    return 1\n')
    assert runner.main(['mypy', source]) == 0


def test_mypy_strict_rejects_an_unannotated_function(tmp_path):
    source = write(tmp_path / 'bare.py', 'def report():\n    return 1\n')
    assert runner.main(['mypy', '--strict', source]) == 1


def test_mypy_leaves_no_cache_in_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = write(tmp_path / 'typed.py', 'def report() -> int:\n    return 1\n')
    assert runner.main(['mypy', source]) == 0
    assert list(tmp_path.glob('.mypy_cache')) == []


def test_mypy_tolerates_duplicate_module_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_py = 'from setuptools import setup\n\nsetup()\n'
    sources = []
    for package in ('pkg_a', 'pkg_b'):
        directory = tmp_path / package
        directory.mkdir()
        sources.append(write(directory / 'setup.py', setup_py))
    assert runner.main(['mypy'] + sources) == 0
