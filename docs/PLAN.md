# Implementation plan

Companion to [DESIGN.md](./DESIGN.md).
This file is the living status board.
Update the status column as tasks are planned, dispatched, and completed.

Status values: `todo`, `dispatched`, `review`, `done`, `deferred`.

## Phase 0: scaffold

Done by hand before any parallel work so every task builds on the same base.

| # | Task | Status |
|---|---|---|
| 0.1 | Copy `checker.py`, `runner.py`, package skeleton from polymath_code_standard, rename to `ros_code_standard` | done |
| 0.2 | `pyproject.toml` with every tool dependency pinned, package data declared for each config subpackage | done |
| 0.3 | `.pre-commit-hooks.yaml` with all thirteen hook ids, `.pre-commit-config.yaml` dev config | done |
| 0.4 | Repo hygiene: LICENSE, `.gitignore`, `.python-version`, `.envrc`, `Justfile`, CI workflow, DEVELOPING.md, CHANGELOG.md, README skeleton | done |
| 0.5 | `test_files/` minimal ROS 2 package layout to be filled in by each task | done |

## Phase 1: checkers

Each task owns the files listed and nothing else, so they run in parallel without conflicts.
Every task adds a `tests/test_<name>.py` and any `test_files/` it needs, and reports the README hook-reference text for its hooks.

| # | Task | Owns | Status |
|---|---|---|---|
| 1.1 | Python linters: `ros-flake8`, `ros-pep257`, `ros-pycodestyle`, `ros-pyflakes`, `ros-mypy` | `checkers/flake8/`, `checkers/pep257.py`, `checkers/pycodestyle/`, `checkers/pyflakes.py`, `checkers/mypy/`, `test_files/python/`, `tests/test_python_linters.py` | done |
| 1.2 | C++ static checks: `ros-cpplint` (header guard patch, root grouping), `ros-cppcheck`, `ros-clang-format` | `checkers/cpplint/`, `checkers/cppcheck.py`, `checkers/clang_format/`, `test_files/cpp_pkg/`, `tests/test_cpplint.py`, `tests/test_cppcheck.py`, `tests/test_clang_format.py` | done |
| 1.3 | `ros-uncrustify`: PATH lookup, version to config selection, fix-then-fail | `checkers/uncrustify/`, `tests/test_uncrustify.py` | done |
| 1.4 | Package-level checks: `ros-copyright` (ament_copyright passthrough), `ros-lint-cmake`, `ros-xmllint` | `checkers/copyright.py`, `checkers/lint_cmake.py`, `checkers/xmllint/`, `test_files/cpp_pkg/package.xml`, `test_files/cpp_pkg/CMakeLists.txt`, `tests/test_copyright.py`, `tests/test_lint_cmake.py`, `tests/test_xmllint.py` | done |

## Phase 2: integration

| # | Task | Status |
|---|---|---|
| 2.1 | Review each Phase 1 result for clarity, style, correctness; re-dispatch fixes | done |
| 2.2 | `uv lock`, `uv run pytest`, `pre-commit run --all-files` against this repo green | done |
| 2.3 | README hook reference assembled from task reports, `ament_lint_common` equivalence block, migration section | done |
| 2.4 | CHANGELOG `0.1.0` entry | done |

## Phase 2b: parity fixes

Triggered by running the hooks on `ros2/rcpputils`, which is green under `ament_lint_common` on rolling.

| # | Task | Owns | Status |
|---|---|---|---|
| 2.5 | Swap PyPI `cpplint` and `cmakelint` for `ament_cpplint` and `ament_lint_cmake` from the ament_lint git repo | `pyproject.toml`, `uv.lock` | done |
| 2.6 | Rewrite `ros-cpplint` as an `ament_cpplint` wrapper | `checkers/cpplint/`, `tests/test_cpplint.py` | done |
| 2.7 | Rewrite `ros-lint-cmake` as an `ament_lint_cmake` wrapper | `checkers/lint_cmake.py`, `tests/test_lint_cmake.py` | done |
| 2.8 | DESIGN.md parity principle, README migration mapping for `EXCLUDE` and `LANGUAGE`, CHANGELOG | docs | done |
| 2.9 | Re-verify: `uv run pytest`, `pre-commit run --all-files` on this repo, hooks over rcpputils clean except the vendored header | | done |

## Phase 4: prebuilt uncrustify wheels

Decision (2026-09-24): apt uncrustify does not match the ROS distribution's pin.
Ubuntu 22.04 ships 0.72.0, rolling and jazzy build 0.78.1 through `uncrustify_vendor`, and the two produce different output on rcpputils.
Building from source on the consumer's machine was rejected.
Instead, a wheel project in this repo bundles prebuilt uncrustify binaries, a GitHub Action builds it for each platform whenever the project changes and publishes the wheels to a GitHub release, and the hook depends on those wheels by direct URL with platform markers.

Contract shared by the three tasks:

