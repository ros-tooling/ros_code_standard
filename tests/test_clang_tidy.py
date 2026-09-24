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
Tests for the clang_tidy checker group.

Every fixture is built under tmp_path: a source tree with a .clang-tidy that enables one check,
and a build tree holding the compile_commands.json that names the sources.
Nothing is compiled, because clang-tidy only needs the command line, not its result.
"""

import argparse
import json
from pathlib import Path

from ros_code_standard import runner
from ros_code_standard.checkers import clang_tidy as clang_tidy_checker

GROUP = clang_tidy_checker.ClangTidyGroup()

# One check, so a fixture's findings do not move with the clang-tidy version.
CLANG_TIDY_CONFIG = "Checks: '-*,modernize-use-nullptr'\n"

# stddef.h and stdint.h come from the clang-tidy wheel's own resource directory, so these
# includes also assert that the wheel finds its builtin headers from inside the virtualenv.
DIRTY = """\
#include <stddef.h>
#include <stdint.h>

int* make() {
  int* p = 0;
  return p;
}

size_t size() { return (uint32_t)0; }
"""

CLEAN = """\
#include <stddef.h>
#include <stdint.h>

int* make() {
  int* p = nullptr;
  return p;
}

size_t size() { return (uint32_t)0; }
"""


def package(root: Path, name: str, sources: dict[str, str]) -> Path:
    """Write a source package and its compilation database, and return the package source dir."""
    source_dir = root / 'src' / name
    build_dir = root / 'build' / name
    source_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / '.clang-tidy').write_text(CLANG_TIDY_CONFIG)
    database = []
    for filename, content in sources.items():
        (source_dir / filename).write_text(content)
        database.append({
            'directory': str(build_dir),
            'command': f'g++ -std=c++17 -c {source_dir / filename}',
            'file': str(source_dir / filename),
        })
    (build_dir / 'compile_commands.json').write_text(json.dumps(database, indent=2))
    return source_dir


def workspace(root: Path) -> Path:
    """Write the single-package workspace most tests use, and return its source dir."""
    return package(root, 'demo', {'dirty.cpp': DIRTY, 'clean.cpp': CLEAN})


def parse(*argv: str) -> argparse.Namespace:
    """Parse hook arguments the way the runner's subparser does."""
    parser = argparse.ArgumentParser()
    GROUP.register_args(parser)
    return parser.parse_args(list(argv))


def check(*argv: str) -> list:
    """Run the group over the given hook arguments."""
    return GROUP.run(parse(*argv))


def output(results: list) -> str:
    """Join the output of every result."""
    return '\n'.join(result.output for result in results)


# --- misconfiguration ---


def test_missing_build_dir_fails_with_the_hook_args_form(tmp_path):
    source = workspace(tmp_path)
    results = check(str(source / 'clean.cpp'))
    assert [r.passed for r in results] == [False]
    assert 'compilation database' in results[0].output
    assert 'args: [--build-dir, build]' in results[0].output


def test_nonexistent_build_dir_fails_with_the_colcon_hint(tmp_path):
    source = workspace(tmp_path)
    results = check('--build-dir', str(tmp_path / 'absent'), str(source / 'clean.cpp'))
    assert [r.passed for r in results] == [False]
    assert 'does not exist' in results[0].output
    assert 'DCMAKE_EXPORT_COMPILE_COMMANDS=ON' in results[0].output


def test_build_dir_without_a_database_fails_with_the_colcon_hint(tmp_path):
    source = workspace(tmp_path)
    empty = tmp_path / 'empty'
    empty.mkdir()
    results = check('--build-dir', str(empty), str(source / 'clean.cpp'))
    assert [r.passed for r in results] == [False]
    assert 'No compile_commands.json' in results[0].output
    assert 'colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON' in results[0].output


def test_missing_config_file_fails(tmp_path):
    source = workspace(tmp_path)
    results = check(
        '--build-dir', str(tmp_path / 'build'),
        '--config', str(tmp_path / 'absent.clang-tidy'),
        str(source / 'clean.cpp'),
    )
    assert [r.passed for r in results] == [False]
    assert 'Could not find config file' in results[0].output


