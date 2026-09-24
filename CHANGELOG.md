# Changelog

All notable changes to this project are documented in this file.
Releases follow semantic versioning as described in [DEVELOPING.md](./DEVELOPING.md).

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
