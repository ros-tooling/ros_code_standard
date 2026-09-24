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

Nothing else is needed on Linux x86_64 and aarch64 or macOS x86_64 and arm64.
The uncrustify binary ships with the hook.

## Configuration

Add the following to your repository's `.pre-commit-config.yaml`.
This block is equivalent to `ament_lint_common`.

```yaml
---
repos:
  - repo: https://github.com/ros-tooling/ros_code_standard
    rev: v0.1.1
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

Packages that call the linters explicitly carry per-linter options that map onto hook fields:

| CMake | pre-commit |
|---|---|
| `ament_cpplint(EXCLUDE path ...)`, `AMENT_LINT_AUTO_FILE_EXCLUDE`, `AMENT_IGNORE` | `exclude: ^path` on that hook |
| `ament_cppcheck(LANGUAGE c++)`, `ament_uncrustify(LANGUAGE c++)` | `args: [--language, c++]` |
| `ament_cpplint(FILTERS -a -b)`, `ament_lint_cmake(FILTERS ...)` | `args: [--filters=-a,-b]` |
| `ament_cpplint(MAX_LINE_LENGTH 120)`, `ament_flake8(MAX_LINE_LENGTH 120)` | `args: [--linelength, '120']` |
| `ament_cppcheck(INCLUDE_DIRS a b)`, `ament_cppcheck(LIBRARIES a b)` | `args: [--include-dirs, 'a,b', --libraries, 'a,b']` |
| `AMENT_LINT_AUTO_EXCLUDE ament_cmake_<tool>` | leave `ros-<tool>` out of the hook list |

For example, `rcpputils` excludes a vendored header from four linters and forces C++ for two:

```yaml
- id: ros-copyright
  exclude: ^include/rcpputils/tl_expected/
- id: ros-cppcheck
  args: [--language, c++]
  exclude: ^include/rcpputils/tl_expected/
- id: ros-cpplint
  exclude: ^include/rcpputils/tl_expected/
- id: ros-lint-cmake
- id: ros-uncrustify
  args: [--language, C++]
  exclude: ^include/rcpputils/tl_expected/
- id: ros-xmllint
```

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

Runs `ament_cpplint`, the ROS 2 linter itself, over the staged C and C++ files.
It is not PyPI cpplint.
ament vendors a modified fork of cpplint 1.5.5, and the checks cpplint 2.0 added do not match ROS 2 style: a package that passes `colcon test` reports `build/c++17`, `whitespace/newline`, and a wider `build/include_what_you_use` under the PyPI release.
Because this hook calls `ament_cpplint`, its findings, filter set, line length of 100, `--root` grouping by the nearest `include`, `src`, or `test` ancestor, and the ROS header guard convention (`include/my_pkg/foo.hpp` guards on `MY_PKG__FOO_HPP_`) are identical to what `colcon test` reports.

**Optional:**

- `--filters=FILTER,FILTER` -- Extra cpplint category filters, appended to ament's defaults
- `--linelength N` -- Maximum line length. ament uses 100
- `--root PATH` -- Use this cpplint root for every file instead of the one ament computes from the path

```yaml
- id: ros-cpplint
  args: [--filters=-build/include_order, --linelength, '120']
```

Vendored or generated C++ that a package excluded from its CMake lint test needs an `exclude:` pattern here, since the hook only sees a file list:

```yaml
- id: ros-cpplint
  exclude: ^include/rcpputils/tl_expected/
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

Runs `ament_lint_cmake` over `CMakeLists.txt`, `*.cmake`, and `*.cmake.in` files.
This is `ament_lint_cmake` itself, not PyPI cmakelint with ament's flags.
The ament package vendors a modified fork of cmakelint, so running the real thing means the findings match `colcon test` exactly, and the 140-character line length, the ROS 2 parenthesis and string rules, and the handling of `*.cmake.in` templates all come from ament.
Per-file `# lint_cmake: <filters>` pragmas work as they do under `colcon test`.

> [!NOTE]
> Like ament, this hook reads `.cmakelintrc` from the working directory, from `$XDG_CONFIG_DIR`, and from your home directory when present, so a personal rc file can change the result.
> That is kept for parity with `colcon test`.

**Optional:**

- `--filters=FILTERS` -- Comma-separated cmakelint category filters, each prefixed with `+` or `-`, passed straight to `ament_lint_cmake`. Same meaning as the `FILTERS` argument of the CMake macro

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

The uncrustify version decides the output, not just the configuration, so the hook ships its own binary rather than using whatever is installed.
`--uncrustify-version` selects it, and the matching ament config follows: 0.78.1 uses `ament_code_style_0_78.cfg`, 0.72.0 uses `ament_code_style_0_72.cfg`.

| ROS 2 distribution | `--uncrustify-version` |
|---|---|
| rolling, jazzy | `0.78.1` (the default) |
| humble | `0.72.0` |

Files are split into a `-l C` group (`.c`, `.cc`, `.h`, `.hh`) and a `-l CPP` group (`.cpp`, `.cxx`, `.hpp`, `.hxx`), matching `ament_uncrustify`, and each group is checked separately.
A C++ header named `.h` is therefore parsed as C, as in ament.
`--language C++` is the escape hatch.

Files that need reformatting are rewritten in place and the hook fails so you re-stage them, with the unified diff of every change in the output.
This differs from `ament_uncrustify`, which prints the diff and leaves the files alone.
Nothing else is written to your repository.

> [!NOTE]
> The uncrustify binary ships with the hook, as the `ros-uncrustify-bin` wheel, for Linux x86_64, Linux aarch64, macOS x86_64, and macOS arm64.
> Nothing needs to be installed on those platforms.
> Anywhere else, install uncrustify yourself and add `--system-uncrustify`, which uses the binary on `PATH` and picks the ament config from the version it reports.
> A distribution package may not match your ROS 2 distribution's pin: Ubuntu 22.04 packages 0.72.0, and it reformats files that rolling's 0.78.1 accepts.

**Optional:**

- `--uncrustify-version {0.78.1,0.72.0}` -- Which bundled uncrustify to run (default `0.78.1`). Ignored with `--system-uncrustify`
- `--system-uncrustify` -- Use the `uncrustify` on `PATH` instead of the bundled one, with the ament config chosen from the version it reports
- `--linelength N` -- Override the config's `code_width` of 100
- `--language {C,C++,CPP}` -- Force uncrustify's `-l` instead of choosing it per file extension

```yaml
- id: ros-uncrustify
  args: [--uncrustify-version, '0.72.0', --language, C++]
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
- **ament's own tools where it matters.**
  `ros-copyright`, `ros-cpplint`, and `ros-lint-cmake` run the `ament_lint` 0.21.2 packages themselves, so their findings match `colcon test` exactly.
  The Python linters and cppcheck are current PyPI releases with ament's configuration; cppcheck is 2.17 where ament refuses to run 2.x at all.
