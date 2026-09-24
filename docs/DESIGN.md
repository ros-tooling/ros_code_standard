# Design: ament_lint as pre-commit hooks

## Goal

Replace the `ament_lint_auto` / `ament_lint_common` CMake test suite with a drop-in `.pre-commit-config.yaml`.
A ROS 2 package that adopts these hooks removes the `ament_lint_*` test dependencies from `package.xml` and the `BUILD_TESTING` linter block from `CMakeLists.txt`.
Linting moves from `colcon test` to the commit, and to a pre-commit step in CI.

The reference architecture is [polymath_code_standard](https://github.com/polymathrobotics/polymath_code_standard).
This repo copies its runner, its `CheckerGroup` pattern, its per-checker config subpackages, and its release workflow.
Where it diverges, this document says why.

## What ament_lint does today

`ament_lint_auto` reads the `<test_depend>` list in `package.xml`, calls `find_package()` on each, and every `ament_cmake_<tool>` package that is found registers a CTest that runs `ament_<tool>` over the package source tree.
`ament_lint_common` is a meta-package whose dependencies are the eight linters below.

Each `ament_<tool>` is a thin Python CLI that:

- walks the package directory for files by extension, skipping `.`/`_` directories and anything under an `AMENT_IGNORE` marker,
- runs an upstream tool with a configuration bundled in the `ament_<tool>` package,
- writes an xUnit XML result file for CTest.

The configuration is the valuable part.
It is what makes the "ROS 2 code style" a concrete thing.
The file walking and xUnit output are CTest plumbing that pre-commit replaces.

Version studied: `ament_lint` 0.21.2 (`rolling`, commit `36ceda18`).

## Inventory

| ament package | Upstream tool | Bundled config | In `ament_lint_common` | Availability from pip |
|---|---|---|---|---|
| `ament_cmake_copyright` | `ament_copyright` itself | license header templates | yes | git subdirectory install, works |
| `ament_cmake_cppcheck` | cppcheck | CLI flags | yes | `cppcheck` wheel (cppcheck 2.17) |
| `ament_cmake_cpplint` | `ament_cpplint` itself (modified cpplint fork) | filter list, line length 100, header guard patch | yes | git subdirectory install, works |
| `ament_cmake_flake8` | flake8 + 7 plugins | `ament_flake8.ini` | yes | all on PyPI |
| `ament_cmake_lint_cmake` | `ament_lint_cmake` itself (modified cmakelint fork) | line length 140 | yes | git subdirectory install, works |
| `ament_cmake_pep257` | pydocstyle | ignore list | yes | `pydocstyle` 6.3 |
| `ament_cmake_uncrustify` | uncrustify | `ament_code_style_0_72.cfg`, `ament_code_style_0_78.cfg` | yes | **no wheel, no Linux release binary** |
| `ament_cmake_xmllint` | libxml2 `xmllint` | none, schemas fetched from network | yes | replaced by `lxml` |
| `ament_cmake_clang_format` | clang-format | `.clang-format` | no | `clang-format` wheel |
| `ament_cmake_clang_tidy` | clang-tidy | none, needs `compile_commands.json` | no | `clang-tidy` wheel, **needs a build tree** |
| `ament_cmake_mypy` | mypy | `ament_mypy.ini`, `ament_mypy_strict.toml` | no | `mypy` |
| `ament_cmake_pycodestyle` | pycodestyle | `ament_pycodestyle.ini` | no | `pycodestyle` |
| `ament_cmake_pyflakes` | pyflakes | none | no | `pyflakes` |
| `ament_cmake_pclint` | PC-lint Plus | none | no | **proprietary, not translated** |

## Decisions

### Parity first, then better

The first release reproduces what `colcon test` reports today, finding for finding.
A package that is green under `ament_lint_common` on rolling must be green under these hooks, so maintainers can swap the mechanism without a reformatting or fixing pass.
Improvements over ament's behavior, such as newer checks or hermetic configuration, come after parity is established and are recorded as open questions in [PLAN.md](./PLAN.md).

This principle was set after the first pass ran on `ros2/rcpputils`: cpplint 2.0 from PyPI reported `build/c++17`, a new `whitespace/newline` rule that contradicts the ament uncrustify style, and wider include-what-you-use tables, none of which ament's own cpplint reports.

### One hook per ament linter

polymath_code_standard groups by file type: one `polymath-cpp` hook runs clang-format and cpplint together.
This repo instead provides one hook per `ament_cmake_<tool>` package.

The reason is the migration story.
A `package.xml` lists linters one per `<test_depend>`, and `AMENT_LINT_AUTO_EXCLUDE` removes them one at a time.
A one-to-one mapping lets a maintainer translate their manifest mechanically:

```
<test_depend>ament_cmake_cpplint</test_depend>   ->   - id: ros-cpplint
```

Hook ids are the ament suffix with a `ros-` prefix: `ros-copyright`, `ros-cppcheck`, `ros-cpplint`, `ros-flake8`, `ros-lint-cmake`, `ros-pep257`, `ros-uncrustify`, `ros-xmllint`, `ros-clang-format`, `ros-clang-tidy`, `ros-mypy`, `ros-pycodestyle`, `ros-pyflakes`.

The README shows the eight-hook block that equals `ament_lint_common`.

### Call the upstream tool, bundle the ament config

For every linter except copyright, the `ament_<tool>` wrapper adds nothing a pre-commit hook needs.
Each checker calls the upstream tool with the ament configuration shipped as package data beside the checker, exactly as polymath_code_standard does.

Configs are passed by absolute path (`flake8 --config`, `pycodestyle --config`, `clang-format --style=file:`, `uncrustify -c`, `mypy --config-file`) so nothing is written into the consuming repository.
The `.ruff.toml` and `.cpplint.cfg` root-copy trick from polymath_code_standard is not needed here.

### Where ament's behavior is the tool, run ament's tool

Three ament packages cannot be reproduced by "upstream tool plus config", so the hooks install them from the `ament_lint` repository and call their console scripts:

- **`ament_copyright`** is not a wrapper around anything.
  Its parser, its license header templates, and its `--add-missing` mode are the tool.
- **`ament_cpplint`** vendors a modified cpplint fork based on a post-1.5.5 upstream commit: NOLINT accepts clang-analyzer categories, `.hh` counts as a project header for include order, `using namespace std::literals` and `std::placeholders` are allowed, and namespace-closing comments are matched differently.
  On top of that it patches the header guard convention (`include/pkg/foo.hpp` guards on `PKG__FOO_HPP_`) and groups files by their nearest `include`, `src`, or `test` ancestor to pass as `--root`.
  No PyPI cpplint release matches: 1.5.5 lacks the fork's changes and 2.0 adds checks ament never had.
- **`ament_lint_cmake`** vendors a modified cmakelint fork: a closing parenthesis may sit at the opening line's indentation, an over-long line is ignored when it is a single string, filter parsing differs, and in-file `# lint_cmake:` pragmas are its own implementation.

A first implementation ported the cpplint patch and grouping onto cpplint 2.0.2 and applied the cmakelint `IsValidFile` override onto cmakelint 1.4.3.
It was replaced by the wrappers after the parity check on rcpputils.

pip can install a setuptools package from a subdirectory of a git repo, and polymath_code_standard already depends on two packages that way:

```
ament_copyright @ git+https://github.com/ament/ament_lint.git@0.21.2#subdirectory=ament_copyright
ament_cpplint @ git+https://github.com/ament/ament_lint.git@0.21.2#subdirectory=ament_cpplint
ament_lint_cmake @ git+https://github.com/ament/ament_lint.git@0.21.2#subdirectory=ament_lint_cmake
```

All three install with their console scripts intact and none depends on the `ament_lint` helper package.
The pin is the `ament_lint` release, so bumping it is how these hooks track ROS 2.

The copyright hook passes staged source files through to `ament_copyright`.
Because ament's crawler only checks `LICENSE` and `CONTRIBUTING.md` when it walks a repository root, the checker appends those two files when they exist in the working directory so the repo-level check is preserved.

### Formatters fix in place, then fail

polymath_code_standard convention: a formatter dry-runs, and if anything would change it rewrites the files and fails with a "re-stage and recommit" message.
`ros-uncrustify` and `ros-clang-format` follow that convention.
This is the opposite of `ament_uncrustify`, which only prints a diff unless `--reformat` is passed.
Auto-fixing is the point of running in pre-commit.

### Per-file operation replaces directory walking

pre-commit hands each hook the staged files that match its `types`.
That replaces ament's directory walk, and it changes three things:

- `AMENT_IGNORE` markers are not honored.
  Use pre-commit `exclude:` patterns instead.
- ament skipped `.`/`_` prefixed directories and untracked files.
  pre-commit only passes tracked files, which is the same effect in practice.
- Files are linted at the repository root, not per package.
  Only cpplint cares, and its root grouping handles it.

No xUnit output is produced.
pre-commit's exit code is the test result.

### Shared virtualenv

As in polymath_code_standard, every hook declares the same `language: python` and no `additional_dependencies`, so pre-commit builds one virtualenv for the whole repo regardless of which hooks a consumer picks.
All tools are installed up front.
The one exception is uncrustify, discussed below.

## Challenges

These are the linters that need more than "install from PyPI and pass a config".

### uncrustify: no pip package and no Linux binary

uncrustify is the primary ROS 2 C++ formatter, and it is the hardest to ship.
There is no PyPI package.
The upstream GitHub release only publishes source archives and Windows zips.
ROS builds it from source through `uncrustify_vendor`.

Phase 1 (this iteration) mirrors how `polymath-go` handles the Go toolchain:
`ros-uncrustify` looks for `uncrustify` on `PATH`, fails with an install hint if absent, and picks `ament_code_style_0_78.cfg` or `ament_code_style_0_72.cfg` from `uncrustify --version` exactly as `ament_uncrustify` does.
Ubuntu 24.04 ships 0.78.1 and Ubuntu 22.04 ships 0.72.0, so both configs matter.

Phase 2 options, for follow-up:

1. **Host prebuilt binaries** in this repo's GitHub releases and download them on first use with pinned checksums, the `golangci-lint` pattern.
   We control the build, users get a consistent 0.78.1 everywhere.
   Cost: a release job that cross-compiles for linux/amd64, linux/arm64, and macOS.
2. **Build from source into the hook virtualenv** on first use.
   Needs cmake, a C++ compiler, and a Python 3 interpreter, and no third-party libraries.
   Measured on 0.78.1 during implementation: 43 CPU-seconds, about 12 s on four cores, for a 1.4 MiB stripped binary that links only libstdc++ and libc.
   Cheap enough to be a real fallback where no prebuilt binary exists.
3. **Publish a wheel** the way `clang-format`, `clang-tidy`, and `cppcheck` wheels are built with scikit-build-core.
   Cleanest for consumers.
   Most upfront work and a PyPI project to maintain.

Recommendation: option 1, because the download-and-verify code already exists in polymath_code_standard.

### clang-tidy: needs a compilation database

`ament_clang_tidy` searches for `compile_commands.json` files and runs clang-tidy against each package's build directory.
A pre-commit hook has no build tree.

The `clang-tidy` PyPI wheel solves distribution.
The hook takes a `--build-dir` argument pointing at a colcon build directory and passes `-p` through.
If the compilation database is missing, the hook fails with a clear message rather than pretending to check.
This is genuinely opt-in and will not run on a fresh checkout.
Deferred to a later phase.

### cppcheck: ament refuses the version everyone has

`ament_cppcheck` exits with a skip on cppcheck 1.88 and every 2.x release unless `AMENT_CPPCHECK_ALLOW_SLOW_VERSIONS` is set, because 2.x is slow on whole packages.
Ubuntu 22.04 and 24.04 both ship 2.x, so on current ROS 2 distributions `ament_lint_common` effectively skips cppcheck.

The `cppcheck` wheel provides 2.17.
Running on the handful of staged files in a commit is fast, so `ros-cppcheck` runs unconditionally and matches ament's flags: `-f --inline-suppr -q -rp --suppress=internalAstError --suppress=unknownMacro`.
Consumers should expect findings that `colcon test` never showed them.

### copyright: header insertion is destructive

`ament_copyright --add-missing NAME LICENSE` rewrites files.
The hook exposes it as `args: [--add-missing, "Name", apache2]` and leaves the default mode check-only, matching ament.

### mypy: whole-program tool run per file

mypy on a subset of files still type-checks their imports, so results depend on what is installed in the hook virtualenv, not the consumer's environment.
`ament_mypy.ini` sets `ignore_missing_imports = True`, which keeps this tolerable.
Same caveat polymath_code_standard documents for `tsc`.

### PC-lint: not translated

Proprietary, requires a license, not part of any ROS 2 default.
Out of scope.

## Repository layout

```
ros_code_standard/
  .pre-commit-hooks.yaml            hook definitions, one per linter
  .pre-commit-config.yaml           dev config, repo: .
  pyproject.toml                    package, pinned tool versions, package data
  ros_code_standard/
    checker.py                      CheckerGroup, Result, run() -- from polymath_code_standard
    runner.py                       argparse dispatcher -- from polymath_code_standard
    checkers/
      copyright.py                  ament_copyright passthrough
      cppcheck.py
      cpplint/__init__.py           ament_cpplint passthrough
      flake8/__init__.py, ament_flake8.ini
      lint_cmake.py                 ament_lint_cmake passthrough
      pep257.py
      uncrustify/__init__.py, ament_code_style_0_72.cfg, ament_code_style_0_78.cfg
      xmllint/__init__.py, package_format2.xsd, package_format3.xsd
      clang_format/__init__.py, clang-format
      clang_tidy.py                 (later phase)
      mypy/__init__.py, ament_mypy.ini, ament_mypy_strict.toml
      pycodestyle/__init__.py, ament_pycodestyle.ini
      pyflakes.py
  test_files/                       a minimal ROS 2 package that passes every hook
  tests/                            pytest per checker
  docs/DESIGN.md, docs/PLAN.md
```

## Migration for a consuming package

`package.xml`, remove:

```xml
<test_depend>ament_lint_auto</test_depend>
<test_depend>ament_lint_common</test_depend>
```

`CMakeLists.txt`, remove:

```cmake
if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()
```

Add `.pre-commit-config.yaml` with the hooks that match the removed test dependencies, run `pre-commit run --all-files`, and commit the reformatting.

## Non-goals

- Reproducing xUnit output or CTest labels.
- Supporting `AMENT_IGNORE`.
- Byte-for-byte parity with the Python tool versions in a specific ROS distribution.
  flake8, pydocstyle, pycodestyle, pyflakes, and mypy are pinned to current PyPI releases with ament's configs.
  The ament-owned tools (copyright, cpplint, lint_cmake) are pinned to an `ament_lint` release and match it exactly.