- Project directory `uncrustify_wheel/`, distribution `ros-uncrustify-bin`, import package `ros_uncrustify_bin`, version in `uncrustify_wheel/pyproject.toml`, starting at `0.1.0`.
- Each wheel is tagged `py3-none-<platform>` and holds both `ros_uncrustify_bin/bin/uncrustify-0.78.1` and `ros_uncrustify_bin/bin/uncrustify-0.72.0`.
  Source pins: `uncrustify-0.78.1.tar.gz` sha256 `ecaf4c0adca14c36dfffa30bc28e69865115ecd602c90eb16a8cddccb41caad2`, `uncrustify-0.72.0.tar.gz` sha256 `d6fff70bc7823fac4c77013055333b79a4839909094e8eee8a14ee8f1777374e`, both from `https://github.com/uncrustify/uncrustify/archive/refs/tags/`.
- Platforms: manylinux x86_64, manylinux aarch64, macOS x86_64, macOS arm64. Windows is out of scope.
- Python API: `VERSIONS = ('0.78.1', '0.72.0')`, `DEFAULT_VERSION = '0.78.1'`, `binary(version=DEFAULT_VERSION) -> pathlib.Path`, raising `ValueError` for an unknown version.
- Release tag `uncrustify-bin-v<version>` with the wheels and a `SHA256SUMS` file as assets.
- Hook: `--uncrustify-version {0.78.1,0.72.0}` (default 0.78.1) selects the bundled binary and the matching ament config; `--system-uncrustify` opts out to the PATH binary with version detection, the previous behavior.

| # | Task | Owns | Status |
|---|---|---|---|
| 4.1 | Wheel project: scikit-build-core, CMake ExternalProject for both versions with pinned hashes, static linking, cibuildwheel config, local build and manylinux verification | `uncrustify_wheel/**` | done |
| 4.2 | Release workflow: cibuildwheel matrix on push to main touching `uncrustify_wheel/**`, GitHub release upload | `.github/workflows/uncrustify-wheels.yml` | done |
| 4.3 | Hook rewrite: bundled binary by default, `--uncrustify-version`, `--system-uncrustify` | `checkers/uncrustify/`, `tests/test_uncrustify.py` | done |
| 4.4 | Wire `pyproject.toml` dependencies to the release URLs with platform markers, `uv lock`, drop apt uncrustify from CI | `pyproject.toml`, `uv.lock`, `.github/workflows/test.yml` | blocked until the first release exists |
| 4.5 | Docs: DESIGN uncrustify section, README prerequisites and `ros-uncrustify`, DEVELOPING release flow, CHANGELOG | docs | done |

### Task 4.4 procedure

The organization is `ros-tooling`, from the README URL commit.
After the first push to `main` runs `Build uncrustify wheels` and the `uncrustify-bin-v0.1.0` release exists:

1. Copy the exact wheel filenames from the workflow's "Wheel download URLs" step summary.
   Expected, from the local cibuildwheel run (auditwheel puts the legacy alias first):
   `ros_uncrustify_bin-0.1.0-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`,
   `ros_uncrustify_bin-0.1.0-py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64.whl`,
   `ros_uncrustify_bin-0.1.0-py3-none-macosx_11_0_x86_64.whl`,
   `ros_uncrustify_bin-0.1.0-py3-none-macosx_11_0_arm64.whl`.
2. Add to `[project] dependencies` in the root `pyproject.toml`, one line per platform, with the base
   `https://github.com/ros-tooling/ros_code_standard/releases/download/uncrustify-bin-v0.1.0/`:

   ```toml
   "ros-uncrustify-bin @ <base><linux x86_64 wheel> ; sys_platform == 'linux' and platform_machine == 'x86_64'",
   "ros-uncrustify-bin @ <base><linux aarch64 wheel> ; sys_platform == 'linux' and platform_machine == 'aarch64'",
   "ros-uncrustify-bin @ <base><macos x86_64 wheel> ; sys_platform == 'darwin' and platform_machine == 'x86_64'",
   "ros-uncrustify-bin @ <base><macos arm64 wheel> ; sys_platform == 'darwin' and platform_machine == 'arm64'",
   ```

3. `uv lock`, `uv sync`, then `uv run pytest -q` should report the uncrustify `external` tests running through the wheel (54 in `tests/test_uncrustify.py`, 0 skipped).
4. Remove `args: [--system-uncrustify]` from `.pre-commit-config.yaml` and the two `apt-get install uncrustify` steps from `.github/workflows/test.yml`.
5. Bump the package with `just bump minor`, move the Unreleased changelog section under the new version, commit.

## Phase 3: deferred

| # | Task | Status |
|---|---|---|
| 3.1 | `ros-clang-tidy` with `--build-dir` argument | done |
| 3.2 | uncrustify prebuilt binary download with pinned checksums (design option 1) | superseded by Phase 4 |
| 3.3 | Publish to GitHub, first tagged release | deferred |

## Open questions

Decisions the implementation made that deserve a second look, collected from the task reports.