def test_no_files_is_skipped(tmp_path):
    workspace(tmp_path)
    results = check('--build-dir', str(tmp_path / 'build'))
    assert [(r.passed, r.skipped) for r in results] == [(True, True)]


# --- database discovery ---


def test_find_databases_walks_the_build_tree(tmp_path):
    package(tmp_path, 'first', {'clean.cpp': CLEAN})
    package(tmp_path, 'second', {'clean.cpp': CLEAN})
    found = clang_tidy_checker.find_databases(tmp_path / 'build')
    assert found == [
        tmp_path / 'build' / 'first' / 'compile_commands.json',
        tmp_path / 'build' / 'second' / 'compile_commands.json',
    ]


def test_find_databases_skips_hidden_and_private_directories(tmp_path):
    package(tmp_path, '_deps', {'clean.cpp': CLEAN})
    package(tmp_path, '.cache', {'clean.cpp': CLEAN})
    assert clang_tidy_checker.find_databases(tmp_path / 'build') == []


def test_find_databases_accepts_a_database_file(tmp_path):
    workspace(tmp_path)
    database = tmp_path / 'build' / 'demo' / 'compile_commands.json'
    assert clang_tidy_checker.find_databases(database) == [database]


def test_database_sources_resolves_entries_relative_to_their_directory(tmp_path):
    source = workspace(tmp_path)
    database = tmp_path / 'build' / 'relative' / 'compile_commands.json'
    database.parent.mkdir(parents=True)
    database.write_text(json.dumps([
        {'directory': str(source), 'command': 'g++ -c clean.cpp', 'file': 'clean.cpp'},
        {
            'directory': str(source),
            'command': 'g++ -c dirty.cpp',
            'file': str(source / 'dirty.cpp'),
        },
    ]))
    assert clang_tidy_checker.database_sources(database) == {
        source / 'clean.cpp',
        source / 'dirty.cpp',
    }


def test_group_files_splits_by_database_and_collects_the_rest(tmp_path):
    first = package(tmp_path, 'first', {'clean.cpp': CLEAN})
    second = package(tmp_path, 'second', {'dirty.cpp': DIRTY})
    header = first / 'extra.hpp'
    header.write_text('#pragma once\n')
    databases, _ = clang_tidy_checker.load_databases(
        clang_tidy_checker.find_databases(tmp_path / 'build')
    )
    groups, unlisted = clang_tidy_checker.group_files(
        [str(first / 'clean.cpp'), str(second / 'dirty.cpp'), str(header)],
        databases,
    )
    assert groups == {
        tmp_path / 'build' / 'first': [str(first / 'clean.cpp')],
        tmp_path / 'build' / 'second': [str(second / 'dirty.cpp')],
    }
    assert unlisted == [str(header)]


def test_unreadable_database_is_reported(tmp_path):
    source = workspace(tmp_path)
    broken = tmp_path / 'build' / 'broken' / 'compile_commands.json'
    broken.parent.mkdir(parents=True)
    broken.write_text('not json')
    results = check('--build-dir', str(tmp_path / 'build'), str(source / 'clean.cpp'))
    assert any(not r.passed and 'broken' in r.output for r in results)


# --- checking ---


def test_clean_file_passes(tmp_path):
    source = workspace(tmp_path)
    results = check('--build-dir', str(tmp_path / 'build'), str(source / 'clean.cpp'))
    assert all(r.passed for r in results), output(results)


def test_wheel_clang_tidy_finds_its_builtin_headers(tmp_path):
    source = workspace(tmp_path)
    results = check('--build-dir', str(tmp_path / 'build'), str(source / 'clean.cpp'))
    assert 'file not found' not in output(results)


def test_dirty_file_fails_even_though_clang_tidy_exits_zero(tmp_path):
    source = workspace(tmp_path)
    results = check('--build-dir', str(tmp_path / 'build'), str(source / 'dirty.cpp'))
    failed = [r for r in results if not r.passed]
    assert failed, output(results)
    assert 'modernize-use-nullptr' in failed[0].output


