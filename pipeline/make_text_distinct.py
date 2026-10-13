"""
Deduplicate the Schedule O delegation explanations to one row per distinct text.

Reads:  delegation_results.csv
Writes: mso_text_distinct.csv  (text_id, n_filings, n_eins, example_ein, text)

Many filings share identical boilerplate, so the ~2,300 "Yes"-with-text filings
collapse to ~1,300 distinct explanations. Classifying the distinct set (then
mapping back with map_to_panel.py) avoids re-classifying identical text.
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CLASSIFY, EXTRACT


INPUT_FILE = EXTRACT / "delegation_results.csv"
OUTPUT_FILE = CLASSIFY / "mso_text_distinct.csv"


def norm(t):
    """Normalize text for de-duplication: drop a leading 'Explanation:' and collapse whitespace."""
    t = re.sub(r"^\s*explanation:\s*", "", str(t), flags=re.I)
    return re.sub(r"\s+", " ", t).strip().lower()


df = pd.read_csv(INPUT_FILE, dtype=str).fillna("")
yes = df[(df["delegation_indicator"] == "Yes") & (df["text_status"] == "text_found")].copy()
yes["key"] = yes["schedule_o_line3_text"].map(norm)

g = yes.groupby("key")
distinct = g.size().sort_values(ascending=False)
rep = yes.drop_duplicates("key").set_index("key")

out = pd.DataFrame({"n_filings": distinct})
out["n_eins"] = g["ein"].nunique()
out["example_ein"] = g["ein"].first()
out["text"] = rep["schedule_o_line3_text"]
out = out.reset_index(drop=True).sort_values("n_filings", ascending=False).reset_index(drop=True)
out.insert(0, "text_id", range(1, len(out) + 1))
out.to_csv(OUTPUT_FILE, index=False)

print("Yes-with-text filings:", len(yes))
print("Distinct explanation texts:", len(out))
print("Saved:", OUTPUT_FILE)
