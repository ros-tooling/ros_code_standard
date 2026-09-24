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
cpplint with the ament_cpplint configuration.

cpplint runs in-process rather than as a subprocess because ament_cpplint replaces
cpplint's header guard function with one that uses the ROS naming convention, and a
monkeypatch cannot survive an exec of the console script.
"""

import argparse
import contextlib
import io
import os
import re

import cpplint

from ros_code_standard.checker import check_group, CheckerGroup, Result

#: Source extensions cpplint is told to accept, as in ament_cpplint.
EXTENSIONS = ('c', 'cc', 'cpp', 'cxx')

#: Header extensions cpplint is told to accept, as in ament_cpplint.
HEADERS = ('h', 'hh', 'hpp', 'hxx')

#: Categories ament_cpplint switches off, with ament's reasoning.
DEFAULT_FILTERS = (
    # we do allow C++11
    '-build/c++11',
    # we consider passing non-const references to be ok
    '-runtime/references',
    # we wrap open curly braces for namespaces, classes and functions
    '-whitespace/braces',
    # we don't indent keywords like public, protected and private with one space
    '-whitespace/indent',
    # we allow closing parenthesis to be on the next line
    '-whitespace/parens',
    # we allow the developer to decide about whitespace after a semicolon
    '-whitespace/semicolon',
)

#: Directory names that start a cpplint --root, longest ancestor wins.
ROOT_SUBFOLDER_NAMES = ('include', 'src', 'test')

#: Version control markers that identify a repository root.
REPOSITORY_MARKERS = ('.git', '.hg', '.svn')


def custom_get_header_guard_cpp_variable(filename: str) -> str:
    """
    Return the header guard ROS 2 expects for a header file.

    This is ament_cpplint's replacement for ``cpplint.GetHeaderGuardCPPVariable``.
    The path components below the cpplint root are joined with a double underscore,
    so ``include/pkg/foo.hpp`` with ``--root`` at ``include`` gives ``PKG__FOO_HPP_``.
    """
    # Restore the original filename in case cpplint is invoked from Emacs's flymake.
    filename = re.sub(r'_flymake\.h$', '.h', filename)
    filename = re.sub(r'/\.flymake/([^/]*)$', r'/\1', filename)
    # Replace 'c++' with 'cpp'.
    filename = filename.replace('C++', 'cpp').replace('c++', 'cpp')

    fileinfo = cpplint.FileInfo(filename)
    file_path_from_root = fileinfo.RepositoryName()
    root = cpplint._root
    if root:
        prefix = root + os.sep
        # use consistent separator on Windows
        if os.sep != '/':
            prefix = prefix.replace(os.sep, '/')
        if file_path_from_root.startswith(prefix):
            file_path_from_root = file_path_from_root[len(prefix):]
        else:
            filename = filename.replace(os.sep, '/')
            if filename.startswith(prefix):
                file_path_from_root = filename[len(prefix):]
    # use double separator
    file_path_from_root = file_path_from_root.replace('/', '//')
    return re.sub(r'[^a-zA-Z0-9]', '_', file_path_from_root).upper() + '_'


cpplint.GetHeaderGuardCPPVariable = custom_get_header_guard_cpp_variable


def find_repository_root(path: str) -> str | None:
    """Return the closest ancestor of path that holds a version control marker."""
    current = os.path.abspath(path)
    while os.path.dirname(current) != current:
        current = os.path.dirname(current)
        if any(os.path.exists(os.path.join(current, m)) for m in REPOSITORY_MARKERS):
            return current
    return None


def append_file_to_group(groups: dict[str, list[str]], path: str) -> None:
    """
    Add one file to the group of files that share its cpplint root.

    The root is the longest ancestor directory whose name is ``include``, ``src`` or
    ``test``, expressed relative to the repository root when the file is inside one.
    Files with no such ancestor are grouped under an empty root and linted without
    ``--root``.
    """
    path = os.path.abspath(path)

    # find the longest subpath which ends with one of the root subfolder names
    matches = [
        re.search(
            '^(.+%s%s)%s' % (re.escape(os.sep), re.escape(name), re.escape(os.sep)), path)
        for name in ROOT_SUBFOLDER_NAMES
    ]
    match_groups = sorted((match.group(1) for match in matches if match), key=len)
    root = match_groups[-1] if match_groups else ''

    # ament guards this with a string comparison of the repository root against the
    # root path, which no pair of real ancestor paths satisfies, so ament always ends
    # up passing an absolute root. The custom header guard function above strips
    # either form, so the relative one is used here: it keeps the group keys and the
    # cpplint command line independent of where the repository is checked out.
    if root:
        repo_root = find_repository_root(path)
        if repo_root and root.startswith(repo_root + os.sep):
            root = os.path.relpath(root, repo_root)

    groups.setdefault(root, []).append(path)


def get_file_groups(paths: list[str]) -> dict[str, list[str]]:
    """Group C and C++ files by the cpplint root they should be linted against."""
    groups: dict[str, list[str]] = {}
    for path in paths:
        extension = os.path.splitext(path)[1].lstrip('.')
        if extension in EXTENSIONS + HEADERS:
            append_file_to_group(groups, path)
    return groups


def _base_arguments(args: argparse.Namespace) -> list[str]:
    """Build the cpplint arguments that every root group shares."""
    filters = list(DEFAULT_FILTERS)
    if args.filters:
        filters += args.filters.split(',')
    return [
        '--counting=detailed',
        '--extensions=%s' % ','.join(EXTENSIONS),
        '--headers=%s' % ','.join(HEADERS),
        '--filter=%s' % ','.join(filters),
        '--linelength=%d' % args.linelength,
        # cpplint otherwise prints a line per file, which buries the findings
        '--quiet',
    ]


def _lint_group(root: str, files: list[str], base_arguments: list[str]) -> None:
    """Run cpplint over one root group, leaving the counts on ``_cpplint_state``."""
    arguments = list(base_arguments)
    # cpplint only assigns _root when --root is given, so a stale value would leak
    # from the previous group into this one.
    cpplint._root = None
    if root:
        arguments.append('--root=%s' % root)
    arguments += files
    for filename in cpplint.ParseArguments(arguments):
        cpplint.ProcessFile(filename, cpplint._cpplint_state.verbose_level)


@check_group
class CpplintGroup(CheckerGroup):

    name = 'cpplint'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the options that mirror the ament_cpplint CMake parameters."""
        super().register_args(subparser)
        subparser.add_argument(
            '--filters', metavar='FILTER,FILTER,...',
            help='A comma separated list of category filters to add to the ament defaults')
        subparser.add_argument(
            '--linelength', metavar='N', type=int, default=100,
            help='The maximum line length (default: 100)')
        subparser.add_argument(
            '--root', metavar='PATH',
            help='Override the computed --root option of cpplint for every file')

    def run(self, args: argparse.Namespace) -> list[Result]:
        """Run cpplint once per root group over the staged C and C++ files."""
        groups = get_file_groups(args.files)
        if not groups:
            return [Result(name='cpplint', passed=True, skipped=True)]

        base_arguments = _base_arguments(args)
        override_root = os.path.abspath(args.root) if args.root else None
        stream = io.StringIO()
        state = cpplint._cpplint_state
        state.ResetErrorCounts()
        try:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                for root in sorted(groups.keys()):
                    _lint_group(override_root or root, groups[root], base_arguments)
        except SystemExit:
            # cpplint calls sys.exit() from its own usage errors.
            return [Result(name='cpplint', passed=False, output=stream.getvalue().strip())]

        output = stream.getvalue().strip()
        if state.error_count:
            output += '\nTotal errors found: %d' % state.error_count
        return [Result(name='cpplint', passed=not state.error_count, output=output.strip())]
