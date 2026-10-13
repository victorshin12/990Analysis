"""
Build the hospital geography / identifier crosswalk from cbi_hospitals.json.

Reads:  cbi_hospitals.json   (Community Benefit Insight hospital file)
Writes: cbi_geo_xwalk.csv     (one row per hospital)

Columns: pn, ein, fips, county_name, state, street, city, zip
  - pn         = 6-digit Medicare CCN  (from medicare_provider_number)
  - ein        = 9-digit EIN
  - fips       = 5-digit county FIPS    (from fips_state_and_county_code)
  - county_name, state, street, city, zip = hospital address

The first five columns (pn, ein, fips, county_name, state) are unchanged from
the original crosswalk, so 2Descriptives.do keeps working as-is; street/city/zip
are appended for matching external hospital lists (e.g. Sheps Center closures).
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CBI_HOSPITALS, PANEL


INPUT_FILE = CBI_HOSPITALS
OUTPUT_FILE = PANEL / "cbi_geo_xwalk.csv"


def digits(series, width):
    """Strip non-digits and zero-pad to a fixed width (preserves leading zeros)."""
    return series.astype(str).str.replace(r"\D", "", regex=True).str.zfill(width)


with open(INPUT_FILE) as f:
    df = pd.DataFrame(json.load(f))

out = pd.DataFrame({
    "pn":          digits(df["medicare_provider_number"], 6),
    "ein":         digits(df["ein"], 9),
    "fips":        digits(df["fips_state_and_county_code"], 5),
    "county_name": df["county"],
    "state":       df["state"],
    "street":      df["street_address"],
    "city":        df["city"],
    "zip":         digits(df["zip_code"], 5),
})

out.to_csv(OUTPUT_FILE, index=False)

print("Rows:", len(out))
print("Saved:", OUTPUT_FILE)
print(out.head().to_string(index=False))
