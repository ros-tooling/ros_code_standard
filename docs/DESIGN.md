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
| `ament_cmake_cpplint` | cpplint (forked 1.5.5) | filter list, line length 100, header guard patch | yes | `cpplint` 2.0.x |
| `ament_cmake_flake8` | flake8 + 7 plugins | `ament_flake8.ini` | yes | all on PyPI |
| `ament_cmake_lint_cmake` | cmakelint (forked) | line length 140 | yes | `cmakelint` 1.4.3 |
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

Two ament forks carry behavior that the config alone does not:

- **cpplint header guards.**
  ament patches `GetHeaderGuardCPPVariable` so `include/pkg/foo.hpp` becomes `PKG__FOO_HPP_` (double underscore between path parts), and it groups files by the nearest `include`, `src`, or `test` ancestor to pass as `--root`.
  The `ros-cpplint` checker imports `cpplint`, applies the same patch, and does the same grouping.
  cpplint 2.0.x still exposes the same function, verified during design.
- **cmakelint filenames.**
  ament overrides `IsValidFile` so `.cmake.in` files are linted.
  Upstream cmakelint refuses them.
  The checker applies the same one-line override.

### Copyright reuses `ament_copyright` directly

`ament_copyright` is not a wrapper around another tool.
Its parser, its license header templates, and its `--add-missing` mode are the tool.
Reimplementing them would drift from the ROS 2 canon for no gain.

pip can install a setuptools package from a subdirectory of a git repo, and polymath_code_standard already depends on two packages that way.
Verified during design:

```
ament_copyright @ git+https://github.com/ament/ament_lint.git@0.21.2#subdirectory=ament_copyright
```

installs cleanly with its console script and license entry points intact.
It has no dependency on the `ament_lint` helper package.

The hook passes staged source files through to `ament_copyright`.
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
      cpplint/__init__.py           header guard patch, root grouping
      flake8/__init__.py, ament_flake8.ini
      lint_cmake.py
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
- Byte-for-byte parity with the linter versions in a specific ROS distribution.
  Tools are pinned to current PyPI releases, and the pins are the standard.
