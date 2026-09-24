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

"""
XML well-formedness and schema validation, the ament_xmllint check.

ament_xmllint shells out to the libxml2 `xmllint` binary and downloads every
referenced schema over the network.
This checker uses lxml, which is a Python dependency rather than a system one,
and it resolves the ROS package format schemas to copies bundled beside this
module so that validating a `package.xml` works offline.

Validation is driven by the document itself, exactly as ament does it: an
`xml-model` processing instruction selects XML Schema or RelaxNG by its
`schematypens`, and `xsi:noNamespaceSchemaLocation` on the root element selects
XML Schema.
Schematron is not supported.
"""

import argparse
import functools
import importlib.resources
import os
from pathlib import Path
from urllib.parse import urlsplit

from lxml import etree

from ros_code_standard.checker import check_group, CheckerGroup, Result

SCHEMA_DIR = importlib.resources.files(__package__)

XSD_NS = 'http://www.w3.org/2001/XMLSchema'
RELAXNG_NS = 'http://relaxng.org/ns/structure/1.0'
SCHEMATRON_NS = 'http://purl.oclc.org/dsdl/schematron'
XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'

# The ROS package format schemas ship with this package so that package.xml
# validation needs no network. Any other URL is fetched by lxml as written.
BUNDLED_SCHEMAS = {
    'http://download.ros.org/schema/package_format2.xsd': 'package_format2.xsd',
    'http://download.ros.org/schema/package_format3.xsd': 'package_format3.xsd',
}


def _resolve(href: str, base_dir: Path) -> str:
    """
    Map a schema reference onto something lxml can parse.

    A bundled URL becomes the local copy, any other URL is left alone, and a
    relative path is taken relative to the document that references it, which is
    what ament gets by running xmllint from the document's directory.
    """
    bundled = BUNDLED_SCHEMAS.get(href)
    if bundled:
        return str(SCHEMA_DIR / bundled)
    if urlsplit(href).scheme:
        return href
    return os.fspath(base_dir / href)


@functools.cache
def _load_xsd(source: str) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(source))


@functools.cache
def _load_relaxng(source: str) -> etree.RelaxNG:
    return etree.RelaxNG(etree.parse(source))


_LOADERS = {XSD_NS: _load_xsd, RELAXNG_NS: _load_relaxng}


def _schema_refs(doc: etree._ElementTree) -> list[tuple[str, str]]:
    """Return the (schematypens, href) schema references the document declares."""
    refs = []
    node = doc.getroot().getprevious()
    while node is not None:
        if isinstance(node, etree._ProcessingInstruction) and node.target == 'xml-model':
            try:
                pi = etree.fromstring(f'<pi {node.text}/>')
            except etree.XMLSyntaxError:
                node = node.getprevious()
                continue
            href = pi.get('href')
            schematypens = pi.get('schematypens')
            if href and schematypens:
                refs.append((schematypens, href))
        node = node.getprevious()
    location = doc.getroot().get(f'{{{XSI_NS}}}noNamespaceSchemaLocation')
    if location:
        refs.append((XSD_NS, location))
    return refs


def validate(filepath: str) -> list[str]:
    """Check well-formedness and every declared schema, returning error strings."""
    try:
        doc = etree.parse(filepath)
    except etree.XMLSyntaxError as exc:
        return [str(entry) for entry in exc.error_log]
    except OSError as exc:
        return [str(exc)]

    base_dir = Path(filepath).resolve().parent
    errors: list[str] = []
    for schematypens, href in _schema_refs(doc):
        if schematypens == SCHEMATRON_NS:
            # ament passes --schematron to xmllint here. lxml's ISO Schematron
            # support does not cover the same dialect, so the reference is ignored.
            continue
        loader = _LOADERS.get(schematypens)
        if loader is None:
            continue
        try:
            schema = loader(_resolve(href, base_dir))
        except Exception as exc:
            errors.append(f'failed to load schema {href}: {exc}')
            continue
        if not schema.validate(doc):
            errors.extend(str(entry) for entry in schema.error_log)
    return errors


@check_group
class XmllintGroup(CheckerGroup):

    name = 'xmllint'

    def run(self, args: argparse.Namespace) -> list[Result]:
        if not args.files:
            return [Result(name='xmllint', passed=True, skipped=True)]

        errors: list[str] = []
        for filepath in args.files:
            errors.extend(f'{filepath}: {msg}' for msg in validate(filepath))
        return [Result(name='xmllint', passed=not errors, output='\n'.join(errors))]
