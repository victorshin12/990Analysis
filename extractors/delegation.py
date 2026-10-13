"""Management-delegation extractor (Part VI, Section A, Line 3).

One row per filing. This is the original measure: the Yes/No indicator plus,
when Yes, the core-form Schedule O narrative. Schedule H "Part VI, Line 3"
(patient education) is excluded.
"""

import re
from pathlib import Path

import pandas as pd

from extractors.xml_utils import (
    element_text,
    first_text,
    iter_schedule_o,
    parse_filename,
    parse_xml,
    yes_no,
)
from paths import ACQUIRE, EXTRACT, XML_DIR


LOG_FILE = ACQUIRE / "xml_download_log.csv"
OUTPUT_FILE = EXTRACT / "delegation_results.csv"

KEY = "delegation"
GROUP = "Management delegation"
DESCRIPTION = "Part VI Section A Line 3 indicator, plus Schedule O text when Yes."

COLUMNS = [
    "ein",
    "tax_period",
    "object_id",
    "xml_file",
    "organization_name",
    "tax_year",
    "delegation_indicator",
    "line3_reference",
    "schedule_o_line3_text",
    "text_status",
]


def is_core_line3(ref):
    """True only for core Form 990 Part VI, Section A, Line 3."""
    folded = re.sub(r"\s+", " ", ref.upper())
    if "SCHEDULE H" in folded or "SCH H" in folded or "PATIENT EDUCATION" in folded or "PART III" in folded:
        return False
    if "SECTION A" in folded and "LINE 3" in folded:
        return True
    if "PART VI" in folded and ("LINE 3" in folded or "QUESTION 3" in folded):
        return True
    return False


def extract_file(xml_path):
    ein, tax_period, object_id = parse_filename(xml_path)
    record = {
        "ein": ein,
        "tax_period": tax_period,
        "object_id": object_id,
        "xml_file": Path(xml_path).name,
        "organization_name": "",
        "tax_year": "",
        "delegation_indicator": "",
        "line3_reference": "",
        "schedule_o_line3_text": "",
        "text_status": "",
    }

    try:
        root = parse_xml(xml_path)
    except Exception:
        record["text_status"] = "xml_parse_error"
        return record

    record["organization_name"] = first_text(
        root, ["BusinessNameLine1Txt", "BusinessNameLine1", "Name"]
    )
    record["tax_year"] = first_text(root, ["TaxYr"]) or (tax_period[:4] if tax_period else "")

    record["delegation_indicator"] = yes_no(element_text(root, "DelegationOfMgmtDutiesInd"))

    if record["delegation_indicator"] == "Yes":
        refs, texts = [], []
        for ref, text in iter_schedule_o(root):
            if is_core_line3(ref) and text:
                refs.append(ref)
                texts.append(text)
        if texts:
            record["line3_reference"] = " | ".join(dict.fromkeys(refs))
            record["schedule_o_line3_text"] = " || ".join(dict.fromkeys(texts))
            record["text_status"] = "text_found"
        else:
            record["text_status"] = "yes_but_no_line3_text"

    return record


def attach_download_log(frame):
    if not LOG_FILE.exists():
        return frame
    log = pd.read_csv(LOG_FILE, dtype=str)
    columns = ["object_id", "taxpayer_name", "hospital_names", "states", "medicare_provider_numbers"]
    columns = [column for column in columns if column in log.columns]
    return frame.merge(log[columns].drop_duplicates("object_id"), on="object_id", how="left")


def main(xml_dir=None, output_file=None):
    xml_dir = Path(xml_dir) if xml_dir else XML_DIR
    output_file = Path(output_file) if output_file else OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)
    xml_files = sorted(xml_dir.glob("*.xml"))
    print("XML files to process:", len(xml_files))

    rows = []
    for index, path in enumerate(xml_files, 1):
        rows.append(extract_file(path))
        if index % 2500 == 0:
            print("  processed", index)

    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame = attach_download_log(frame)
    frame.to_csv(output_file, index=False)

    print()
    print("Group:", GROUP)
    print("Done. Saved:", output_file)
    print("Total filings:", len(frame))
    print()
    print("delegation_indicator counts:")
    print(frame["delegation_indicator"].replace("", "(absent)").value_counts().to_string())
    yes = frame[frame["delegation_indicator"] == "Yes"]
    print()
    print("Yes filings:", len(yes))
    print("  with Schedule O text:", (yes["text_status"] == "text_found").sum())
    print("  Yes but no Line 3 text:", (yes["text_status"] == "yes_but_no_line3_text").sum())
    print("Unique EINs with >=1 Yes:", yes["ein"].nunique())
    return frame
