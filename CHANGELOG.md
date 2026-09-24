# Changelog

All notable changes to this project are documented in this file.
Releases follow semantic versioning as described in [DEVELOPING.md](./DEVELOPING.md).

## Unreleased

### Changed

- `ros-uncrustify` runs a bundled uncrustify binary instead of whatever is on `PATH`.
  The `ros-uncrustify-bin` wheel, built from `uncrustify_wheel/` by the `Build uncrustify wheels` workflow and published to this repo's releases, carries both 0.78.1 (rolling, jazzy) and 0.72.0 (humble) for Linux x86_64 and aarch64 and macOS x86_64 and arm64.
  `--uncrustify-version` selects one, default 0.78.1.
  `--system-uncrustify` restores the `PATH` lookup for other platforms.
  Motivation: Ubuntu 22.04's apt uncrustify is 0.72.0, and with the 0_72 config it reformats files that rolling's pinned 0.78.1 accepts, so the distro binary cannot give parity.

### Pending

- The root `pyproject.toml` does not yet depend on the wheel. That wiring waits for the first `uncrustify-bin-v0.1.0` release to exist (plan task 4.4).

## 0.1.1

### Fixed

- `ros-cpplint` and `ros-lint-cmake` run `ament_cpplint` and `ament_lint_cmake` themselves instead of PyPI cpplint 2.0 and cmakelint 1.4.3 with ament's flags.
  Both ament packages vendor modified forks, and cpplint 2.0 reported `build/c++17`, `whitespace/newline`, and wider include-what-you-use findings on `ros2/rcpputils`, which is green under ament_lint on rolling.
  Findings now match `colcon test` exactly.
- README migration section maps `ament_<tool>(EXCLUDE ...)`, `LANGUAGE`, `FILTERS`, and `MAX_LINE_LENGTH` onto hook fields, with rcpputils as the worked example.

## 0.1.0

Initial release: the `ament_lint` linters as pre-commit hooks, one hook per `ament_cmake_<tool>` package.

### Added

- The `ament_lint_common` set: `ros-copyright`, `ros-cppcheck`, `ros-cpplint`, `ros-flake8`, `ros-lint-cmake`, `ros-pep257`, `ros-uncrustify`, `ros-xmllint`.
- The optional linters: `ros-clang-format`, `ros-clang-tidy` (experimental, needs a build directory), `ros-mypy`, `ros-pycodestyle`, `ros-pyflakes`.
- Every ament configuration file is bundled and passed by absolute path, so nothing is written into the consuming repository.
- `ros-copyright`, `ros-cpplint`, and `ros-lint-cmake` run `ament_copyright`, `ament_cpplint`, and `ament_lint_cmake` themselves, installed from the `ament_lint` repository at 0.21.2, so their findings match `colcon test` exactly.

### Differences from ament_lint

- Formatters (`ros-uncrustify`, `ros-clang-format`, `ros-copyright --add-missing`) rewrite files and fail so they are re-staged.
- `ros-cppcheck` runs on cppcheck 2.x, which `ament_cppcheck` skips.
- `ros-mypy` passes `--explicit-package-bases` so multi-package workspaces do not fail on duplicate `setup.py` modules.
- `ros-uncrustify` needs `uncrustify` on `PATH`; there is no pip package.
- `AMENT_IGNORE` is not honored, and no xUnit files are produced.
