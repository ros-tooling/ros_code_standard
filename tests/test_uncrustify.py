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

Most of the group is the bookkeeping that decides how uncrustify is invoked: which binary,
which of the two ament configs, and which files go into the C group and which into the CPP
group.
Those tests run everywhere, driving binary resolution with a shell stub that only answers
--version, so no uncrustify is needed.

The tests marked `external` run a real uncrustify. They find one through the
ros-uncrustify-bin wheel when it is installed, and otherwise through PATH plus
ROS_UNCRUSTIFY_TEST_BINARIES, a path-separated list of binaries to probe. Each skips when
the version it needs is not available.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest

from ros_code_standard import runner
from ros_code_standard.checkers import uncrustify

_PROJECT_ROOT = Path(__file__).parent.parent
_CPP_PKG = _PROJECT_ROOT / 'test_files' / 'cpp_pkg'

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

# Reduced from src/thread_name.cpp of ros2/rcpputils at 64a437c, which is green under
# ament_lint_common on rolling. uncrustify 0.78.1 leaves the call wrapped as written;
# 0.72.0 moves the first argument onto its own line. This is the divergence that made the
# hook ship its own binary rather than trust whatever apt installed.
RCPPUTILS_CALL_WRAP = """\
#include <string>

namespace rcpputils
{

int wide_char_to_multi_byte(
  unsigned code_page, unsigned long flags, const wchar_t * wide, int wide_length,
  char * out, int out_length, const char * fallback, bool * used_fallback);

int size_of(const wchar_t * description)
{
  int size_needed = wide_char_to_multi_byte(CP_UTF8, 0, description, -1, nullptr, 0, nullptr,
      nullptr);
  return size_needed;
}

}  // namespace rcpputils
"""


def _args(*files: Path, **overrides) -> argparse.Namespace:
    namespace = argparse.Namespace(
        files=[str(f) for f in files],
        linelength=None,
        language=None,
        uncrustify_version=uncrustify.DEFAULT_VERSION,
        system_uncrustify=False,
    )
    for key, value in overrides.items():
        setattr(namespace, key, value)
    return namespace


def _fake_wheel(**binaries: str) -> types.SimpleNamespace:
    """
    Build a stand-in for ros_uncrustify_bin that hands back the given paths.

    Keys are versions with dots written as underscores, so they can be keyword arguments.
    """
    paths = {version.replace('_', '.'): value for version, value in binaries.items()}

    def binary(version: str = uncrustify.DEFAULT_VERSION) -> Path:
        if version not in paths:
            raise ValueError(f'unknown uncrustify version {version!r}')
        return Path(paths[version])

    return types.SimpleNamespace(
        VERSIONS=tuple(paths),
        DEFAULT_VERSION=uncrustify.DEFAULT_VERSION,
        binary=binary,
    )


def _install_wheel(monkeypatch, module: object | None) -> None:
    """
    Put a fake ros_uncrustify_bin in sys.modules, or None to make the import fail.

    The import machinery hands back whatever sys.modules holds, and a None entry is the
    documented way to make an import raise, so the real wheel is never needed.
    """
    monkeypatch.setitem(sys.modules, 'ros_uncrustify_bin', module)


def _version_stub(tmp_path: Path, name: str, version_output: str, code: int = 0) -> Path:
    """Write an executable that only answers --version, standing in for an uncrustify."""
    path = tmp_path / name
    path.write_text(f'#!/bin/sh\necho "{version_output}"\nexit {code}\n')
    path.chmod(0o755)
    return path


