"""
Download actual IRS XML files for the hospital-related EINs (FULL PANEL).

This script:
1. Reads xml_matches.csv.
2. Keeps EVERY distinct Form 990 filing (full panel), not just the latest per EIN.
3. Downloads IRS ZIP files that contain those XML filings.
4. Extracts matching XML files using the IRS object_id.
5. Saves a download log showing what worked and what failed.

Output XML filenames are EIN_TAXPERIOD_OBJECTID.xml, which is unique per filing,
so multiple tax years per hospital coexist without collisions.

Important:
- This script keeps a log at xml_download_log.csv.
- It skips filings already logged on future runs (success or failure).
- This prevents repeating the same failed downloads.

Start with TEST_LIMIT = 10 while testing.
After verifying the script works, change TEST_LIMIT to None to pull everything.
"""

import ssl
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import ACQUIRE, IRS_ZIPS, XML_DIR


MATCHES_FILE = ACQUIRE / "xml_matches.csv"
XML_OUTPUT_DIR = XML_DIR
ZIP_CACHE_DIR = IRS_ZIPS
LOG_FILE = ACQUIRE / "xml_download_log.csv"

XML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ZIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


# Test mode: only try this many filings per run.
# Change to None when ready to process everything remaining.
TEST_LIMIT = None


def get_zip_urls(year):
    """
    Return possible IRS ZIP URLs for a given IRS index year.

    Two naming schemes:
    - 2017-2020 (legacy): download990xml_<year>_<n>.zip, plus a CT1 catch-all.
    - 2021+ (TEOS): <year>_TEOS_XML_<month><suffix>.zip, posted incrementally.

    For the TEOS years we do NOT hard-code each year's exact batch set. The IRS
    adds batches over time and the set differs unpredictably by year (e.g. 2021
    has only 01A, 2022 has 01A/02A, 2025 spans 12 months plus B/C/D supplements,
    2026 grows as the year progresses). Hard-coding silently drops every filing
    in an unlisted batch, so instead we generate every plausible name and let
    download_zip skip the ones that do not exist (cached as missing after the
    first probe). A-suffix batches are listed first since they are the common
    case, so most filings are found without probing the rarer B/C/D batches.
    """
    base = f"https://apps.irs.gov/pub/epostcard/990/xml/{year}"

    # 2017-2020 use the legacy naming.
    # Verified on the IRS server: download990xml_<year>_1..7 exist (8 is harmless),
    # and 2017 also has a CT1 catch-all (other years' CT1 simply fails and is skipped).
    if year in [2017, 2018, 2019, 2020]:
        urls = [f"{base}/{year}_TEOS_XML_CT1.zip"]
        urls += [f"{base}/download990xml_{year}_{i}.zip" for i in range(1, 9)]
        return urls

    # 2021+ TEOS monthly batches: generate all plausible names (A first).
    if year >= 2021:
        urls = []
        for suffix in ("A", "B", "C", "D"):
            for month in range(1, 13):
                urls.append(f"{base}/{year}_TEOS_XML_{month:02d}{suffix}.zip")
        return urls

    return []


# In-run cache of ZIP URLs that do not exist on the server, so each missing
# batch (there are many, given the broad name generation above) is only probed
# once per run instead of once per filing.
_missing_zip_urls = set()


def download_zip(url):
    """
    Download a ZIP file if it is not already saved locally.
    """
    zip_name = url.split("/")[-1]
    zip_path = ZIP_CACHE_DIR / zip_name

    if zip_path.exists():
        return zip_path, "already_downloaded"

    # Skip URLs already known (this run) to be missing.
    if url in _missing_zip_urls:
        return None, "known_missing"

    try:
        context = ssl._create_unverified_context()

        print(f"Downloading ZIP: {zip_name}")
        with urllib.request.urlopen(url, context=context) as response:
            zip_path.write_bytes(response.read())

        return zip_path, "downloaded"

    except Exception as e:
        # Remember misses so other filings in this run don't re-probe them.
        _missing_zip_urls.add(url)
        return None, f"zip_download_failed: {e}"


def extract_with_unzip(zip_path, member, output_path):
    """
    Fallback extraction for ZIP members Python's zipfile cannot decode.

    Some recent IRS ZIPs compress XML with Deflate64 (compression method 9),
    which the standard library does not support. The system `unzip` does, so we
    shell out to `unzip -p` (write member to stdout) and save the bytes.
    """
    try:
        result = subprocess.run(
            ["unzip", "-p", str(zip_path), member],
            capture_output=True,
        )

        # Note: `unzip` may return a non-zero exit code on a benign warning
        # (these IRS archives trigger an "extra bytes at beginning" warning)
        # while still extracting the member correctly. So validate by content
        # rather than exit code: accept it if the output looks like XML,
        # allowing for an optional UTF-8 byte-order mark.
        content = result.stdout
        if content and content.lstrip(b"\xef\xbb\xbf").lstrip().startswith(b"<"):
            output_path.write_bytes(content)
            return output_path

    except Exception as e:
        print(f"unzip fallback error for {member}: {e}")

    return None