1. `ros-flake8` and `ros-pycodestyle` disagree by design: `ament_flake8.ini` uses `extend-ignore` so flake8 keeps its default ignore list, while `ament_pycodestyle.ini` clears it.
   W503, W504, E226 and E704 pass flake8 and fail pycodestyle.
   This is ament's real behavior; changing `extend-ignore` to `ignore` would align them and diverge from ROS 2.
2. `ros-mypy` always passes `--explicit-package-bases`, otherwise two staged packages with a `setup.py` each abort mypy with a duplicate module error.
   It slightly weakens import resolution for packages rooted in a subdirectory.
3. `ros-copyright` appends `LICENSE` and `CONTRIBUTING.md` only when they exist.
   ament in directory mode fails when they are missing.
   The hook also does not run on commits that stage no source files, so `always_run: true` may be wanted.
4. `ros-clang-tidy` fails on any diagnostic because clang-tidy exits 0 for warnings, matching ament's report-based behavior rather than the exit code.
   No default `--header-filter`, so headers are unchecked unless asked.
   The wheel's clang-tidy picks the newest GCC on the machine for libstdc++ and can need `--extra-arg=--gcc-install-dir=...`.
5. `ros-uncrustify`'s `--check` gate is verified on both 0.78.1 and 0.72.0.
   A `.h` file is parsed as C, as in ament.
   `--uncrustify-version` is per hook; if other hooks ever grow distribution-dependent behavior, a shared `--ros-distro` argument would be the better shape, and changing it later is a breaking argument change.
6. `ros-uncrustify` and `ros-clang-format` both pass on the fixtures today, but their configs conflict on short function bodies and constructor initializer lists.
   The README says to pick one.
7. List-valued hook arguments are comma separated (`--filters=-a,-b`, `--libraries a,b`, `--add-ignore D1,D2`) rather than ament's space separated form, because pre-commit appends file names after the args.
8. The `clang-tidy` wheel is about 140 MB and is installed into every consumer's hook virtualenv, even for consumers that never enable `ros-clang-tidy`.
   Moving it to `additional_dependencies` on that one hook would cost the shared virtualenv.
9. cppcheck 2.17 runs where ament skipped 2.x.
   Consumers migrating should expect new cppcheck findings.
   cpplint and lint_cmake are ament's own and match exactly.
10. `ros-lint-cmake` reads `~/.cmakelintrc` because ament does.
   A hermetic standard would pass `--config=None`; deferred to the improve phase.

## Dispatch log

Newest first.

- 2026-09-24: Phase 4 tasks 4.1, 4.2, 4.3 complete. Local manylinux2014 wheel built and verified (1.8 MiB, glibc 2.14 floor, no libstdc++ dependency); the bundled 0.78.1 passes all 46 rcpputils C++ files and 0.72.0 reformats `thread_name.cpp`, reproducing the reported symptom. 188 tests pass with the real wheel installed. Task 4.4 blocked until the first release; procedure recorded above.
- 2026-09-24: apt uncrustify 0.72.0 on Ubuntu 22.04 reformats rcpputils files that 0.78.1 accepts. Phase 4 planned: prebuilt wheels built by GitHub Actions. Tasks 4.1, 4.2, 4.3 dispatched in parallel.
- 2026-09-24: Parity fixes complete. `ros-cpplint` and `ros-lint-cmake` are wrappers over `ament_cpplint` and `ament_lint_cmake`. 169 tests pass. All twelve dev hooks pass on this repo. The eight `ament_lint_common` hooks pass on a clone of ros2/rcpputils (64a437c) with the CMake `EXCLUDE` and `LANGUAGE` options translated to `exclude:` and `--language`, with no files modified.
- 2026-09-24: Parity check on ros2/rcpputils failed under cpplint 2.0.2 (build/c++17, whitespace/newline on `{return;}`, wider IWYU tables). ament's vendored cpplint and cmakelint confirmed to be modified forks. Dependencies swapped to `ament_cpplint` and `ament_lint_cmake` from git; checker rewrites dispatched to the original task owners.
- 2026-09-24: Phase 2 complete. Review found relative imports and a filename-swallowing `nargs='+'` in the C++ task, fixed by re-dispatch. Integrator fixed W503/W504, a D403, a mypy annotation, and a YAML anchor in the hook manifest that merged `types_or` into every hook and emptied `ros-xmllint`. `uv run pytest`: 168 passed. `pre-commit run --all-files` over the repo with uncrustify 0.78.1 on PATH: 12 hooks passed.
- 2026-09-24: Task 3.1 (clang-tidy) completed alongside Phase 1 and marked experimental.
- 2026-09-24: Phase 1 tasks 1.1, 1.2, 1.3, 1.4 and Phase 3 task 3.1 dispatched to Opus subagents in parallel.
- 2026-09-24: Phase 0 scaffold complete. Environment resolves with `uv lock`, all flake8 plugins load, core files pass the ament Python style and ament_copyright.
- 2026-09-24: DESIGN.md and PLAN.md written.
