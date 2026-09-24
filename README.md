# ROS 2 Code Standard

pre-commit hooks for the ROS 2 core code formatters and linters.

> [!WARNING]
> This repository is STILL EXPERIMENTAL, it is not yet in use on any ROS core packages

These hooks are the [`ament_lint`](https://github.com/ament/ament_lint) linters with their ROS 2 configurations, run by pre-commit instead of CMake.
One hook is provided per `ament_cmake_<tool>` package, so a `package.xml` test dependency list translates one-to-one onto hook ids.
Consuming repositories reference this repo directly via `.pre-commit-config.yaml`.
No config files need to be copied or kept in sync.

See [docs/DESIGN.md](./docs/DESIGN.md) for the reasoning and [DEVELOPING.md](./DEVELOPING.md) for development workflows.

## Prerequisites

Install [pre-commit](https://pre-commit.com).
Our recommended approach is with [uv](https://github.com/astral-sh/uv).

```shell
uv tool install --with pre-commit-uv pre-commit
```

Set up pre-commit hooks in the repository:

```shell
pre-commit install
```

`ros-uncrustify` also needs `uncrustify` on `PATH`.
See its [hook reference](#ros-uncrustify) entry.

## Configuration

Add the following to your repository's `.pre-commit-config.yaml`.
This block is equivalent to `ament_lint_common`.

```yaml
---
repos:
  - repo: https://github.com/ros-tooling/ros_code_standard
    rev: v0.1.0
    hooks:
      - id: ros-copyright
      - id: ros-cppcheck
      - id: ros-cpplint
      - id: ros-flake8
      - id: ros-lint-cmake
      - id: ros-pep257
      - id: ros-uncrustify
      - id: ros-xmllint
```

Optional linters that are not part of `ament_lint_common`:

```yaml
      - id: ros-clang-format
      - id: ros-clang-tidy
        args: [--build-dir, build]
      - id: ros-mypy
      - id: ros-pycodestyle
      - id: ros-pyflakes
```

## Migrating from ament_lint_auto

Remove the linter test dependencies from `package.xml`:

```xml
<test_depend>ament_lint_auto</test_depend>
<test_depend>ament_lint_common</test_depend>
```

Remove the linter block from `CMakeLists.txt`:

```cmake
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()
```

If the package listed individual `ament_cmake_<tool>` dependencies instead of `ament_lint_common`, add the matching `ros-<tool>` hook for each one.

Files that were excluded with `AMENT_LINT_AUTO_FILE_EXCLUDE` or an `AMENT_IGNORE` marker need a pre-commit `exclude:` pattern on the relevant hook instead.

## First-time use

Apply your newly configured hooks to all existing files:

```shell
pre-commit run --all-files
```

Stage the reformatted files, then run again to surface any failures that require manual correction.

> [!NOTE]
> After a large reformatting pass, add the commit hash to `.git-blame-ignore-revs` so `git blame` points back to the original authors rather than the reformatting commit.

## CI

Add the following GitHub Actions workflow to run pre-commit on every push and pull request:

```yaml
---
name: Lint

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      # Only needed for ros-uncrustify.
      - run: sudo apt-get install -y --no-install-recommends uncrustify
      - uses: pre-commit/action@v3.0.1
```

## Hook Reference

Hook ids mirror the `ament_cmake_<tool>` package names.
The first eight are the `ament_lint_common` set.

| Hook | ament package | Tool |
|---|---|---|
| `ros-copyright` | `ament_cmake_copyright` | `ament_copyright` |
| `ros-cppcheck` | `ament_cmake_cppcheck` | cppcheck |
| `ros-cpplint` | `ament_cmake_cpplint` | cpplint |
| `ros-flake8` | `ament_cmake_flake8` | flake8 |
| `ros-lint-cmake` | `ament_cmake_lint_cmake` | cmakelint |
| `ros-pep257` | `ament_cmake_pep257` | pydocstyle |
| `ros-uncrustify` | `ament_cmake_uncrustify` | uncrustify |
| `ros-xmllint` | `ament_cmake_xmllint` | lxml |
| `ros-clang-format` | `ament_cmake_clang_format` | clang-format |
| `ros-clang-tidy` | `ament_cmake_clang_tidy` | clang-tidy |
| `ros-mypy` | `ament_cmake_mypy` | mypy |
| `ros-pycodestyle` | `ament_cmake_pycodestyle` | pycodestyle |
| `ros-pyflakes` | `ament_cmake_pyflakes` | pyflakes |

`ament_cmake_pclint` has no hook.
PC-lint Plus is proprietary and is not part of any ROS 2 default.

Hook arguments that take a list are comma separated, and a value that starts with `-` must use the `--option=value` form so it is not read as another option.

> [!NOTE]
> `ros-uncrustify` and `ros-clang-format` are both in-place C++ formatters and their ament configurations disagree on short function bodies and constructor initializer lists.
> Enable one or the other, not both.
> `ament_lint_common` uses uncrustify.

---

### `ros-copyright`

Runs `ament_copyright` over staged C, C++, CMake, and Python files, and over the repository's `LICENSE` and `CONTRIBUTING.md` when they exist.
Checks that each file carries a copyright notice and a recognized license header, and that the two repository-level files match one of the known license texts.
A `setup.py` beside a `package.xml` is skipped, as `ament_copyright` does when it crawls a package.

**Optional:**

- `--add-missing COPYRIGHT_NAME LICENSE` -- Insert a notice and header into files that have none, using the given copyright holder and license name (for example `apache2`), then check. The hook fails when anything was inserted so the files get re-staged.
- `--verbose` -- Report every file checked, not only the ones with errors

```yaml
- id: ros-copyright
  args: [--add-missing, 'Polymath Robotics, Inc.', apache2]
```

Run `ament_copyright --list-licenses` in the hook environment for the license names.

---

### `ros-cppcheck`

Runs cppcheck with the ament_cppcheck flag set (`-f --inline-suppr -q -rp --suppress=internalAstError --suppress=unknownMacro`) over the staged C and C++ files, one job per core, and fails on any finding.
`ament_cppcheck` skips every cppcheck 2.x release as too slow for a whole package, and Ubuntu 22.04 and 24.04 both ship 2.x, so on current ROS 2 distributions `ament_lint_common` never actually runs cppcheck.
This hook always runs, so expect findings that `colcon test` never showed you.

**Optional:**

- `--language {c,c++}` -- Force cppcheck to treat every file as this language
- `--libraries NAMES` -- Comma separated cppcheck library configurations to load in addition to the standard C and C++ ones
- `--include-dirs DIRS` -- Comma separated include directories for the files being checked

```yaml
- id: ros-cppcheck
  args: [--language, c++, --libraries, posix, --include-dirs, 'include,src/private']
```

---

### `ros-cpplint`

Runs cpplint with the ament_cpplint filter set, a line length of 100, and the ROS header guard convention, so `include/my_pkg/foo.hpp` must guard on `MY_PKG__FOO_HPP_`.
Files are grouped by their nearest `include`, `src`, or `test` ancestor and each group is linted with that directory as cpplint's `--root`, so the guard is correct for every package in a multi-package repository.

**Optional:**

- `--filters=FILTER,FILTER` -- Extra cpplint category filters, appended to the ament defaults
- `--linelength N` -- Maximum line length, default 100
- `--root PATH` -- Use this cpplint root for every file instead of the computed one

```yaml
- id: ros-cpplint
  args: [--filters=-build/include_order, --linelength, '120']
```

---

### `ros-flake8`

Runs `flake8` on Python files with the `ament_flake8` configuration and its seven plugins: `flake8-blind-except`, `flake8-builtins`, `flake8-class-newline`, `flake8-comprehensions`, `flake8-deprecated`, `flake8-quotes`, and `flake8-import-order` (Google import order style, max line length 99).
The configuration is passed with `--config`, which flake8 treats as authoritative, so a `setup.cfg`, `tox.ini`, or `.flake8` in your repository is not read and cannot weaken the ROS 2 style.

**Optional:**

- `--linelength N` -- Maximum line length, overriding the 99 in the ament configuration

```yaml
- id: ros-flake8
  args: [--linelength, '120']
```

---

### `ros-lint-cmake`

Runs `cmakelint` over `CMakeLists.txt`, `*.cmake`, and `*.cmake.in` files with `ament_lint_cmake`'s line length of 140.
Like ament, it widens cmakelint's filename check so `*.cmake.in` templates are linted instead of silently skipped.
Unlike ament, it passes `--config=None` so no `.cmakelintrc` is read from the working directory, `$XDG_CONFIG_DIR`, or your home directory: the standard is the same on every machine.
Per-file `# lint_cmake: <filters>` pragmas still work.

**Optional:**

- `--filters=FILTERS` -- Comma-separated cmakelint category filters, each prefixed with `+` or `-`. Same meaning as the `FILTERS` argument of `ament_lint_cmake`.

```yaml
- id: ros-lint-cmake
  args: [--filters=-readability/mixedcase,-convention/filename]
```

---

### `ros-pep257`

Runs `pydocstyle` on Python files with the `ament_pep257` ignore list, which ament calls the `ament` convention: `D100` to `D107`, `D203`, `D212`, and `D404` are ignored.
That leaves `D211` and `D213` active, so a class docstring starts on the line after the `class` statement and a multi-line docstring summary starts on the line after the opening quotes.
Unlike bare `pydocstyle`, files whose names begin with `test_` are checked.

**Optional:**

- `--ignore CODES` -- Comma separated codes for pydocstyle not to check, replacing the ament list (mutually exclusive with `--select` and `--convention`)
- `--select CODES` -- Comma separated codes for pydocstyle to check, replacing the ament list (mutually exclusive with `--ignore` and `--convention`)
- `--convention NAME` -- A preset list: `ament` (default), `google`, `numpy`, or `pep257` (mutually exclusive with `--ignore` and `--select`)
- `--add-ignore CODES` -- Comma separated codes to remove from the selected list
- `--add-select CODES` -- Comma separated codes to add to the selected list

```yaml
- id: ros-pep257
  args: [--add-ignore, 'D213,D205']
```

---

### `ros-uncrustify`

Runs `uncrustify` with the `ament_code_style` configuration, the same one `ament_uncrustify` ships.
`uncrustify --version` selects the config: 0.78.1 and newer get `ament_code_style_0_78.cfg`, anything older gets `ament_code_style_0_72.cfg`.
Ubuntu 24.04 ships 0.78.1 and Ubuntu 22.04 ships 0.72.0, so both are supported.

Files are split into a `-l C` group (`.c`, `.cc`, `.h`, `.hh`) and a `-l CPP` group (`.cpp`, `.cxx`, `.hpp`, `.hxx`), matching `ament_uncrustify`, and each group is checked separately.
A C++ header named `.h` is therefore parsed as C, as in ament.
`--language C++` is the escape hatch.

Files that need reformatting are rewritten in place and the hook fails so you re-stage them, with the unified diff of every change in the output.
This differs from `ament_uncrustify`, which prints the diff and leaves the files alone.
Nothing else is written to your repository.

> [!NOTE]
> Requires `uncrustify` on `PATH`.
> There is no PyPI package and no upstream Linux binary, so it cannot be installed into the hook virtualenv.
> Ubuntu and Debian: `sudo apt install uncrustify`.
> macOS: `brew install uncrustify`.
> ROS 2 builds it through [`uncrustify_vendor`](https://github.com/ros2/uncrustify_vendor), so sourcing a ROS 2 installation also puts a suitable version on `PATH`.

**Optional:**

- `--linelength N` -- Override the config's `code_width` of 100
- `--language {C,C++,CPP}` -- Force uncrustify's `-l` instead of choosing it per file extension

```yaml
- id: ros-uncrustify
  args: [--language, C++]
```

---

### `ros-xmllint`

Checks XML files for well-formedness and validates them against the schemas they declare, using `lxml` rather than the libxml2 `xmllint` binary, so nothing needs to be installed outside the hook virtualenv.
Schemas come from an `xml-model` processing instruction or from `xsi:noNamespaceSchemaLocation` on the root element.
XML Schema and RelaxNG are both supported, and a relative reference is resolved next to the document, as `ament_xmllint` does.
The ROS `package_format2.xsd` and `package_format3.xsd` schemas are bundled with the hook, so validating a `package.xml` needs no network access.
Schematron references are recognized and skipped, which is the one thing `ament_xmllint` does that this hook does not.

No arguments.

---

### `ros-clang-format`

Runs clang-format with the ament `.clang-format` style.
Reformats the staged C and C++ files in place and then fails, so you re-stage and recommit.
`ament_clang_format` is not part of `ament_lint_common`.
Its style disagrees with the ament uncrustify configuration on short function bodies and on constructor initializer lists, so enable this hook or `ros-uncrustify`, not both.

No arguments.

---

### `ros-clang-tidy`

Runs `clang-tidy` over the staged C and C++ sources, using the compilation databases of a colcon build directory.
Translated from `ament_clang_tidy`.

> [!NOTE]
> Experimental, and the only hook here that cannot work on a bare checkout.
> clang-tidy needs the compiler command line for every file it analyses, so the hook has to be pointed at a build tree:
>
> ```shell
> colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
> ```
>
> colcon writes one `build/<package>/compile_commands.json` per package.
> Without `--build-dir`, or with a build directory that holds no database, the hook fails with that command rather than pretending to check anything.

The hook searches `--build-dir` recursively for `compile_commands.json` files, skipping `.` and `_` directories, and runs one `clang-tidy -p <database dir>` per database with the staged files that database lists.
A path that names a file is treated as a compilation database itself.

Staged files that no database lists are reported as skipped, not as failures.
Headers are normally in this group: they have no entry of their own and are analysed through the sources that include them, which needs `--header-filter`.
A source that shows up as skipped has not been built yet.

Findings fail the hook.
clang-tidy exits 0 for warnings, so, like `ament_clang_tidy` when it builds its report, the hook fails on any reported diagnostic.

**Required:**

- `--build-dir PATH` -- A colcon build directory to search for `compile_commands.json`, or one such file

**Optional:**

- `--config PATH` -- A `.clang-tidy` file, passed as `--config-file`. Without it, clang-tidy looks for `.clang-tidy` up the source tree, as `ament_clang_tidy` does
- `--header-filter REGEX` -- Report diagnostics from the non-system headers matching this regex
- `--fix` -- Apply the suggested fixes with `--fix-errors`, then fail so you re-stage them
- `--quiet` -- Suppress the counts of ignored warnings
- `--system-headers` -- Report diagnostics from system headers too
- `--explain-config` -- Explain which configuration file enables each check
- `--jobs N` -- Number of compilation databases to analyse in parallel (default: 1)
- `--extra-arg=ARG` -- Append a compiler argument to every command line. Repeatable

```yaml
- id: ros-clang-tidy
  args: [--build-dir, build, --header-filter, 'include/my_package/.*']
  exclude: ^test/
```

> [!NOTE]
> The bundled clang-tidy finds its own builtin headers, but it picks the newest GCC installation on the machine to locate the C++ standard library.
> If that installation has no headers, every `#include <cstddef>` is reported as `file not found` and the hook fails for reasons unrelated to lint.
> Point it at the right toolchain with `--extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/11`.

> [!NOTE]
> `ament_clang_tidy` excludes gtest sources and everything under a package's `test/` directory.
> This hook lints what you staged, so use `exclude:` for the same effect.

---

### `ros-mypy`

Runs `mypy` on Python files with the `ament_mypy` configuration, which sets `ignore_missing_imports = True`.
The cache is directed at the null device, so no `.mypy_cache` is written into your repository.

**Optional:**

- `--strict` -- Use `ament_mypy_strict.toml` (`strict = true`, `pretty = true`) instead of `ament_mypy.ini`

```yaml
- id: ros-mypy
  args: [--strict]
```

> [!NOTE]
> mypy type-checks the imports of the files it is given, so results depend on what is installed in the hook virtualenv rather than in your workspace.
> `ignore_missing_imports = True` keeps unresolved ROS message and client library imports from failing the hook.

> [!NOTE]
> The hook passes `--explicit-package-bases`, so module names are derived from the repository root.
> Without it, a workspace with more than one Python package fails immediately with `Duplicate module named "setup"`, because pre-commit hands mypy every staged file at once instead of one package at a time.

---

### `ros-pycodestyle`

Runs `pycodestyle` on Python files with the `ament_pycodestyle` configuration: max line length 99 and an empty ignore list.
Clearing the ignore list means `E121`, `E123`, `E126`, `E226`, `E24`, `E704`, `W503`, and `W504` are all reported, which `pycodestyle` suppresses by default.
The configuration is passed with `--config`, so a `[pycodestyle]` section in your `setup.cfg` or `tox.ini` is not read.

**Optional:**

- `--linelength N` -- Maximum line length, overriding the 99 in the ament configuration

```yaml
- id: ros-pycodestyle
  args: [--linelength, '120']
```

> [!NOTE]
> `ros-pycodestyle` is stricter than `ros-flake8` on purpose, and it is not part of `ament_lint_common`.
> `ament_flake8.ini` uses `extend-ignore`, so flake8 keeps its own default ignore list, while `ament_pycodestyle.ini` clears it.
> A line break before a binary operator (`W503`) or `x*y` without spaces (`E226`) passes `ros-flake8` and fails `ros-pycodestyle`.

---

### `ros-pyflakes`

Runs `pyflakes` on Python files, with no configuration, matching `ament_pyflakes`.
It reports unused imports, undefined names, unused local variables, and similar correctness problems, and says nothing about style.

No arguments.

---

## What changes versus ament_lint

- **Files, not directories.**
  pre-commit hands each hook the staged files that match its type, so `AMENT_IGNORE` markers are not honored.
  Use `exclude:` patterns instead.
- **Formatters fix.**
  `ros-uncrustify`, `ros-clang-format`, and `ros-copyright --add-missing` rewrite files and fail so you re-stage them.
  ament only reports.
- **No xUnit output.**
  The exit code is the result.
- **Current tool versions.**
  Tools are pinned to current PyPI releases in this repo's `pyproject.toml`, not to the versions in a ROS distribution.
  cpplint is 2.0.x where ament bundles a 1.5.5 fork, and cppcheck is 2.17 where ament refuses to run 2.x at all.