def _discover_binaries() -> dict[str, Path]:
    """
    Map version to a real uncrustify on this machine, for the tests marked external.

    The wheel is preferred because that is what consumers run. PATH and
    ROS_UNCRUSTIFY_TEST_BINARIES fill in for a developer who has not installed it yet.
    """
    found: dict[str, Path] = {}
    try:
        import ros_uncrustify_bin
    except ImportError:
        pass
    else:
        for version in ros_uncrustify_bin.VERSIONS:
            found[version] = Path(ros_uncrustify_bin.binary(version))

    candidates = [
        Path(entry)
        for entry in os.environ.get('ROS_UNCRUSTIFY_TEST_BINARIES', '').split(os.pathsep)
        if entry
    ]
    on_path = shutil.which('uncrustify')
    if on_path is not None:
        candidates.append(Path(on_path))

    for candidate in candidates:
        if not candidate.is_file():
            continue
        probe = subprocess.run([str(candidate), '--version'], capture_output=True, text=True)
        parsed = uncrustify.parse_version(probe.stdout + probe.stderr)
        if parsed is not None:
            found.setdefault('.'.join(str(part) for part in parsed), candidate)
    return found


BINARIES = _discover_binaries()


def needs(*versions: str):
    """Skip unless a real uncrustify of every named version is available."""
    missing = [version for version in versions if version not in BINARIES]
    return pytest.mark.skipif(bool(missing), reason=f'no uncrustify {", ".join(missing)}')


def _wheel_of(monkeypatch, *versions: str) -> None:
    """Install a fake wheel backed by the real binaries discovered on this machine."""
    _install_wheel(monkeypatch, _fake_wheel(**{v.replace('.', '_'): str(BINARIES[v])
                                               for v in versions}))


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
        # The same parse serves --uncrustify-version, which passes a bare version.
        ('0.78.1', 'ament_code_style_0_78.cfg'),
        ('0.72.0', 'ament_code_style_0_72.cfg'),
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
    assert uncrustify.parse_version('0.72.0') == (0, 72, 0)


def test_every_bundled_version_maps_to_a_config():
    for version in uncrustify.BUNDLED_VERSIONS:
        assert uncrustify.select_config(version) is not None
    assert uncrustify.DEFAULT_VERSION in uncrustify.BUNDLED_VERSIONS


# --- bundled binary resolution ---


def test_bundled_default_picks_0_78_1_and_its_config(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'Uncrustify-0.78.1_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))

    binary, config = uncrustify.resolve_bundled(uncrustify.DEFAULT_VERSION)
    assert binary == str(stub)
    assert config.name == 'ament_code_style_0_78.cfg'


def test_bundled_0_72_0_picks_the_0_72_config(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify-0.72.0', 'Uncrustify-0.72.0_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_72_0': str(stub)}))

    binary, config = uncrustify.resolve_bundled('0.72.0')
    assert binary == str(stub)
    assert config.name == 'ament_code_style_0_72.cfg'


def test_version_guard_rejects_a_binary_of_the_wrong_version(tmp_path, monkeypatch):
    """A wheel that shipped the wrong build must fail, not silently format with it."""
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'Uncrustify-0.72.0_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))

    result = uncrustify.resolve_bundled('0.78.1')
    assert isinstance(result, uncrustify.Result)
    assert not result.passed
    assert 'reports' in result.output
    assert '0.72.0' in result.output
    assert 'reinstall' in result.output


def test_bundled_binary_that_will_not_run_is_reported(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'boom', code=3)
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))

    result = uncrustify.resolve_bundled('0.78.1')
    assert isinstance(result, uncrustify.Result)
    assert '--version' in result.output
    assert 'boom' in result.output


