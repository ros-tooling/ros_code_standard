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

"""Tests for the xmllint checker: well-formedness, XML Schema, and RelaxNG."""

import argparse
from pathlib import Path

from ros_code_standard.checkers.xmllint import (
    _resolve,
    BUNDLED_SCHEMAS,
    SCHEMA_DIR,
    validate,
    XmllintGroup,
)
from ros_code_standard.runner import main

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_FILES = REPO_ROOT / 'test_files'

FORMAT3_PACKAGE_XML = TEST_FILES / 'cpp_pkg' / 'package.xml'
FORMAT2_PACKAGE_XML = TEST_FILES / 'xml' / 'package_format2.xml'

MODEL_PI = (
    '<?xml-model href="http://download.ros.org/schema/package_format3.xsd" '
    'schematypens="http://www.w3.org/2001/XMLSchema"?>'
)

MINIMAL_PACKAGE = """<?xml version="1.0"?>
{model}
<package format="3">
  <name>demo</name>
  <version>0.1.0</version>
  <description>Demo.</description>
  <maintainer email="nobody@example.com">Nobody</maintainer>
  <license>Apache-2.0</license>
{extra}</package>
"""

LOCAL_XSD = """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="root">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="value" type="xs:string"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

LOCAL_RNG = """<?xml version="1.0"?>
<element name="root" xmlns="http://relaxng.org/ns/structure/1.0">
  <element name="value">
    <text/>
  </element>
</element>
"""


def _package(extra: str = '') -> str:
    return MINIMAL_PACKAGE.format(model=MODEL_PI, extra=extra)


# --- bundled schemas ---


def test_every_bundled_schema_url_resolves_to_a_file_in_the_package():
    for url, filename in BUNDLED_SCHEMAS.items():
        resolved = Path(_resolve(url, Path('/nonexistent')))
        assert resolved == Path(SCHEMA_DIR) / filename
        assert resolved.is_file()


def test_both_package_format_urls_are_bundled():
    assert set(BUNDLED_SCHEMAS) == {
        'http://download.ros.org/schema/package_format2.xsd',
        'http://download.ros.org/schema/package_format3.xsd',
    }


def test_remote_url_is_left_alone():
    url = 'http://example.com/other.xsd'
    assert _resolve(url, Path('/tmp')) == url


def test_relative_href_resolves_next_to_the_document():
    assert _resolve('schema/local.xsd', Path('/pkg')) == '/pkg/schema/local.xsd'


# --- the repository fixtures ---


def test_format3_package_xml_fixture_passes():
    assert main(['xmllint', str(FORMAT3_PACKAGE_XML)]) == 0


def test_format2_package_xml_fixture_passes():
    assert main(['xmllint', str(FORMAT2_PACKAGE_XML)]) == 0


def test_fixture_validation_used_the_bundled_schema_not_the_network(monkeypatch):
    """A document is validated with no network access because the schema is local."""
    def refuse(*args, **kwargs):
        raise AssertionError('the checker tried to open a network connection')

    monkeypatch.setattr('socket.socket', refuse)
    monkeypatch.setattr('socket.create_connection', refuse)
    assert validate(str(FORMAT3_PACKAGE_XML)) == []


# --- failures ---


def test_unknown_element_fails(tmp_path):
    path = tmp_path / 'package.xml'
    path.write_text(_package('  <not_a_manifest_tag>x</not_a_manifest_tag>\n'))
    errors = validate(str(path))
    assert errors
    assert any('not_a_manifest_tag' in e for e in errors)
    assert main(['xmllint', str(path)]) == 1


def test_missing_required_element_fails(tmp_path):
    path = tmp_path / 'package.xml'
    path.write_text(
        '<?xml version="1.0"?>\n' + MODEL_PI + '\n<package format="3">\n'
        '  <name>demo</name>\n</package>\n'
    )
    assert main(['xmllint', str(path)]) == 1


def test_malformed_xml_fails(tmp_path):
    path = tmp_path / 'broken.xml'
    path.write_text('<root><unclosed></root>\n')
    errors = validate(str(path))
    assert errors
    assert main(['xmllint', str(path)]) == 1


def test_unreadable_file_fails(tmp_path):
    assert main(['xmllint', str(tmp_path / 'absent.xml')]) == 1


def test_failure_output_names_the_file(tmp_path):
    path = tmp_path / 'broken.xml'
    path.write_text('<root>\n')
    result = XmllintGroup().run(argparse.Namespace(files=[str(path)]))[0]
    assert not result.passed
    assert str(path) in result.output


# --- xsi:noNamespaceSchemaLocation ---


def test_no_namespace_schema_location_is_honored(tmp_path):
    (tmp_path / 'local.xsd').write_text(LOCAL_XSD)
    xsi = 'http://www.w3.org/2001/XMLSchema-instance'
    good = tmp_path / 'good.xml'
    good.write_text(
        f'<root xmlns:xsi="{xsi}" xsi:noNamespaceSchemaLocation="local.xsd">'
        '<value>ok</value></root>\n'
    )
    bad = tmp_path / 'bad.xml'
    bad.write_text(
        f'<root xmlns:xsi="{xsi}" xsi:noNamespaceSchemaLocation="local.xsd">'
        '<wrong>no</wrong></root>\n'
    )
    assert main(['xmllint', str(good)]) == 0
    assert main(['xmllint', str(bad)]) == 1


# --- RelaxNG ---


def test_relaxng_valid_document_passes(tmp_path):
    (tmp_path / 'local.rng').write_text(LOCAL_RNG)
    path = tmp_path / 'good.xml'
    path.write_text(
        '<?xml-model href="local.rng" schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        '<root><value>ok</value></root>\n'
    )
    assert main(['xmllint', str(path)]) == 0


def test_relaxng_invalid_document_fails(tmp_path):
    (tmp_path / 'local.rng').write_text(LOCAL_RNG)
    path = tmp_path / 'bad.xml'
    path.write_text(
        '<?xml-model href="local.rng" schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
        '<root><wrong>no</wrong></root>\n'
    )
    assert main(['xmllint', str(path)]) == 1


def test_missing_schema_is_reported_not_crashed(tmp_path):
    path = tmp_path / 'doc.xml'
    path.write_text(
        '<?xml-model href="absent.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>\n'
        '<root/>\n'
    )
    errors = validate(str(path))
    assert any('failed to load schema absent.xsd' in e for e in errors)


# --- references that carry no validation ---


def test_schematron_reference_is_ignored(tmp_path):
    path = tmp_path / 'doc.xml'
    path.write_text(
        '<?xml-model href="rules.sch" schematypens="http://purl.oclc.org/dsdl/schematron"?>\n'
        '<root/>\n'
    )
    assert validate(str(path)) == []


def test_document_without_a_schema_reference_only_needs_to_be_well_formed(tmp_path):
    path = tmp_path / 'doc.xml'
    path.write_text('<root><anything/></root>\n')
    assert main(['xmllint', str(path)]) == 0


def test_no_files_is_a_skip():
    assert main(['xmllint']) == 0