def test_file_not_in_any_database_is_skipped_not_failed(tmp_path, capsys):
    source = workspace(tmp_path)
    header = source / 'extra.hpp'
    header.write_text('#pragma once\n\ninline int* make() { return 0; }\n')
    results = check('--build-dir', str(tmp_path / 'build'), str(header))
    assert all(r.passed for r in results), output(results)
    skipped = [r for r in results if r.skipped and r.output]
    assert len(skipped) == 1
    assert str(header) in skipped[0].output
    assert 'did not check these files' in skipped[0].output
    # The runner only reports failures, so the notice is printed to be visible at all.
    assert str(header) in capsys.readouterr().out


def test_config_file_replaces_the_source_tree_lookup(tmp_path):
    source = workspace(tmp_path)
    # One check the fixture cannot trigger. clang-tidy errors out when nothing is enabled.
    config = tmp_path / 'other.clang-tidy'
    config.write_text("Checks: '-*,bugprone-assert-side-effect'\n")
    results = check(
        '--build-dir', str(tmp_path / 'build'),
        '--config', str(config),
        str(source / 'dirty.cpp'),
    )
    assert all(r.passed for r in results), output(results)


def test_fix_rewrites_the_file_and_fails_with_a_restage_message(tmp_path):
    source = workspace(tmp_path)
    dirty = source / 'dirty.cpp'
    results = check('--build-dir', str(tmp_path / 'build'), '--fix', '--quiet', str(dirty))
    assert 'nullptr;' in dirty.read_text()
    restage = [r for r in results if not r.passed and clang_tidy_checker.FIXED in r.output]
    assert len(restage) == 1
    assert str(dirty) in restage[0].output


def test_jobs_checks_several_databases(tmp_path):
    first = package(tmp_path, 'first', {'dirty.cpp': DIRTY})
    second = package(tmp_path, 'second', {'dirty.cpp': DIRTY})
    results = check(
        '--build-dir', str(tmp_path / 'build'),
        '--jobs', '2',
        str(first / 'dirty.cpp'), str(second / 'dirty.cpp'),
    )
    assert len(results) == 2
    assert [r.passed for r in results] == [False, False]
    assert str(first / 'dirty.cpp') in results[0].output
    assert str(second / 'dirty.cpp') in results[1].output


# --- command line ---


def test_build_command_forwards_the_optional_flags(tmp_path):
    args = parse(
        '--build-dir', str(tmp_path),
        '--config', str(tmp_path / 'cfg'),
        '--header-filter', 'include/demo/.*',
        '--fix', '--quiet', '--system-headers', '--explain-config',
        # A value that starts with a dash needs the --extra-arg=VALUE form, as argparse
        # otherwise reads it as another option.
        '--extra-arg=-DFOO=1',
        '--extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
    )
    cmd = clang_tidy_checker.build_command(args)
    assert cmd[0].endswith('clang-tidy')
    assert cmd[1:] == [
        '--config-file', str(tmp_path / 'cfg'),
        '--header-filter', 'include/demo/.*',
        '--fix-errors',
        '--quiet',
        '--system-headers',
        '--explain-config',
        '--extra-arg=-DFOO=1',
        '--extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13',
    ]


def test_build_command_passes_no_config_by_default(tmp_path):
    assert clang_tidy_checker.build_command(parse('--build-dir', str(tmp_path))) == [
        clang_tidy_checker.tool('clang-tidy'),
    ]


# --- runner ---


def test_runner_exit_codes(tmp_path):
    source = workspace(tmp_path)
    build = str(tmp_path / 'build')
    assert runner.main(['clang_tidy', '--build-dir', build, str(source / 'clean.cpp')]) == 0
    assert runner.main(['clang_tidy', '--build-dir', build, str(source / 'dirty.cpp')]) == 1
    assert runner.main(['clang_tidy', str(source / 'clean.cpp')]) == 1