def extract_xml_from_zip(zip_path, object_id, output_name):
    """
    Look inside a ZIP file for an XML whose filename contains the object_id.
    If found, extract it to XML_OUTPUT_DIR.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                member_name = Path(member).name

                if object_id in member_name and member_name.endswith(".xml"):
                    output_path = XML_OUTPUT_DIR / output_name

                    try:
                        with z.open(member) as source:
                            output_path.write_bytes(source.read())

                        return output_path, member_name

                    except NotImplementedError:
                        # IRS sometimes uses Deflate64 (compression method 9),
                        # which Python's zipfile cannot decode. Fall back to the
                        # system `unzip`, which handles it.
                        if extract_with_unzip(zip_path, member, output_path) is not None:
                            return output_path, member_name

                        print(f"Deflate64 fallback failed for {member_name} in {zip_path.name}")
                        return None, None

                    except Exception as e:
                        print(f"Could not extract {member_name} from {zip_path.name}: {e}")
                        return None, None

        return None, None

    except Exception as e:
        print(f"Could not open ZIP {zip_path.name}: {e}")
        return None, None


# Load IRS index matches
df = pd.read_csv(MATCHES_FILE, dtype=str)

# Keep regular Form 990 filings only
df = df[df["return_type"] == "990"].copy()

# FULL PANEL: keep every distinct filing.
# Dedup only by object_id so the same filing is never downloaded twice; amended
# returns (same EIN + tax_period, different object_id) are intentionally kept.
filings = df.drop_duplicates(subset=["object_id"]).copy()

# Sort so output is stable and easy to scan (by EIN, then tax period).
filings["tax_period_num"] = pd.to_numeric(filings["tax_period"], errors="coerce")
filings = filings.sort_values(["ein", "tax_period_num", "irs_index_year"]).copy()


# Skip filings that were already attempted in a previous run.
# This includes both successful downloads and failures.
if LOG_FILE.exists():
    old_log = pd.read_csv(LOG_FILE, dtype=str)
    already_tried = set(old_log["object_id"].dropna().astype(str))

    before = len(filings)
    filings = filings[~filings["object_id"].astype(str).isin(already_tried)].copy()
    after = len(filings)

    print(f"Skipped already logged filings: {before - after}")


if TEST_LIMIT is not None:
    filings = filings.head(TEST_LIMIT).copy()

print("Filings selected for XML download:", len(filings))


log_rows = []

for _, row in filings.iterrows():
    ein = row["ein"]
    object_id = row["object_id"]
    irs_index_year = int(row["irs_index_year"])
    tax_period = row["tax_period"]
    taxpayer_name = row["taxpayer_name"]

    output_name = f"{ein}_{tax_period}_{object_id}.xml"

    print()
    print(f"Looking for XML: EIN={ein}, tax_period={tax_period}, object_id={object_id}")

    found_xml_path = None
    found_zip_name = None
    status = "xml_not_found"

    # The XML physically lives in the ZIP batch identified by the object_id's
    # year prefix, which is not always the index year (~12% of filings differ,
    # and the object_id year is always the earlier one). Search the object_id
    # year first, then fall back to the index year.
    # Note: object_id years <= 2016 are not hosted by the IRS as bulk ZIPs, so
    # those filings cannot be downloaded from this source and will log as
    # xml_not_found.
    candidate_years = []
    try:
        candidate_years.append(int(str(object_id)[:4]))
    except (ValueError, TypeError):
        pass
    if irs_index_year not in candidate_years:
        candidate_years.append(irs_index_year)

    zip_urls = []
    for candidate_year in candidate_years:
        zip_urls.extend(get_zip_urls(candidate_year))

    for url in zip_urls:
        zip_path, zip_status = download_zip(url)

        if zip_path is None:
            continue

        extracted_path, xml_member_name = extract_xml_from_zip(
            zip_path=zip_path,
            object_id=object_id,
            output_name=output_name,
        )

        if extracted_path is not None:
            found_xml_path = extracted_path
            found_zip_name = zip_path.name
            status = "downloaded"
            print(f"Found XML in {found_zip_name}")
            break

    log_rows.append({
        "ein": ein,
        "tax_period": tax_period,
        "irs_index_year": irs_index_year,
        "taxpayer_name": taxpayer_name,
        "object_id": object_id,
        "xml_file": str(found_xml_path) if found_xml_path else "",
        "zip_file": found_zip_name if found_zip_name else "",
        "status": status,
        "hospital_count": row.get("hospital_count", ""),
        "hospital_names": row.get("hospital_names", ""),
        "states": row.get("states", ""),
        "medicare_provider_numbers": row.get("medicare_provider_numbers", ""),
    })


# Append new results to the existing log instead of overwriting it.
new_log = pd.DataFrame(log_rows)

if LOG_FILE.exists():
    old_log = pd.read_csv(LOG_FILE, dtype=str)
    log = pd.concat([old_log, new_log], ignore_index=True)
else:
    log = new_log

log.to_csv(LOG_FILE, index=False)


print()
print("Done.")
print("XML files saved in:", XML_OUTPUT_DIR)
print("Download log saved to:", LOG_FILE)

if not log.empty:
    print()
    print("Overall log status counts:")
    print(log["status"].value_counts())

if not new_log.empty:
    print()
    print("This run status counts:")
    print(new_log["status"].value_counts())