def test_bundled_unknown_version_reports_the_wheels_error(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'Uncrustify-0.78.1_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))

    result = uncrustify.resolve_bundled('0.60.0')
    assert isinstance(result, uncrustify.Result)
    assert 'cannot supply uncrustify 0.60.0' in result.output


def test_a_wheel_missing_its_binary_is_reported(monkeypatch):
    """ros_uncrustify_bin.binary raises FileNotFoundError for a wheel built elsewhere."""
    def binary(version: str = uncrustify.DEFAULT_VERSION) -> Path:
        raise FileNotFoundError(f'no uncrustify {version} in this wheel')

    _install_wheel(
        monkeypatch,
        types.SimpleNamespace(
            VERSIONS=uncrustify.BUNDLED_VERSIONS,
            DEFAULT_VERSION=uncrustify.DEFAULT_VERSION,
            binary=binary,
        ),
    )

    result = uncrustify.resolve_bundled('0.78.1')
    assert isinstance(result, uncrustify.Result)
    assert not result.passed
    assert 'cannot supply uncrustify 0.78.1' in result.output


def test_missing_wheel_reports_the_platform_message(tmp_path, monkeypatch):
    _install_wheel(monkeypatch, None)
    monkeypatch.setattr(
        uncrustify, 'format_group', lambda *a: pytest.fail('uncrustify must not be invoked')
    )
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [(r.name, r.passed, r.skipped) for r in results] == [('uncrustify', False, False)]
    assert results[0].output == uncrustify.BUNDLED_MISSING
    assert 'Linux x86_64' in results[0].output
    assert 'macOS arm64' in results[0].output
    assert '--system-uncrustify' in results[0].output


def test_bundled_mode_is_the_default(tmp_path, monkeypatch):
    """Without --system-uncrustify nothing reaches PATH, even when an uncrustify is there."""
    _install_wheel(monkeypatch, None)
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: pytest.fail('PATH must not be used'))
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    assert uncrustify.UncrustifyGroup().run(_args(source))[0].output == uncrustify.BUNDLED_MISSING


# --- system binary resolution ---


def test_system_mode_uses_path_and_the_detected_version(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify', 'Uncrustify-0.72.0_f')
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: str(stub))
    _install_wheel(monkeypatch, None)

    binary, config = uncrustify.resolve_system()
    assert binary == str(stub)
    assert config.name == 'ament_code_style_0_72.cfg'


def test_system_mode_ignores_the_requested_version(tmp_path, monkeypatch):
    """--uncrustify-version selects a bundled binary, so it has nothing to say here."""
    stub = _version_stub(tmp_path, 'uncrustify', 'Uncrustify-0.72.0_f')
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: str(stub))
    seen = []

    def _record(binary, config, language, files):
        seen.append((binary, config.name))
        return uncrustify.Result(name='uncrustify', passed=True)

    monkeypatch.setattr(uncrustify, 'format_group', _record)
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    uncrustify.UncrustifyGroup().run(
        _args(source, system_uncrustify=True, uncrustify_version='0.78.1')
    )
    assert seen == [(str(stub), 'ament_code_style_0_72.cfg')]


def test_system_mode_missing_binary_fails_with_an_install_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: None)
    monkeypatch.setattr(
        uncrustify, 'format_group', lambda *a: pytest.fail('uncrustify must not be invoked')
    )
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source, system_uncrustify=True))
    assert [(r.name, r.passed, r.skipped) for r in results] == [('uncrustify', False, False)]
    assert results[0].output == uncrustify.UNCRUSTIFY_MISSING
    assert 'apt install uncrustify' in results[0].output
    assert 'brew install uncrustify' in results[0].output
    assert 'uncrustify_vendor' in results[0].output


def test_system_mode_missing_binary_makes_the_runner_exit_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: None)
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)
    assert runner.main(['uncrustify', '--system-uncrustify', str(source)]) == 1


def test_system_mode_unparseable_version_fails(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify', 'Frobnicate 1.2')
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: str(stub))

    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)
    results = uncrustify.UncrustifyGroup().run(_args(source, system_uncrustify=True))
    assert not results[0].passed
    assert 'Invalid uncrustify version' in results[0].output


# --- argument parsing ---


def test_hook_arguments_have_the_documented_defaults():
    parser = argparse.ArgumentParser()
    uncrustify.UncrustifyGroup().register_args(parser)
    parsed = parser.parse_args(['a.cpp'])
    assert parsed.uncrustify_version == '0.78.1'
    assert parsed.system_uncrustify is False
    assert parsed.files == ['a.cpp']

    parsed = parser.parse_args(['--uncrustify-version', '0.72.0', '--system-uncrustify', 'a.cpp'])
    assert parsed.uncrustify_version == '0.72.0'
    assert parsed.system_uncrustify is True


