"""
Build the hospital-year panel of management-delegation measures.

Reads:  delegation_results.csv     (full census of filings, one row per filing)
        mso_filings_classified.csv (taxonomy labels for the "Yes"-with-text filings)
        cbi_geo_xwalk.csv          (hospital universe: pn <-> EIN <-> county)
Writes: hosp_year_panel.csv        (one row per hospital (pn) x tax_year)

What it does:
1. De-duplicates amended returns: within each EIN x tax_year, keeps the latest
   submission (highest object_id).
2. Expands each EIN-level filing to the hospitals it covers by splitting the
   "pn1 | pn2 | ..." medicare_provider_numbers field.
3. Joins the MSO taxonomy labels and derives is_mso (= A_dedicated_MSO) and
   is_peer_managed (= D_peer_system_managed).
4. Places the result on a balanced grid: every hospital in the CBI universe x
   every tax year 2014-2025, with filing_observed marking which hospital-years
   actually have a filing. A False row means "no e-filed 990 available for this
   hospital-year" (never filed, filed on paper, not yet filed, or not in the
   IRS bulk XML) -- NOT that the hospital had no MSO. Recent years are thin
   because of filing lags; treat the 2024-2025 tails accordingly.
5. Merges county geography from the crosswalk.

The panel key is pn (Medicare CCN) x tax_year (calendar year the fiscal year
begins). MSO status is assigned at the EIN (filer) level, so all hospitals
under one EIN share a label in a given year.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CLASSIFY, EXTRACT, PANEL


DELEGATION_FILE = EXTRACT / "delegation_results.csv"
CLASSIFIED_FILE = CLASSIFY / "mso_filings_classified.csv"
XWALK_FILE = PANEL / "cbi_geo_xwalk.csv"
OUTPUT_FILE = PANEL / "hosp_year_panel.csv"

PANEL_YEARS = range(2014, 2026)  # tax years observed in the corpus

# Categories counted as MSO / peer-system management (same convention as
# map_to_panel.py -- edit there and here together if the definition changes).
MSO_CATEGORY = "A_dedicated_MSO"
PEER_CATEGORY = "D_peer_system_managed"


def main():
    filings = pd.read_csv(DELEGATION_FILE, dtype=str).fillna("")
    labels = pd.read_csv(CLASSIFIED_FILE, dtype=str).fillna("")
    xwalk = pd.read_csv(XWALK_FILE, dtype=str).fillna("")

    # 1. One filing per EIN x tax_year: amended returns share the key, and the
    # higher object_id is the later submission.
    filings = (
        filings.sort_values("object_id")
        .drop_duplicates(subset=["ein", "tax_year"], keep="last")
    )

    # 2. Attach taxonomy labels to their filings.
    keys = ["ein", "tax_period", "object_id"]
    labels = labels[keys + ["category", "manager_name", "confidence"]]
    filings = filings.merge(labels, on=keys, how="left").fillna("")

    filings["is_mso"] = filings["category"] == MSO_CATEGORY
    filings["is_peer_managed"] = filings["category"] == PEER_CATEGORY

    # 3. Expand EIN-level filings to hospital level.
    filings["pn"] = filings["medicare_provider_numbers"].str.split(r" \| ")
    hosp = filings.explode("pn")
    hosp["pn"] = hosp["pn"].str.strip().str.zfill(6)
    hosp = hosp[hosp["pn"].str.len() == 6]

    hosp = hosp[
        [
            "pn", "tax_year", "ein", "tax_period", "object_id", "taxpayer_name",
            "delegation_indicator", "text_status", "category", "manager_name",
            "confidence", "is_mso", "is_peer_managed",
        ]
    ]

    # 4. Balanced grid: hospital universe x panel years.
    grid = xwalk[["pn", "ein"]].rename(columns={"ein": "ein_xwalk"})
    grid = grid.merge(pd.Series(PANEL_YEARS, name="tax_year").astype(str), how="cross")

    panel = grid.merge(hosp, on=["pn", "tax_year"], how="outer")
    panel["filing_observed"] = panel["object_id"].notna() & (panel["object_id"] != "")
    # For unobserved hospital-years, fall back to the crosswalk EIN.
    panel["ein"] = panel["ein"].where(panel["filing_observed"], panel["ein_xwalk"])
    panel = panel.drop(columns=["ein_xwalk"])
    for col in ("is_mso", "is_peer_managed"):
        panel[col] = panel[col].eq(True)

    # 5. Geography.
    geo = xwalk[["pn", "fips", "county_name", "state", "city", "zip"]]
    panel = panel.merge(geo, on="pn", how="left")

    panel = panel.sort_values(["pn", "tax_year"]).fillna("")
    panel.to_csv(OUTPUT_FILE, index=False)

    obs = panel["filing_observed"].sum()
    print(f"Panel: {len(panel):,} hospital-years "
          f"({panel['pn'].nunique():,} hospitals x {len(PANEL_YEARS)} years)")
    print(f"  with an observed filing: {obs:,}")
    print(f"  MSO (A) hospital-years: {panel['is_mso'].sum():,}; "
          f"peer-managed (D): {panel['is_peer_managed'].sum():,}")
    print(f"Wrote {OUTPUT_FILE.name}")


if __name__ == "__main__":
    main()
