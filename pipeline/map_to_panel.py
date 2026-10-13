"""
Map distinct-text MSO classifications back onto every filing.

Reads:  mso_classified.csv      (1 row per distinct text, with category etc.)
        mso_text_distinct.csv   (text_id <-> text)
        delegation_results.csv  (full census of filings)
Writes: mso_filings_classified.csv  (each "Yes"-with-text filing + its labels)

is_mso_affiliation is DERIVED here as (category in MSO_CATEGORIES). To also count
peer-system management as MSO affiliation, add "D_peer_system_managed" below.
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CLASSIFY, EXTRACT


CLASSIFIED = CLASSIFY / "mso_classified.csv"
DISTINCT = CLASSIFY / "mso_text_distinct.csv"
DELEG = EXTRACT / "delegation_results.csv"
OUTPUT_FILE = CLASSIFY / "mso_filings_classified.csv"

# Which categories count as an MSO affiliation (the derived flag).
MSO_CATEGORIES = {"A_dedicated_MSO"}  # add "D_peer_system_managed" to include peer-managed


def norm(t):
    t = re.sub(r"^\s*explanation:\s*", "", str(t), flags=re.I)
    return re.sub(r"\s+", " ", t).strip().lower()


cls = pd.read_csv(CLASSIFIED, dtype=str)
cls["text_id"] = cls["text_id"].astype(int)

distinct = pd.read_csv(DISTINCT, dtype=str)
distinct["text_id"] = distinct["text_id"].astype(int)
distinct["key"] = distinct["text"].map(norm)
key2id = dict(zip(distinct["key"], distinct["text_id"]))

deleg = pd.read_csv(DELEG, dtype=str).fillna("")
yes = deleg[(deleg["delegation_indicator"] == "Yes") & (deleg["text_status"] == "text_found")].copy()
yes["key"] = yes["schedule_o_line3_text"].map(norm)
yes["text_id"] = yes["key"].map(key2id)

lab = cls.set_index("text_id")
for col in ["category", "manager_relationship", "scope", "manager_name", "confidence"]:
    yes[col] = yes["text_id"].map(lab[col])
yes["is_mso_affiliation"] = yes["category"].isin(MSO_CATEGORIES)

yes.drop(columns=["key"]).to_csv(OUTPUT_FILE, index=False)

print("Filings labeled:", len(yes))
print("Saved:", OUTPUT_FILE)
print()
print("Category distribution (filings):")
print(yes["category"].value_counts().to_string())
mso = yes[yes["is_mso_affiliation"]]
print()
print("MSO-affiliated filings:", len(mso), "| unique EINs:", mso["ein"].nunique())
