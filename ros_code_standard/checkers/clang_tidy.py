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
clang-tidy against the compilation databases of a colcon build directory.

Experimental, and the only hook here that cannot work on a bare source checkout: clang-tidy
needs the compiler command line for every file it analyses.
The consumer points the hook at a build tree with args: [--build-dir, build], and colcon writes
a compile_commands.json per package when the workspace is built with
-DCMAKE_EXPORT_COMPILE_COMMANDS=ON.

Like ament_clang_tidy, this searches the given path for compile_commands.json files, treats a
path that names a file as a compilation database itself, and runs one clang-tidy per database.
It diverges in three ways.
Staged files replace the database's own file list, so only what is being committed is analysed,
and a staged file that no database lists is reported as skipped instead of silently checked.
A --config file is passed as --config-file rather than inlined as YAML on the command line.
A finding fails the hook: clang-tidy exits 0 for warnings, so, as ament_clang_tidy does when it
builds its xUnit report, the output is scanned for diagnostics.
ament also drops gtest sources and anything under a package's test directory from the file list
it builds; here that belongs in the hook's own exclude: pattern.
"""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import functools
import hashlib
import json
import os
from pathlib import Path
import re

from ros_code_standard.checker import check_group, CheckerGroup, Result, run, tool

NAME = 'clang-tidy'

DATABASE = 'compile_commands.json'

# clang-tidy reports findings as warnings and exits 0 unless a check is configured as an error,
# so the output decides whether the hook passes.
DIAGNOSTIC = re.compile(r':\d+:\d+: (?:warning|error):')

BUILD_DIR_REQUIRED = (
    'clang-tidy needs a compilation database and a source checkout does not have one, so this\n'
    'hook has to be pointed at a build directory:\n'
    '\n'
    '  - id: ros-clang-tidy\n'
    '    args: [--build-dir, build]\n'
)

BUILD_DIR_HINT = (
    'Build the workspace with the compilation database enabled:\n'
    '\n'
    '  colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON\n'
)

NOT_IN_DATABASE = (
    'clang-tidy did not check these files because no compilation database under {path} lists\n'
    'them. Headers normally have no entry of their own and are analysed through the sources\n'
    'that include them, which needs --header-filter. A source that is missing here has not\n'
    'been built yet, so rebuild the workspace.'
)

FIXED = '(clang-tidy --fix-errors has rewritten these files, please re-stage and recommit)'


def find_databases(path: Path) -> list[Path]:
    """Return every compile_commands.json under path, or path itself when it names one."""
    if path.is_file():
        return [path]
    found = []
    for dirpath, dirnames, filenames in os.walk(path):
        # Same pruning as ament_clang_tidy: skip hidden and private directories.
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(('.', '_')))
        if DATABASE in filenames:
            found.append(Path(dirpath) / DATABASE)
    return sorted(found)


def database_sources(database: Path) -> set[Path]:
    """
    Return the resolved source paths a compilation database lists.

    An entry's file may be relative, in which case it is relative to that entry's directory.
    """
    sources = set()
    for entry in json.loads(database.read_text()):
        name = entry.get('file')
        if not name:
            continue
        directory = entry.get('directory') or str(database.parent)
        sources.add((Path(directory) / name).resolve())
    return sources


def load_databases(databases: list[Path]) -> tuple[dict[Path, set[Path]], list[str]]:
    """Return the sources of each database keyed by its directory, plus one message per failure."""
    loaded: dict[Path, set[Path]] = {}
    errors = []
    for database in databases:
        try:
            loaded[database.parent] = database_sources(database)
        except (OSError, ValueError) as exc:
            errors.append(f'{database}: {exc}')
    return loaded, errors


def group_files(
    files: list[str],
    databases: dict[Path, set[Path]],
) -> tuple[dict[Path, list[str]], list[str]]:
    """Split files by the directory of the first database that lists them, plus the rest."""
    groups: dict[Path, list[str]] = defaultdict(list)
    unlisted = []
    for path in files:
        resolved = Path(path).resolve()
        for directory in sorted(databases):
            if resolved in databases[directory]:
                groups[directory].append(str(resolved))
                break
        else:
            unlisted.append(path)
    return dict(groups), unlisted


def build_command(args: argparse.Namespace) -> list[str]:
    """Return the clang-tidy command line the hook arguments ask for, without files."""
    cmd = [tool(NAME)]
    if args.config:
        # ament inlines the config as YAML; --config-file leaves that to clang-tidy. Without it
        # clang-tidy walks up from each source for a .clang-tidy, which is the ament default.
        cmd += ['--config-file', args.config]
    if args.header_filter:
        cmd += ['--header-filter', args.header_filter]
    if args.fix:
        cmd.append('--fix-errors')
    if args.quiet:
        cmd.append('--quiet')
    if args.system_headers:
        cmd.append('--system-headers')
    if args.explain_config:
        cmd.append('--explain-config')
    cmd += [f'--extra-arg={extra}' for extra in args.extra_arg]
    return cmd


def digests(files: list[str]) -> dict[str, str]:
    """Return a content hash per file, skipping the ones that cannot be read."""
    hashes = {}
    for path in files:
        try:
            hashes[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            continue
    return hashes


def check_database(command: list[str], group: tuple[Path, list[str]]) -> Result:
    """Run clang-tidy over the files of one compilation database."""
    directory, files = group
    result = run(NAME, command + ['-p', str(directory)], files)
    if result.passed and DIAGNOSTIC.search(result.output):
        return Result(name=NAME, passed=False, output=result.output, cmd=result.cmd)
    return result


def check_databases(command: list[str], groups: dict[Path, list[str]], jobs: int) -> list[Result]:
    """Run clang-tidy once per compilation database, over at most jobs databases at a time."""
    worker = functools.partial(check_database, command)
    items = sorted(groups.items())
    if jobs > 1 and len(items) > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            return list(pool.map(worker, items))
    return [worker(item) for item in items]


def fail(output: str) -> list[Result]:
    """Return the single failing result of a hook that could not run at all."""
    return [Result(name=NAME, passed=False, output=output)]


@check_group
class ClangTidyGroup(CheckerGroup):

    name = 'clang_tidy'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        super().register_args(subparser)
        subparser.add_argument(
            '--build-dir',
            metavar='PATH',
            help='A colcon build directory to search for compile_commands.json files, or one '
                 'such file. Required.',
        )
        subparser.add_argument(
            '--config',
            metavar='PATH',
            help='A .clang-tidy file, passed to clang-tidy as --config-file. Without it, '
                 'clang-tidy looks for .clang-tidy up the source tree.',
        )
        subparser.add_argument(
            '--header-filter',
            metavar='REGEX',
            help='Report diagnostics from the non-system headers matching this regex.',
        )
        subparser.add_argument(
            '--fix',
            action='store_true',
            help='Apply the suggested fixes with --fix-errors, then fail so they are re-staged.',
        )
        subparser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress the counts of ignored warnings.',
        )
        subparser.add_argument(
            '--system-headers',
            action='store_true',
            help='Report diagnostics from system headers too.',
        )
        subparser.add_argument(
            '--explain-config',
            action='store_true',
            help='Explain which configuration file enables each check.',
        )
        subparser.add_argument(
            '--jobs',
            type=int,
            default=1,
            metavar='N',
            help='Number of compilation databases to analyse in parallel (default: 1).',
        )
        subparser.add_argument(
            '--extra-arg',
            action='append',
            default=[],
            metavar='ARG',
            help='Append a compiler argument to every command line. Repeatable, and an '
                 'argument that itself starts with a dash needs the --extra-arg=ARG form. '
                 'Not an ament_clang_tidy option; it is the escape hatch for a toolchain '
                 "that clang-tidy's own driver does not find, as in "
                 '--extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13.',
        )

    def run(self, args: argparse.Namespace) -> list[Result]:
        if not args.build_dir:
            return fail(BUILD_DIR_REQUIRED)
        build_dir = Path(args.build_dir)
        if not build_dir.exists():
            return fail(f"'{build_dir}' does not exist.\n{BUILD_DIR_HINT}")
        databases = find_databases(build_dir)
        if not databases:
            return fail(f"No {DATABASE} under '{build_dir}'.\n{BUILD_DIR_HINT}")
        if args.config and not Path(args.config).is_file():
            return fail(f"Could not find config file '{args.config}'.")
        if not args.files:
            return [Result(name=NAME, passed=True, skipped=True)]

        loaded, errors = load_databases(databases)
        results = [Result(name=NAME, passed=False, output=error) for error in errors]
        groups, unlisted = group_files(args.files, loaded)

        if unlisted:
            notice = NOT_IN_DATABASE.format(path=build_dir) + '\n' + '\n'.join(
                f'  {path}' for path in unlisted
            )
            # Only failing results are reported, so the notice is printed to be seen at all.
            print(notice)
            results.append(Result(name=NAME, passed=True, skipped=True, output=notice))

        before = digests(args.files) if args.fix else {}
        results += check_databases(build_command(args), groups, args.jobs)
        after = digests(args.files) if args.fix else {}
        changed = [path for path, digest in after.items() if before.get(path, digest) != digest]
        if changed:
            results.append(Result(name=NAME, passed=False, output='\n'.join(changed + [FIXED])))
        return results
