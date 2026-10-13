"""
Build the FULL EIN list from the CBI hospital crosswalk (no random sampling).

This is the same preparation as make_sample_500.py, but instead of drawing a
random sample of 500 EINs it keeps every unique hospital-related EIN, so you can
pull all available Form 990 filings.

Steps:
1. Load the CBI hospital crosswalk JSON.
2. Clean EINs into a consistent 9-digit string format.
3. Group hospitals by EIN (Form 990 filings are organization/EIN-level,
   and several hospitals can share one EIN).
4. Save every unique EIN (no sampling) for the next step.
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import ACQUIRE, CBI_HOSPITALS


CBI_FILE = CBI_HOSPITALS
OUTPUT_FILE = ACQUIRE / "ein_list_all.csv"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# Load CBI hospital crosswalk
with open(CBI_FILE, "r") as f:
    data = json.load(f)

df = pd.DataFrame(data)


# Clean EINs so they are stored as 9-digit strings
df["ein"] = (
    df["ein"]
    .astype(str)
    .str.replace(r"\D", "", regex=True)
    .str.zfill(9)
)

df = df[df["ein"].str.len() == 9]


# Group hospitals by EIN because Form 990 filings are organization/EIN-level,
# not always one filing per individual hospital
ein_frame = (
    df.groupby("ein")
      .agg(
          hospital_count=("hospital_id", "count"),
          hospital_names=("name", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))),
          states=("state", lambda x: " | ".join(sorted(set(x.dropna().astype(str))))),
          medicare_provider_numbers=(
              "medicare_provider_number",
              lambda x: " | ".join(sorted(set(x.dropna().astype(str))))
          ),
      )
      .reset_index()
)


# Keep every unique hospital-related EIN (no sampling).
ein_all = ein_frame


# Save full EIN list for the next step
ein_all.to_csv(OUTPUT_FILE, index=False)


print("Done.")
print("Total unique hospital EINs:", len(ein_all))
print("Saved file:", OUTPUT_FILE)
print(ein_all.head())
