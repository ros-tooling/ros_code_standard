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
uncrustify with the ament_code_style configuration.

uncrustify has no PyPI package and no upstream Linux binary, so the hook takes it from PATH
the way the polymath-go hook takes the Go toolchain.
Unlike ament_uncrustify, which only prints a diff, this hook reformats the files it finds and
fails so the developer re-stages them.
"""

import argparse
from collections import defaultdict
from configparser import ConfigParser
import difflib
import importlib.resources
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from ros_code_standard.checker import check_group, CheckerGroup, Result, run

# Config files bundled alongside this checker
CONFIG_DIR = importlib.resources.files(__package__)

# The extension to language mapping of ament_uncrustify.
C_EXTENSIONS = ('c', 'cc', 'h', 'hh')
CPP_EXTENSIONS = ('cpp', 'cxx', 'hpp', 'hxx')

# Appended by uncrustify --suffix to the copies it writes under --prefix.
SUFFIX = '.uncrustify'

# uncrustify is not always idempotent, so reformatting repeats until the content settles.
MAX_PASSES = 5

UNCRUSTIFY_MISSING = (
    'uncrustify was not found on PATH.\n'
    "Ubuntu and Debian: 'sudo apt install uncrustify'.\n"
    "macOS: 'brew install uncrustify'.\n"
    'ROS 2 builds uncrustify through the uncrustify_vendor package, so sourcing a ROS 2\n'
    'installation puts a suitable version on PATH as well.'
)

REFORMATTED = '(files have been reformatted, please re-stage and recommit)'

# uncrustify prints strings such as 'Uncrustify-0.72.0_f' or 'Uncrustify_d-0.78.1',
# depending on how it was built.
_VERSION_RE = re.compile(r'^Uncrustify[^0-9]*([0-9]+\.[0-9]+\.[0-9]+)')


class UncrustifyError(Exception):
    """An invocation of the uncrustify binary failed."""


def parse_version(version_output: str) -> tuple[int, ...] | None:
    """Return the version triple printed by `uncrustify --version`, or None if unrecognized."""
    match = _VERSION_RE.match(version_output.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split('.'))


def select_config(version_output: str) -> Path | None:
    """
    Return the bundled ament config for the version uncrustify reports.

    0.78.1 changed enough option behavior that ament ships a second configuration for it.
    That release and anything newer use the 0.78 config, everything older uses the 0.72 one.
    Returns None when the version string cannot be parsed.
    """
    version = parse_version(version_output)
    if version is None:
        return None
    name = 'ament_code_style_0_78.cfg' if version >= (0, 78, 1) else 'ament_code_style_0_72.cfg'
    return Path(str(CONFIG_DIR / name))


def normalize_language(language: str | None) -> str | None:
    """Return uncrustify's own spelling of a --language argument."""
    return 'CPP' if language == 'C++' else language


def group_by_language(files: list[str], language: str | None = None) -> dict[str, list[str]]:
    """
    Split files into uncrustify `-l` groups by extension, as ament_uncrustify does.

    Extensions outside both ament lists are dropped, since uncrustify would guess at them.
    A forced language collects every recognized file into that one group instead.
    """
    languages = {f'.{extension}': 'C' for extension in C_EXTENSIONS}
    languages.update({f'.{extension}': 'CPP' for extension in CPP_EXTENSIONS})

    grouped: dict[str, list[str]] = defaultdict(list)
    for path in files:
        matched = languages.get(Path(path).suffix)
        if matched is not None:
            grouped[language or matched].append(path)
    return dict(grouped)


def config_code_width(config_text: str) -> int:
    """Return the code_width setting of an uncrustify configuration."""
    parser = ConfigParser()
    parser.read_string('[DEFAULT]\n' + config_text)
    value = parser['DEFAULT']['code_width']
    return int(re.split('[ \t#]', value, maxsplit=1)[0])


def linelength_config(config: Path, linelength: int) -> Path | None:
    """
    Write a copy of config whose code_width is linelength, or None if it already matches.

    The caller owns the returned temporary file and is responsible for removing it.
    """
    config_text = config.read_text()
    if config_code_width(config_text) == linelength:
        return None
    handle, path = tempfile.mkstemp(prefix='uncrustify_', suffix='.cfg')
    with os.fdopen(handle, 'w') as override:
        override.write(f'{config_text}\ncode_width={linelength}')
    return Path(path)


def _output_path(temp_dir: Path, absolute: Path) -> Path:
    """Return where `uncrustify --prefix` writes the reformatted copy of an absolute path."""
    return temp_dir / (str(absolute.relative_to(absolute.anchor)) + SUFFIX)


