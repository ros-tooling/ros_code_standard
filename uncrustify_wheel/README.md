# ros-uncrustify-bin

Prebuilt [uncrustify](https://github.com/uncrustify/uncrustify) binaries, packaged as a Python
wheel so the `ros-uncrustify` hook of
[ros_code_standard](https://github.com/polymathrobotics/ros_code_standard) gets the exact version
a ROS 2 distribution pins instead of whatever the operating system happens to ship.

uncrustify has no PyPI package and no upstream Linux release binary, and the versions differ in
what they accept: Ubuntu 22.04 ships 0.72.0, while rolling and jazzy build 0.78.1 through
`uncrustify_vendor`, and the two reformat the same ROS 2 sources differently.
Each wheel therefore carries both versions.

## What is in the wheel

```
ros_uncrustify_bin/__init__.py
ros_uncrustify_bin/bin/uncrustify-0.78.1
ros_uncrustify_bin/bin/uncrustify-0.72.0
```

The binaries are built from the pinned upstream source tarballs with their sha256 checked, in
`Release` mode, with the C++ runtime linked statically on Linux so the binary does not need the
build image's libstdc++.

## Python API

```python
import ros_uncrustify_bin

ros_uncrustify_bin.VERSIONS          # ('0.78.1', '0.72.0')
ros_uncrustify_bin.DEFAULT_VERSION   # '0.78.1'
ros_uncrustify_bin.binary()          # Path to the 0.78.1 executable
ros_uncrustify_bin.binary('0.72.0')  # Path to the 0.72.0 executable
```

`binary()` raises `ValueError` for a version this distribution does not build and
`FileNotFoundError` when the installed wheel does not carry the requested binary.

## Platforms

One wheel per platform, each tagged `py3-none-<platform>` because nothing here touches the Python
C API:

| Platform | Wheel tag |
|---|---|
| Linux x86\_64 | `py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64` |
| Linux aarch64 | `py3-none-manylinux2014_aarch64.manylinux_2_17_aarch64` |
| macOS x86\_64 | `py3-none-macosx_11_0_x86_64` |
| macOS arm64 | `py3-none-macosx_11_0_arm64` |

The manylinux2014 base gives a glibc 2.17 floor, which covers Ubuntu 22.04 and 24.04 and
everything newer.
Windows and musl are out of scope.

## Building locally

From this directory, for the platform you are on:

```sh
uv build --wheel
```

CMake downloads and builds both uncrustify versions, so the first build takes a few minutes.
To reproduce what CI produces, including the manylinux container and `auditwheel`:

```sh
uvx cibuildwheel --platform linux --archs x86_64 .
```

All cibuildwheel configuration lives in `pyproject.toml`, so the GitHub workflow only chooses the
runner and the architecture.

## Bumping an uncrustify version

1. Edit the version and its `UNCRUSTIFY_SHA256_<version>` in `CMakeLists.txt`, taking the checksum
   from `https://github.com/uncrustify/uncrustify/archive/refs/tags/uncrustify-<version>.tar.gz`.
2. Update `VERSIONS` and, if it moved, `DEFAULT_VERSION` in `src/ros_uncrustify_bin/__init__.py`,
   and the version asserted by `test-command` in `pyproject.toml`.
3. Raise `version` in `pyproject.toml` and `__version__` in `src/ros_uncrustify_bin/__init__.py`.
4. Make sure `ros_code_standard/checkers/uncrustify/` has an ament config for the new version and
   that the hook's `--uncrustify-version` choices list it.

## Releases

Pushing these changes to `main` runs the wheel workflow, which builds every platform and publishes
the wheels and a `SHA256SUMS` file to the GitHub release `uncrustify-bin-v<version>` of the
ros_code_standard repository.
The hook depends on those wheel URLs directly, with platform markers, so consumers never build
uncrustify themselves.
