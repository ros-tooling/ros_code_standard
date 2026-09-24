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
Tests for the uncrustify checker group.

The unit tests cover the parts that decide how uncrustify is invoked: which bundled config
matches the installed version, which files go into the C group and which into the CPP group,
and what happens when the binary is not installed at all.
The tests marked `external` need a real uncrustify on PATH and skip without one.
"""

import argparse
from pathlib import Path
import shutil

import pytest

from ros_code_standard import runner
from ros_code_standard.checkers import uncrustify

_PROJECT_ROOT = Path(__file__).parent.parent
_CPP_PKG = _PROJECT_ROOT / 'test_files' / 'cpp_pkg'

needs_uncrustify = pytest.mark.skipif(
    shutil.which('uncrustify') is None, reason='uncrustify not on PATH'
)

CLEAN_CPP = """\
#include <string>

namespace demo
{

int add(int a, int b)
{
  return a + b;
}

std::string name()
{
  return "demo";
}

}  // namespace demo
"""

MESSY_CPP = """\
#include <string>
namespace demo {
int add(int a,int b){
    return a+b;
}
std::string name() { return "demo" ; }
}
"""


def _args(*files: Path, **overrides) -> argparse.Namespace:
    namespace = argparse.Namespace(files=[str(f) for f in files], linelength=None, language=None)
    for key, value in overrides.items():
        setattr(namespace, key, value)
    return namespace


# --- version string to config selection ---


@pytest.mark.parametrize(
    ('version_output', 'expected'),
    [
        ('Uncrustify-0.72.0_f', 'ament_code_style_0_72.cfg'),
        ('Uncrustify_d-0.78.1', 'ament_code_style_0_78.cfg'),
        ('Uncrustify-0.83.0', 'ament_code_style_0_78.cfg'),
        ('Uncrustify-0.78.1_f', 'ament_code_style_0_78.cfg'),
        ('Uncrustify-0.78.0', 'ament_code_style_0_72.cfg'),
        ('Uncrustify-0.69.0', 'ament_code_style_0_72.cfg'),
        # A double digit minor sorts correctly because the parse compares integers,
        # where ament_uncrustify compares the version bytes.
        ('Uncrustify-0.100.0', 'ament_code_style_0_78.cfg'),
    ],
)
def test_select_config_per_version(version_output, expected):
    config = uncrustify.select_config(version_output)
    assert config.name == expected
    assert config.is_file()


@pytest.mark.parametrize('version_output', ['', 'uncrustify', 'Uncrustify', 'clang-format 19.1.7'])
def test_select_config_rejects_an_unparseable_version(version_output):
    assert uncrustify.select_config(version_output) is None


def test_parse_version_returns_a_comparable_triple():
    assert uncrustify.parse_version('Uncrustify-0.72.0_f') == (0, 72, 0)


# --- language grouping ---


def test_group_by_language_splits_c_from_cpp():
    files = ['a.c', 'b.cc', 'c.h', 'd.hh', 'e.cpp', 'f.cxx', 'g.hpp', 'h.hxx']
    assert uncrustify.group_by_language(files) == {
        'C': ['a.c', 'b.cc', 'c.h', 'd.hh'],
        'CPP': ['e.cpp', 'f.cxx', 'g.hpp', 'h.hxx'],
    }


def test_group_by_language_drops_unknown_extensions():
    assert uncrustify.group_by_language(['a.cpp', 'b.ipp', 'c.py', 'Makefile']) == {
        'CPP': ['a.cpp'],
    }


def test_group_by_language_keeps_directories_in_the_path():
    files = ['include/pkg/greeter.hpp', 'src/greeter.cpp', 'src/legacy.c']
    assert uncrustify.group_by_language(files) == {
        'C': ['src/legacy.c'],
        'CPP': ['include/pkg/greeter.hpp', 'src/greeter.cpp'],
    }


def test_group_by_language_honors_a_forced_language():
    files = ['a.c', 'b.hpp', 'c.py']
    assert uncrustify.group_by_language(files, 'CPP') == {'CPP': ['a.c', 'b.hpp']}


def test_group_by_language_of_nothing_is_empty():
    assert uncrustify.group_by_language(['README.md']) == {}


def test_normalize_language_maps_the_ament_spelling():
    assert uncrustify.normalize_language('C++') == 'CPP'
    assert uncrustify.normalize_language('CPP') == 'CPP'
    assert uncrustify.normalize_language('C') == 'C'
    assert uncrustify.normalize_language(None) is None


# --- line length override ---


def test_config_code_width_of_both_bundled_configs():
    for name in ('ament_code_style_0_72.cfg', 'ament_code_style_0_78.cfg'):
        config = Path(str(uncrustify.CONFIG_DIR / name))
        assert uncrustify.config_code_width(config.read_text()) == 100


def test_linelength_config_is_none_when_it_matches_the_config():
    config = uncrustify.select_config('Uncrustify-0.78.1')
    assert uncrustify.linelength_config(config, 100) is None


def test_linelength_config_appends_an_override():
    config = uncrustify.select_config('Uncrustify-0.78.1')
    override = uncrustify.linelength_config(config, 120)
    try:
        assert override is not None
        text = override.read_text()
        # The override is appended, so uncrustify's last-value-wins parsing picks it up.
        assert text.endswith('\ncode_width=120')
        assert text.startswith(config.read_text())
    finally:
        override.unlink(missing_ok=True)


def test_linelength_override_is_removed_after_the_run(tmp_path, monkeypatch):
    """The temp config must not outlive the hook, even though the check itself fails."""
    source = tmp_path / 'messy.cpp'
    source.write_text(MESSY_CPP)
    seen = []

    def _record(binary, config, language, files):
        seen.append(Path(config))
        return uncrustify.Result(name='uncrustify', passed=True)

    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: '/usr/bin/uncrustify')
    monkeypatch.setattr(
        uncrustify.subprocess,
        'run',
        lambda *a, **k: argparse.Namespace(returncode=0, stdout='Uncrustify-0.78.1', stderr=''),
    )
    monkeypatch.setattr(uncrustify, 'format_group', _record)

    uncrustify.UncrustifyGroup().run(_args(source, linelength=120))
    assert len(seen) == 1
    assert not seen[0].exists()


# --- missing binary ---


def test_missing_binary_fails_with_an_install_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: None)
    monkeypatch.setattr(
        uncrustify, 'format_group', lambda *a: pytest.fail('uncrustify must not be invoked')
    )
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [(r.name, r.passed, r.skipped) for r in results] == [('uncrustify', False, False)]
    assert results[0].output == uncrustify.UNCRUSTIFY_MISSING
    assert 'apt install uncrustify' in results[0].output
    assert 'brew install uncrustify' in results[0].output
    assert 'uncrustify_vendor' in results[0].output


def test_missing_binary_makes_the_runner_exit_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: None)
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)
    assert runner.main(['uncrustify', str(source)]) == 1


def test_unparseable_version_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: '/usr/bin/uncrustify')
    monkeypatch.setattr(
        uncrustify.subprocess,
        'run',
        lambda *a, **k: argparse.Namespace(returncode=0, stdout='Frobnicate 1.2', stderr=''),
    )
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert not results[0].passed
    assert 'Invalid uncrustify version' in results[0].output


def test_no_matching_files_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: '/usr/bin/uncrustify')
    monkeypatch.setattr(
        uncrustify.subprocess,
        'run',
        lambda *a, **k: argparse.Namespace(returncode=0, stdout='Uncrustify-0.78.1', stderr=''),
    )
    unrelated = tmp_path / 'notes.md'
    unrelated.write_text('hello\n')

    results = uncrustify.UncrustifyGroup().run(_args(unrelated))
    assert [(r.passed, r.skipped) for r in results] == [(True, True)]


# --- diff rendering ---


def test_diff_lines_reports_the_change():
    raw = uncrustify.diff_lines('a.cpp', b'int a=1;\n', b'int a = 1;\n')
    diff = [line.rstrip('\n') for line in raw]
    assert diff[0] == '--- a.cpp'
    assert diff[1] == '+++ a.cpp.uncrustify'
    assert '-int a=1;' in diff
    assert '+int a = 1;' in diff


def test_diff_lines_of_identical_content_is_empty():
    assert uncrustify.diff_lines('a.cpp', b'int a = 1;\n', b'int a = 1;\n') == []


# --- end to end, needs the real binary ---


@pytest.mark.external
@needs_uncrustify
def test_clean_file_passes(tmp_path):
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)
    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [r.passed for r in results] == [True], results[0].output
    assert source.read_text() == CLEAN_CPP


@pytest.mark.external
@needs_uncrustify
def test_messy_file_is_reformatted_and_reported(tmp_path):
    source = tmp_path / 'greeter.cpp'
    source.write_text(MESSY_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [r.passed for r in results] == [False]
    output = results[0].output
    assert str(source) in output
    assert output.endswith(uncrustify.REFORMATTED)
    assert '1 file with code style divergence' in output
    # The diff of the reformatting is part of the report.
    assert '-int add(int a,int b){' in output

    rewritten = source.read_text()
    assert rewritten != MESSY_CPP
    assert 'int add(int a, int b)' in rewritten

    # The rewrite is stable, so a second run of the hook passes.
    assert uncrustify.UncrustifyGroup().run(_args(source))[0].passed


@pytest.mark.external
@needs_uncrustify
def test_runner_exit_codes(tmp_path):
    clean = tmp_path / 'clean.cpp'
    clean.write_text(CLEAN_CPP)
    messy = tmp_path / 'messy.cpp'
    messy.write_text(MESSY_CPP)

    assert runner.main(['uncrustify', str(clean)]) == 0
    assert runner.main(['uncrustify', str(messy)]) == 1
    assert runner.main(['uncrustify', str(messy)]) == 0


@pytest.mark.external
@needs_uncrustify
def test_c_and_cpp_groups_are_checked_separately(tmp_path):
    header = tmp_path / 'legacy.h'
    header.write_text('int add(int a, int b);\n')
    source = tmp_path / 'greeter.cpp'
    source.write_text(MESSY_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(header, source))
    assert [(r.name, r.passed) for r in results] == [
        ('uncrustify -l C', True),
        ('uncrustify -l CPP', False),
    ]


@pytest.mark.external
@needs_uncrustify
def test_linelength_override_changes_the_verdict(tmp_path):
    """A line that fits in 100 columns but not in 40 is only wrapped at the shorter width."""
    source = tmp_path / 'wide.cpp'
    source.write_text(
        'int compute(int alpha, int beta, int gamma)\n'
        '{\n'
        '  return alpha + beta + gamma;\n'
        '}\n'
    )
    assert uncrustify.UncrustifyGroup().run(_args(source))[0].passed
    assert not uncrustify.UncrustifyGroup().run(_args(source, linelength=20))[0].passed


@pytest.mark.external
@needs_uncrustify
@pytest.mark.skipif(not _CPP_PKG.is_dir(), reason='test_files/cpp_pkg not populated yet')
def test_bundled_cpp_package_is_clean():
    sources = sorted(
        str(path)
        for path in _CPP_PKG.rglob('*')
        if path.suffix.lstrip('.') in uncrustify.C_EXTENSIONS + uncrustify.CPP_EXTENSIONS
    )
    if not sources:
        pytest.skip('test_files/cpp_pkg has no C or C++ sources yet')
    results = uncrustify.UncrustifyGroup().run(_args(*[Path(s) for s in sources]))
    failures = [r.output for r in results if not r.passed]
    assert not failures, '\n'.join(failures)