def test_an_unbundled_version_is_rejected_by_argparse():
    parser = argparse.ArgumentParser()
    uncrustify.UncrustifyGroup().register_args(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(['--uncrustify-version', '0.69.0', 'a.cpp'])


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


def test_no_matching_files_skips(tmp_path, monkeypatch):
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'Uncrustify-0.78.1_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))
    unrelated = tmp_path / 'notes.md'
    unrelated.write_text('hello\n')

    results = uncrustify.UncrustifyGroup().run(_args(unrelated))
    assert [(r.passed, r.skipped) for r in results] == [(True, True)]


# --- line length override ---


def test_config_code_width_of_both_bundled_configs():
    for name in ('ament_code_style_0_72.cfg', 'ament_code_style_0_78.cfg'):
        config = Path(str(uncrustify.CONFIG_DIR / name))
        assert uncrustify.config_code_width(config.read_text()) == 100


def test_linelength_config_is_none_when_it_matches_the_config():
    config = uncrustify.select_config('0.78.1')
    assert uncrustify.linelength_config(config, 100) is None


def test_linelength_config_appends_an_override():
    config = uncrustify.select_config('0.78.1')
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
    """The temp config must not outlive the hook."""
    stub = _version_stub(tmp_path, 'uncrustify-0.78.1', 'Uncrustify-0.78.1_f')
    _install_wheel(monkeypatch, _fake_wheel(**{'0_78_1': str(stub)}))
    source = tmp_path / 'messy.cpp'
    source.write_text(MESSY_CPP)
    seen = []

    def _record(binary, config, language, files):
        seen.append(Path(config))
        return uncrustify.Result(name='uncrustify', passed=True)

    monkeypatch.setattr(uncrustify, 'format_group', _record)

    uncrustify.UncrustifyGroup().run(_args(source, linelength=120))
    assert len(seen) == 1
    assert not seen[0].exists()


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


# --- end to end, needs a real binary ---


@pytest.mark.external
@needs('0.78.1')
def test_clean_file_passes(tmp_path, monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [r.passed for r in results] == [True], results[0].output
    assert source.read_text() == CLEAN_CPP


@pytest.mark.external
@needs('0.78.1')
def test_messy_file_is_reformatted_and_reported(tmp_path, monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
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
@needs('0.78.1')
def test_runner_exit_codes(tmp_path, monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
    clean = tmp_path / 'clean.cpp'
    clean.write_text(CLEAN_CPP)
    messy = tmp_path / 'messy.cpp'
    messy.write_text(MESSY_CPP)

    assert runner.main(['uncrustify', str(clean)]) == 0
    assert runner.main(['uncrustify', str(messy)]) == 1
    assert runner.main(['uncrustify', str(messy)]) == 0


@pytest.mark.external
@needs('0.78.1')
def test_c_and_cpp_groups_are_checked_separately(tmp_path, monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
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
@needs('0.78.1')
def test_linelength_override_changes_the_verdict(tmp_path, monkeypatch):
    """A line that fits in 100 columns but not in 20 is only wrapped at the shorter width."""
    _wheel_of(monkeypatch, '0.78.1')
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
@needs('0.78.1')
def test_system_mode_runs_the_path_binary(tmp_path, monkeypatch):
    """--system-uncrustify reaches a real binary and formats with the config for its version."""
    monkeypatch.setattr(uncrustify.shutil, 'which', lambda _: str(BINARIES['0.78.1']))
    _install_wheel(monkeypatch, None)
    source = tmp_path / 'greeter.cpp'
    source.write_text(CLEAN_CPP)

    results = uncrustify.UncrustifyGroup().run(_args(source, system_uncrustify=True))
    assert [r.passed for r in results] == [True], results[0].output


@pytest.mark.external
@needs('0.78.1')
def test_bundled_cpp_package_is_clean(monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
    sources = sorted(
        path
        for path in _CPP_PKG.rglob('*')
        if path.suffix.lstrip('.') in uncrustify.C_EXTENSIONS + uncrustify.CPP_EXTENSIONS
    )
    assert sources, 'test_files/cpp_pkg has no C or C++ sources'
    results = uncrustify.UncrustifyGroup().run(_args(*sources))
    failures = [r.output for r in results if not r.passed]
    assert not failures, '\n'.join(failures)


# --- the parity regression that motivated the bundled binary ---


@pytest.mark.external
@needs('0.78.1')
def test_rcpputils_call_wrap_passes_under_0_78_1(tmp_path, monkeypatch):
    _wheel_of(monkeypatch, '0.78.1')
    source = tmp_path / 'thread_name.cpp'
    source.write_text(RCPPUTILS_CALL_WRAP)

    results = uncrustify.UncrustifyGroup().run(_args(source))
    assert [r.passed for r in results] == [True], results[0].output
    assert source.read_text() == RCPPUTILS_CALL_WRAP


@pytest.mark.external
@needs('0.72.0')
def test_rcpputils_call_wrap_is_reformatted_under_0_72_0(tmp_path, monkeypatch):
    """The symptom: apt's 0.72.0 rewrites a file that rolling's 0.78.1 accepts."""
    _wheel_of(monkeypatch, '0.72.0')
    source = tmp_path / 'thread_name.cpp'
    source.write_text(RCPPUTILS_CALL_WRAP)

    results = uncrustify.UncrustifyGroup().run(_args(source, uncrustify_version='0.72.0'))
    assert [r.passed for r in results] == [False]
    assert 'int size_needed = wide_char_to_multi_byte(\n' in source.read_text()


@pytest.mark.external
@needs('0.78.1', '0.72.0')
def test_the_two_bundled_versions_disagree_on_the_same_file(tmp_path, monkeypatch):
    """One hook, two verdicts, chosen by --uncrustify-version alone."""
    _wheel_of(monkeypatch, '0.78.1', '0.72.0')
    rolling = tmp_path / 'rolling.cpp'
    rolling.write_text(RCPPUTILS_CALL_WRAP)
    humble = tmp_path / 'humble.cpp'
    humble.write_text(RCPPUTILS_CALL_WRAP)

    assert uncrustify.UncrustifyGroup().run(_args(rolling, uncrustify_version='0.78.1'))[0].passed
    assert not uncrustify.UncrustifyGroup().run(
        _args(humble, uncrustify_version='0.72.0')
    )[0].passed


@pytest.mark.external
@needs('0.78.1', '0.72.0')
@pytest.mark.skipif(
    not os.environ.get('ROS_RCPPUTILS_CLONE'), reason='ROS_RCPPUTILS_CLONE is not set'
)
def test_rcpputils_thread_name_parity(tmp_path, monkeypatch):
    """The whole upstream file, when a clone is available to point at."""
    original = Path(os.environ['ROS_RCPPUTILS_CLONE']) / 'src' / 'thread_name.cpp'
    if not original.is_file():
        pytest.skip(f'{original} does not exist')
    content = original.read_bytes()

    rolling = tmp_path / 'rolling.cpp'
    rolling.write_bytes(content)
    humble = tmp_path / 'humble.cpp'
    humble.write_bytes(content)

    _wheel_of(monkeypatch, '0.78.1', '0.72.0')
    assert uncrustify.UncrustifyGroup().run(_args(rolling, uncrustify_version='0.78.1'))[0].passed
    assert not uncrustify.UncrustifyGroup().run(
        _args(humble, uncrustify_version='0.72.0')
    )[0].passed
    assert rolling.read_bytes() == content