def preview(
    binary: str,
    config: Path,
    language: str,
    files: list[str],
    temp_dir: Path,
) -> dict[str, bytes]:
    """
    Return the reformatted content of every file uncrustify would change.

    --prefix sends the output to temp_dir, so this leaves the sources untouched.
    """
    absolute = [Path(path).resolve() for path in files]
    cmd = [
        binary, '-c', str(config), '-l', language,
        '--prefix', str(temp_dir), '--suffix', SUFFIX,
        *(str(path) for path in absolute),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise UncrustifyError((proc.stdout + proc.stderr).strip())

    changed = {}
    for path, resolved in zip(files, absolute):
        formatted = _output_path(temp_dir, resolved).read_bytes()
        if formatted != resolved.read_bytes():
            changed[path] = formatted
    return changed


def reformat(binary: str, config: Path, language: str, files: list[str]) -> list[str]:
    """
    Rewrite files in place until uncrustify stops changing them, and return the ones it wrote.

    uncrustify can need more than one pass to reach a stable result, which is why
    ament_uncrustify also reinvokes it on the files that changed.
    """
    written: list[str] = []
    pending = list(files)
    with tempfile.TemporaryDirectory(prefix='uncrustify_') as temp_dir:
        for _ in range(MAX_PASSES):
            changed = preview(binary, config, language, pending, Path(temp_dir))
            if not changed:
                return written
            for path, formatted in changed.items():
                Path(path).write_bytes(formatted)
            written = sorted(set(written) | set(changed))
            pending = sorted(changed)
    unsettled = ', '.join(pending)
    raise UncrustifyError(
        f"'uncrustify' did not settle on a final result after {MAX_PASSES} passes: {unsettled}"
    )


def diff_lines(path: str, before: bytes, after: bytes) -> list[str]:
    """Return the unified diff between a file's original and reformatted content."""
    return list(
        difflib.unified_diff(
            before.decode('utf-8', errors='replace').splitlines(keepends=True),
            after.decode('utf-8', errors='replace').splitlines(keepends=True),
            fromfile=path,
            tofile=path + SUFFIX,
            n=0,
        )
    )


def format_group(binary: str, config: Path, language: str, files: list[str]) -> Result:
    """
    Check one language group and reformat it in place if uncrustify would change anything.

    --check compares byte for byte without writing, so a clean commit costs one process
    and touches no file.
    """
    name = f'uncrustify -l {language}'
    check = run(name, [binary, '-c', str(config), '-l', language, '--check'], files)
    if check.passed:
        return check

    originals = {path: Path(path).read_bytes() for path in files}
    try:
        written = reformat(binary, config, language, files)
    except UncrustifyError as error:
        return Result(name=name, passed=False, output=str(error), cmd=check.cmd)

    if not written:
        # --check rejected the group but reformatting found nothing to write.
        return Result(name=name, passed=False, output=check.output, cmd=check.cmd)

    report = []
    for path in written:
        report.append(f"Code style divergence in file '{path}': reformatted file")
        diff = diff_lines(path, originals[path], Path(path).read_bytes())
        report.extend(line.rstrip('\r\n') for line in diff)
    plural = '' if len(written) == 1 else 's'
    report.append(f'{len(written)} file{plural} with code style divergence')
    report.append(REFORMATTED)
    return Result(name=name, passed=False, output='\n'.join(report), cmd=check.cmd)


@check_group
class UncrustifyGroup(CheckerGroup):

    name = 'uncrustify'

    def register_args(self, subparser: argparse.ArgumentParser) -> None:
        """Register the ament_uncrustify options that this hook forwards."""
        subparser.add_argument(
            '--linelength',
            metavar='N',
            type=int,
            help='Override the code_width of the bundled configuration',
        )
        subparser.add_argument(
            '--language',
            choices=['C', 'C++', 'CPP'],
            help="Force uncrustify's -l instead of choosing it per file extension",
        )
        super().register_args(subparser)

    def run(self, args: argparse.Namespace) -> list[Result]:
        binary = shutil.which('uncrustify')
        if binary is None:
            return [Result(name='uncrustify', passed=False, output=UNCRUSTIFY_MISSING)]

        version = subprocess.run([binary, '--version'], capture_output=True, text=True)
        version_output = (version.stdout + version.stderr).strip()
        if version.returncode != 0:
            return [Result(
                name='uncrustify',
                passed=False,
                output=f"The invocation of '{binary} --version' failed:\n{version_output}",
            )]

        config = select_config(version_output)
        if config is None:
            return [Result(
                name='uncrustify',
                passed=False,
                output=f"Invalid uncrustify version '{version_output}'",
            )]

        groups = group_by_language(args.files, normalize_language(args.language))
        if not groups:
            return [Result(name='uncrustify', passed=True, skipped=True)]

        override = None
        try:
            if args.linelength is not None:
                override = linelength_config(config, args.linelength)
            active = override or config
            return [
                format_group(binary, active, language, files)
                for language, files in sorted(groups.items())
            ]
        finally:
            if override is not None:
                override.unlink(missing_ok=True)
