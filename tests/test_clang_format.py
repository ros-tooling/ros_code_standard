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

from pathlib import Path

from ros_code_standard.checkers.clang_format import CONFIG, RESTAGE_MESSAGE, run_clang_format
from ros_code_standard.runner import main

CPP_PKG = Path(__file__).parent.parent / 'test_files' / 'cpp_pkg'
HEADER = str(CPP_PKG / 'include' / 'cpp_pkg' / 'greeter.hpp')
SOURCE = str(CPP_PKG / 'src' / 'greeter.cpp')

MISFORMATTED = 'int main(){int   value=1;\nreturn value;}\n'


def test_bundled_config_is_package_data():
    assert Path(str(CONFIG)).is_file()


def test_fixture_package_passes():
    assert main(['clang_format', HEADER, SOURCE]) == 0


def test_misformatted_file_is_rewritten_and_fails(tmp_path):
    path = tmp_path / 'bad.cpp'
    path.write_text(MISFORMATTED)
    result = run_clang_format([str(path)])
    assert not result.passed
    assert result.output.endswith(RESTAGE_MESSAGE)
    assert path.read_text() != MISFORMATTED
    # The rewrite is what the ament style asks for, so a second pass is clean.
    assert run_clang_format([str(path)]).passed


def test_no_files_is_skipped():
    result = run_clang_format([])
    assert result.skipped
