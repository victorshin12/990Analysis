#!/usr/bin/env python3
"""
build_governance_web.py  --  Form 990 Explorer: governance graphics pipeline

    governance_management_measures.csv  ->  governance_dashboard_data.json  ->  governance_dashboard.html

Inputs  (addressed relative to this script unless you pass a path):
    governance_management_measures.csv        the official dataset (one row per filing)
    governance_dashboard_template.html        the page; contains the placeholder __DATA__
    delegation_results.csv   (optional)       only used by --names-csv, to restore full organization names

Outputs (written to ./output by default):
    governance_dashboard_data.json            numbers behind the three graphics
    governance_dashboard.html                 standalone page = template + data

Form 990 lines used (all Part VI, all read directly from the form -- no text classification):
    Line 1a  number of voting members of the governing body
    Line 1b  number of those who are independent
    Line 3   delegated management duties to a management company or other person?   (Yes/No)
    Line 4   significant changes to governing documents?                              (Yes/No)
    Line 16a invested in / participated in a joint venture with a taxable entity?     (Yes/No)

Run:
    python3 build_governance_web.py
    python3 build_governance_web.py --csv path/to/governance_management_measures.csv --out-dir output
    python3 build_governance_web.py --names-csv delegation_results.csv      # restore truncated names
    python3 build_governance_web.py --json-in output/governance_dashboard_data.json   # rebuild HTML only
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
YEARS = (2015, 2024)
REQUIRED = ["tax_year", "ein", "tax_period", "object_id", "organization_name",
            "line_3_management_delegation", "line_16a_investment_in_joint_venture",
            "line_4_governing_document_changes", "line_1a_voting_members", "line_1b_independent_members"]
FLAGS = ["line_3_management_delegation", "line_16a_investment_in_joint_venture", "line_4_governing_document_changes"]


# ---------------------------------------------------------------- step 1: load and clean
def load_clean(csv_path):
    if not Path(csv_path).exists():
        raise SystemExit(f"CSV not found: {csv_path}\nPut governance_management_measures.csv next to this script or pass --csv <path>.")
    d = pd.read_csv(csv_path, low_memory=False)
    missing = [c for c in REQUIRED if c not in d.columns]
    if missing:
        raise SystemExit(f"{csv_path} is missing required column(s): {missing}")
    n_raw = len(d)

    # one filing per EIN x tax year: sort by period and object id, keep the latest (amended returns share the key)
    d = (d[d.tax_year.between(*YEARS)]
         .sort_values(["ein", "tax_year", "tax_period", "object_id"])
         .drop_duplicates(["ein", "tax_year"], keep="last").copy())
    d["ein"] = d.ein.astype("string").str.replace(r"\.0$", "", regex=True).str.zfill(9)

    # Yes/No text -> 1/0 (anything else, including blank, becomes missing)
    for col in FLAGS:
        d[col + "_flag"] = d[col].astype("string").str.strip().str.lower().map({"yes": 1, "no": 0})

    # board independence = line 1b / line 1a, only when the counts are valid
    a = pd.to_numeric(d.line_1a_voting_members, errors="coerce")
    b = pd.to_numeric(d.line_1b_independent_members, errors="coerce")
    d["board_independence"] = ((100 * b / a).where((a > 0) & (b >= 0) & (b <= a))).round(2)

    print(f"[load]  {n_raw:,} rows read -> {len(d):,} filings kept ({YEARS[0]}-{YEARS[1]}, one per EIN and tax year)")
    for col in FLAGS:
        print(f"[check] {col}: {100 * d[col + '_flag'].isna().mean():.1f}% missing / not Yes-No")
    print(f"[check] board independence: {100 * d.board_independence.isna().mean():.1f}% of filings have no valid 1b/1a")
    return d


# ---------------------------------------------------------------- step 2: numbers for graphics 1 and 2
def build_annual(d):
    annual = []
    for y, g in d.groupby("tax_year"):
        row = {"year": int(y), "filings": len(g)}
        for key, col in [("delegation", "line_3_management_delegation_flag"), ("jointventure", "line_16a_investment_in_joint_venture_flag")]:
            v = g[col].dropna()
            row[key] = {"rate": round(100 * v.mean(), 2) if len(v) else None, "yes": int(v.sum()), "valid": len(v)}
        for flag, label in [(1, "yes"), (0, "no")]:
            z = g.loc[g.line_3_management_delegation_flag == flag, "board_independence"].dropna()
            row["independence_" + label] = {"mean": round(float(z.mean()), 2) if len(z) else None, "valid": len(z)}
        annual.append(row)
    return annual


# ---------------------------------------------------------------- step 3: lookup for graphic 3
def build_orgs(d):
    orgs = []
    for ein, g in d.groupby("ein", sort=False):
        if len(g) < 2:                       # lookup needs at least two observed years
            continue
        name = g.organization_name.dropna().astype(str)
        if name.empty:
            continue
        records = []
        for _, r in g.sort_values("tax_year").iterrows():
            def val(col):
                x = r[col + "_flag"]
                return None if pd.isna(x) else int(x)
            records.append({"year": int(r.tax_year), "delegation": val("line_3_management_delegation"),
                            "jointventure": val("line_16a_investment_in_joint_venture"),
                            "documents": val("line_4_governing_document_changes"),
                            "independence": None if pd.isna(r.board_independence) else float(r.board_independence)})
        orgs.append({"ein": str(ein), "name": name.iloc[-1], "records": records})
    orgs.sort(key=lambda x: (x["name"].lower(), x["ein"]))
    return orgs


def apply_full_names(orgs, names_csv):
    """Some XML names hold only the first name line (e.g. 'ALBANY MEDICAL CENTER GROUP').
    If the IRS-index name of the latest filing starts with the XML name and is longer, use the longer one."""
    n = pd.read_csv(names_csv, dtype=str).fillna("")
    n = n[n.taxpayer_name != ""]
    n["yr"] = n.tax_year.astype(int)
    latest = n.sort_values(["ein", "yr"]).groupby("ein").taxpayer_name.last()
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    changed = 0
    for o in orgs:
        full = latest.get(o["ein"])
        if full and norm(full) != norm(o["name"]) and norm(full).startswith(norm(o["name"])):
            o["name"], changed = full, changed + 1
    orgs.sort(key=lambda x: (x["name"].lower(), x["ein"]))
    print(f"[names] restored the full name for {changed} of {len(orgs)} organizations")


# ---------------------------------------------------------------- step 4: write JSON and HTML
def write_outputs(json_data, template, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(json_data, separators=(",", ":"))
    (out_dir / "governance_dashboard_data.json").write_text(payload)
    page = Path(template).read_text(encoding="utf-8")
    if "__DATA__" not in page:
        raise SystemExit("template has no __DATA__ placeholder")
    (out_dir / "governance_dashboard.html").write_text(page.replace("__DATA__", payload.replace("</", "<\\/")), encoding="utf-8")
    print(f"[write] {out_dir}/governance_dashboard_data.json ({len(payload) / 1e6:.2f} MB) and governance_dashboard.html")


def main():
    ap = argparse.ArgumentParser(description="Build the Form 990 Explorer governance graphics")
    ap.add_argument("--csv", default=str(ROOT / "governance_management_measures.csv"))
    ap.add_argument("--template", default=str(ROOT / "governance_dashboard_template.html"))
    ap.add_argument("--out-dir", default=str(ROOT / "output"))
    ap.add_argument("--names-csv", default=None, help="delegation_results.csv, to restore full organization names")
    ap.add_argument("--json-in", default=None, help="reuse an existing data JSON and only rebuild the HTML")
    a = ap.parse_args()

    if a.json_in:
        json_data = json.loads(Path(a.json_in).read_text())
        print(f"[load]  reused {a.json_in}")
    else:
        d = load_clean(a.csv)
        orgs = build_orgs(d)
        json_data = {"annual": build_annual(d), "organizations": orgs,
                     "metadata": {"source": "governance_management_measures.csv", "years": "2015\u20132024", "filings": len(d),
                                  "organization_count": len(orgs),
                                  "unit": "One EIN\u2013tax-year filing; organizations with two or more observed years included in the lookup"}}
    if a.names_csv:
        apply_full_names(json_data["organizations"], a.names_csv)
    write_outputs(json_data, a.template, Path(a.out_dir))
    m = json_data["metadata"]
    print(f"[done]  filings={m['filings']:,}  organizations={m['organization_count']:,}")


if __name__ == "__main__":
    main()
