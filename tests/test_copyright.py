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

"""Tests for the copyright checker: header checking, --add-missing, and ament's crawler rules."""

import argparse
from pathlib import Path
import shutil

from ros_code_standard.checkers.copyright import CopyrightGroup, RESTAGE_MESSAGE, select_files
from ros_code_standard.runner import main

REPO_ROOT = Path(__file__).resolve().parent.parent

HEADERLESS_PY = 'x = 1\n'

GOOD_HEADER_PY = """\
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

x = 1
"""


def _run(files, add_missing=None, verbose=False):
    args = argparse.Namespace(
        files=[str(f) for f in files], add_missing=add_missing, verbose=verbose
    )
    return CopyrightGroup().run(args)


def _fake_repo_root(tmp_path):
    """Make tmp_path look like a repository root to ament's crawler."""
    (tmp_path / '.git').mkdir()
    return tmp_path


# --- checking ---


def test_this_repository_passes_on_its_own_sources(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    assert main(['copyright', 'ros_code_standard/checker.py']) == 0


def test_cmakelists_fixture_passes(monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    assert main(['copyright', 'test_files/cpp_pkg/CMakeLists.txt']) == 0


def test_headerless_file_fails(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    results = _run([path])
    assert not results[0].passed
    assert 'could not find copyright notice' in results[0].output


def test_file_with_the_apache_header_passes(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(tmp_path)
    assert _run([path])[0].passed


def test_verbose_reports_every_file(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(tmp_path)
    result = _run([path], verbose=True)[0]
    assert result.passed
    assert 'license=apache2' in result.output


def test_no_files_is_a_skip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = _run([])
    assert len(results) == 1
    assert results[0].skipped


# --- repository level LICENSE and CONTRIBUTING.md ---


def test_repository_license_and_contributing_are_appended(tmp_path, monkeypatch):
    (tmp_path / 'LICENSE').write_text('anything\n')
    (tmp_path / 'CONTRIBUTING.md').write_text('anything\n')
    monkeypatch.chdir(tmp_path)
    assert select_files(['a.py']) == ['a.py', 'LICENSE', 'CONTRIBUTING.md']


def test_absent_license_and_contributing_are_not_appended(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert select_files(['a.py']) == ['a.py']


def test_a_staged_license_is_not_appended_twice(tmp_path, monkeypatch):
    (tmp_path / 'LICENSE').write_text('anything\n')
    monkeypatch.chdir(tmp_path)
    assert select_files(['LICENSE']) == ['LICENSE']


def test_absent_license_does_not_fail_the_hook(tmp_path, monkeypatch):
    _fake_repo_root(tmp_path)
    path = tmp_path / 'thing.py'
    path.write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(tmp_path)
    assert main(['copyright', 'thing.py']) == 0


def test_this_repositorys_license_and_contributing_pass(tmp_path, monkeypatch):
    root = _fake_repo_root(tmp_path)
    shutil.copy(REPO_ROOT / 'LICENSE', root / 'LICENSE')
    shutil.copy(REPO_ROOT / 'CONTRIBUTING.md', root / 'CONTRIBUTING.md')
    (root / 'thing.py').write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(root)
    result = _run(['thing.py'], verbose=True)[0]
    assert result.passed
    assert 'LICENSE: apache2' in result.output
    assert 'CONTRIBUTING.md: apache2' in result.output


def test_an_unrecognized_license_file_fails(tmp_path, monkeypatch):
    root = _fake_repo_root(tmp_path)
    (root / 'LICENSE').write_text('All rights reserved, do what you want.\n')
    (root / 'thing.py').write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(root)
    assert main(['copyright', 'thing.py']) == 1


# --- setup.py beside package.xml ---


def test_package_level_setup_py_is_skipped(tmp_path, monkeypatch):
    pkg = tmp_path / 'pkg'
    pkg.mkdir()
    (pkg / 'package.xml').write_text('<package format="3"/>\n')
    (pkg / 'setup.py').write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    assert select_files(['pkg/setup.py']) == []
    assert main(['copyright', 'pkg/setup.py']) == 0


def test_setup_py_without_a_package_xml_is_checked(tmp_path, monkeypatch):
    (tmp_path / 'setup.py').write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    assert select_files(['setup.py']) == ['setup.py']
    assert main(['copyright', 'setup.py']) == 1


# --- --add-missing ---


def test_add_missing_inserts_the_header(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    _run([path], add_missing=['Polymath Robotics, Inc.', 'apache2'])
    content = path.read_text()
    assert content.startswith('# Copyright ')
    assert 'Polymath Robotics, Inc.' in content
    assert 'Apache License, Version 2.0' in content
    assert content.endswith(HEADERLESS_PY)


def test_add_missing_fails_with_the_restage_message(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    results = _run([path], add_missing=['Polymath Robotics, Inc.', 'apache2'])
    add_result = results[0]
    assert add_result.name == 'copyright (add-missing)'
    assert not add_result.passed
    assert f'header inserted: {path}' in add_result.output
    assert RESTAGE_MESSAGE in add_result.output


def test_add_missing_makes_the_following_check_pass(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    results = _run([path], add_missing=['Polymath Robotics, Inc.', 'apache2'])
    assert results[1].name == 'copyright'
    assert results[1].passed


def test_add_missing_still_fails_the_hook_overall(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    argv = ['copyright', '--add-missing', 'Polymath Robotics, Inc.', 'apache2', 'thing.py']
    assert main(argv) == 1


def test_add_missing_is_quiet_when_nothing_changes(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(GOOD_HEADER_PY)
    monkeypatch.chdir(tmp_path)
    results = _run([path], add_missing=['Polymath Robotics, Inc.', 'apache2'])
    assert all(r.passed for r in results)
    assert path.read_text() == GOOD_HEADER_PY


def test_add_missing_rejects_an_unknown_license(tmp_path, monkeypatch):
    path = tmp_path / 'thing.py'
    path.write_text(HEADERLESS_PY)
    monkeypatch.chdir(tmp_path)
    results = _run([path], add_missing=['Polymath Robotics, Inc.', 'not-a-license'])
    assert not results[0].passed
    assert path.read_text() == HEADERLESS_PY
