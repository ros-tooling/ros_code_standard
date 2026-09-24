# Development workflows

Design and status live in [docs/DESIGN.md](./docs/DESIGN.md) and [docs/PLAN.md](./docs/PLAN.md).

## Environment

```shell
uv sync
uv run pytest
```

`ros-uncrustify` needs `uncrustify` on `PATH`.
Its tests are marked `external` and skip when it is missing.
Run `uv run pytest -m 'not external'` to leave them out on purpose.

## Running pre-commit

`.pre-commit-config.yaml` in this repo is a `repo: .` dev config that runs the hooks directly from the working tree.
pre-commit caches `HEAD`, so uncommitted changes are not what gets run.

Run `just verify` after `commit --no-verify` to use your latest HEAD instead of any cached version.

pre-commit keys its cache on the literal `repo: .` and `rev: HEAD` strings, so every repo that uses this dev-config pattern (polymath_code_standard does too) shares one cache slot.
If you see `ros-copyright is not present in repository .`, that slot holds a different repo.
`just verify` runs `pre-commit clean` first, which fixes it, or set `PRE_COMMIT_HOME` to a scratch directory.

## Style

This repo's own Python is checked by its own hooks, so it follows the ROS 2 Python style rather than the Polymath one:
99 columns, Google import order (names inside a `from x import a, b` are sorted case-insensitively too), single quotes, class bodies start with a blank line, multi-line docstrings start on the second line, and every non-empty file carries the full Apache header that `ament_copyright` recognizes.
SPDX two-line headers are not recognized.
`ros-pycodestyle` also runs here with ament's cleared ignore list, so a line may not break before or after a binary operator (W503 and W504 both fire).

`runner.py` imports every module under `checkers/` eagerly.
A syntax or import error in one checker breaks every hook, so run `uv run ros_code_standard --help` after editing a checker.

## Adding a checker

1. Add a module or subpackage under `ros_code_standard/checkers/`.
   A subpackage is for checkers that ship a config file beside the code.
2. Subclass `CheckerGroup`, set `name`, implement `run()`, and decorate with `@check_group`.
   The runner discovers it by import.
3. Declare any config files in `[tool.setuptools.package-data]` in `pyproject.toml`.
4. Add a hook entry to `.pre-commit-hooks.yaml` and to the dev `.pre-commit-config.yaml`.
5. Add a `tests/test_<name>.py` and any fixtures under `test_files/`.
6. Document the hook in the README hook reference.

## Releases

Releases follow semantic versioning:

- **Patch**: bugfixes or nonfunctional dependency updates, must not require any manual changes from users
- **Minor**: new checks, formatting changes, or new linting checks. May require fixing existing code.
- **Major**: removed checks or other breaking changes to existing API

To bump the version, use `just bump`.
It updates `pyproject.toml` and syncs the README pin in one step:

```shell
just bump minor   # or major / patch
```

Then add a `## <version>` section to `CHANGELOG.md` describing the release.

CI fails PRs where the README pin or the changelog section is missing for the version in `pyproject.toml`.
On merge to main, CI pushes the tag and publishes a GitHub release whose notes are that changelog section.
