"""Shared Form 990 XML helpers used by every extractor."""

import re
from pathlib import Path

from lxml import etree


YES_VALUES = {"1", "true", "x"}
NO_VALUES = {"0", "false"}


def local(element):
    """Local tag name, ignoring namespaces (and skipping comment nodes)."""
    return etree.QName(element).localname if isinstance(element.tag, str) else ""


def parse_xml(xml_path):
    return etree.parse(
        str(xml_path), etree.XMLParser(recover=True, huge_tree=True)
    ).getroot()


def first_element(scope, tag_name):
    if scope is None:
        return None
    for element in scope.iter():
        if local(element) == tag_name:
            return element
    return None


def element_text(scope, tag_name):
    """Text of the first matching tag, or None when the tag is absent."""
    element = first_element(scope, tag_name)
    if element is None:
        return None
    return (element.text or "").strip()


def first_text(scope, tag_names):
    for tag in tag_names:
        text = element_text(scope, tag)
        if text:
            return text
    return ""


def parse_filename(xml_path):
    """Pipeline filenames are EIN_TAXPERIOD_OBJECTID.xml."""
    parts = Path(xml_path).stem.split("_")
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
        return parts[0], parts[1], parts[2]
    return "", "", ""


def yes_no(raw):
    """Map an IRS boolean to Yes / No. Blank means the tag was absent or empty."""
    if raw is None:
        return ""
    value = raw.strip().lower()
    if value in YES_VALUES:
        return "Yes"
    if value in NO_VALUES:
        return "No"
    return ""


def filer_name(root):
    """Organization name from the Filer block, not a preparer or related org."""
    filer = first_element(root, "Filer")
    if filer is not None:
        name = first_text(filer, ["BusinessNameLine1Txt", "BusinessNameLine1"])
        if name:
            return name
    return first_text(root, ["BusinessNameLine1Txt", "BusinessNameLine1", "Name"])


def iter_schedule_o(root):
    """Yield (line reference, explanation) from the core-form Schedule O only."""
    schedule_o = first_element(root, "IRS990ScheduleO")
    if schedule_o is None:
        return
    for detail in schedule_o.iter():
        if local(detail) != "SupplementalInformationDetail":
            continue
        ref = "".join(
            (node.text or "")
            for node in detail.iter()
            if local(node) == "FormAndLineReferenceDesc"
        )
        text = " ".join(
            (node.text or "").strip()
            for node in detail.iter()
            if local(node) == "ExplanationTxt"
        )
        ref = re.sub(r"\s+", " ", ref).strip()
        text = re.sub(r"\s+", " ", text).strip()
        if ref or text:
            yield ref, text
