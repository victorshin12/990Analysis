"""Governance & Management Measures extractor.

One row per filing. Reads the structured Part VI fields (Sections A and B)
from the core IRS990 form. Line 11b has no checkbox, so that column is the
core-form Schedule O narrative. Lines 10b and 16b are blank when the IRS
did not ask them (parent answer was not Yes).
"""

import re
from pathlib import Path

import pandas as pd

from extractors.xml_utils import (
    element_text,
    filer_name,
    first_element,
    first_text,
    iter_schedule_o,
    parse_filename,
    parse_xml,
    yes_no,
)
from paths import EXTRACT, XML_DIR


OUTPUT_FILE = EXTRACT / "governance_management_measures.csv"

KEY = "governance"
GROUP = "Governance & Management Measures"
DESCRIPTION = (
    "Part VI Sections A and B: board independence, relationships, delegation, "
    "document changes, asset diversion, minutes, chapters, 990 review, "
    "conflict of interest, whistleblower, document retention, compensation "
    "process, and joint-venture policy."
)

# (column, XML tag). Counts stay as filed; flags become Yes/No.
COUNTS = [
    ("line_1a_voting_members", "GoverningBodyVotingMembersCnt"),
    ("line_1b_independent_members", "IndependentVotingMemberCnt"),
]
FLAGS = [
    ("line_2_family_or_business_relationship", "FamilyOrBusinessRlnInd"),
    ("line_3_management_delegation", "DelegationOfMgmtDutiesInd"),
    ("line_4_governing_document_changes", "ChangeToOrgDocumentsInd"),
    ("line_5_asset_diversion", "MaterialDiversionOrMisuseInd"),
    ("line_8a_minutes_governing_body", "MinutesOfGoverningBodyInd"),
    ("line_8b_minutes_committees", "MinutesOfCommitteesInd"),
    ("line_10a_local_chapters", "LocalChaptersInd"),
    ("line_10b_policies_reference_chapters", "PoliciesReferenceChaptersInd"),
    ("line_11a_form_990_provided_to_board", "Form990ProvidedToGvrnBodyInd"),
    ("line_12a_conflict_of_interest_policy", "ConflictOfInterestPolicyInd"),
    ("line_12b_annual_disclosure", "AnnualDisclosureCoveredPrsnInd"),
    ("line_12c_coi_monitoring", "RegularMonitoringEnfrcInd"),
    ("line_13_whistleblower_policy", "WhistleblowerPolicyInd"),
    ("line_14_document_retention_policy", "DocumentRetentionPolicyInd"),
    ("line_15a_compensation_process_ceo", "CompensationProcessCEOInd"),
    ("line_15b_compensation_process_other", "CompensationProcessOtherInd"),
    ("line_16a_investment_in_joint_venture", "InvestmentInJointVentureInd"),
    ("line_16b_joint_venture_written_policy", "WrittenPolicyOrProcedureInd"),
]

ID_COLUMNS = [
    "ein",
    "tax_period",
    "object_id",
    "xml_file",
    "organization_name",
    "tax_year",
    "extract_status",
]
MEASURE_COLUMNS = (
    [column for column, _tag in COUNTS]
    + [column for column, _tag in FLAGS]
    + ["line_11b_form_990_review_text"]
)
COLUMNS = ID_COLUMNS + MEASURE_COLUMNS


def is_core_line_11b(ref):
    """Core Form 990 Part VI line 11b. Excludes Schedule H line references."""
    folded = re.sub(r"\s+", " ", ref.upper())
    if "SCHEDULE H" in folded or re.search(r"\bSCH\s*H\b", folded):
        return False
    if "PART VI" not in folded:
        return False
    return re.search(r"\b11\s*B\b", folded) is not None


def _blank_measures():
    return {column: "" for column in MEASURE_COLUMNS}


def extract_file(xml_path):
    ein, tax_period, object_id = parse_filename(xml_path)
    record = {
        "ein": ein,
        "tax_period": tax_period,
        "object_id": object_id,
        "xml_file": Path(xml_path).name,
        "organization_name": "",
        "tax_year": tax_period[:4] if len(tax_period) >= 4 else "",
        "extract_status": "",
        **_blank_measures(),
    }

    try:
        root = parse_xml(xml_path)
    except Exception:
        record["extract_status"] = "xml_parse_error"
        return record

    record["organization_name"] = filer_name(root)
    record["tax_year"] = first_text(root, ["TaxYr"]) or record["tax_year"]
    if not record["ein"]:
        filer = first_element(root, "Filer")
        record["ein"] = first_text(filer, ["EIN"]) if filer is not None else ""

    form = first_element(root, "IRS990")
    if form is None:
        record["extract_status"] = "no_irs990"
        return record

    for column, tag in COUNTS:
        raw = element_text(form, tag)
        record[column] = "" if raw is None else raw

    for column, tag in FLAGS:
        record[column] = yes_no(element_text(form, tag))

    texts = []
    for ref, text in iter_schedule_o(root):
        if is_core_line_11b(ref) and text:
            texts.append(text)
    if texts:
        record["line_11b_form_990_review_text"] = " || ".join(dict.fromkeys(texts))

    record["extract_status"] = "ok"
    return record


def main(xml_dir=None, output_file=None):
    xml_dir = Path(xml_dir) if xml_dir else XML_DIR
    output_file = Path(output_file) if output_file else OUTPUT_FILE
    output_file.parent.mkdir(parents=True, exist_ok=True)
    xml_files = sorted(xml_dir.glob("*.xml"))
    print("Group:", GROUP)
    print("XML files to process:", len(xml_files))

    rows = []
    for index, path in enumerate(xml_files, 1):
        rows.append(extract_file(path))
        if index % 2500 == 0:
            print("  processed", index)

    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame.to_csv(output_file, index=False)

    print()
    print("Done. Saved:", output_file)
    print("Total filings:", len(frame))
    print("extract_status:")
    print(frame["extract_status"].replace("", "(blank)").value_counts().to_string())
    print()
    print("Line 11b narratives found:", (frame["line_11b_form_990_review_text"] != "").sum())
    print(
        "Line 10b answered:",
        frame["line_10b_policies_reference_chapters"].isin(["Yes", "No"]).sum(),
    )
    print(
        "Line 16b answered:",
        frame["line_16b_joint_venture_written_policy"].isin(["Yes", "No"]).sum(),
    )
    return frame
