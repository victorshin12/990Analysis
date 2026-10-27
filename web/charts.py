"""Chart aggregates for the explorer UI, adapted from make_trend_charts.py.

Takes a filtered slice of delegation_results rows and returns JSON-friendly
series. Taxonomy labels still come from mso_text_distinct + mso_classified,
joined the same way map_to_panel / make_trend_charts do.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from paths import CLASSIFY, INPUT

YEARS = list(range(2015, 2025))


def _norm_text(t: str) -> str:
    t = re.sub(r"^\s*explanation:\s*", "", str(t), flags=re.I)
    return re.sub(r"\s+", " ", t).strip().lower()


def _norm_mgr(n: str) -> str:
    s = n.lower()
    if re.search(r"quorum|qhr|ovation", s):
        return "Quorum Health Resources"
    if "healthtech" in s:
        return "HealthTech Management"
    if re.search(
        r"\bchc\b|community hospital corp|community health consult|"
        r"community hospital consult|community health corp",
        s,
    ):
        return "Community Hospital Corp. (CHC)"
    if "alliant" in s:
        return "Alliant Management"
    if "cypress" in s:
        return "Cypress Healthcare"
    if "central ohio orthopedic" in s:
        return "Central Ohio Orthopedic Mgmt."
    if n.strip() == "":
        return "Manager not named"
    return "All other named managers"


def _attach_taxonomy(filings: pd.DataFrame) -> pd.DataFrame:
    f = filings.copy()
    dist_path = CLASSIFY / "mso_text_distinct.csv"
    cls_path = CLASSIFY / "mso_classified.csv"
    if not dist_path.exists() or not cls_path.exists():
        f["category"] = ""
        f["manager_name"] = ""
        return f

    dist = pd.read_csv(dist_path, dtype=str)
    dist["key"] = dist.text.map(_norm_text)
    key2id = dict(zip(dist.key, dist.text_id))
    cls = pd.read_csv(cls_path, dtype=str).fillna("").set_index("text_id")
    f["text_id"] = f.schedule_o_line3_text.map(_norm_text).map(key2id)
    f["category"] = f.text_id.map(cls.category).fillna("")
    f["manager_name"] = f.text_id.map(cls.manager_name).fillna("")
    return f


def _hospital_years(filings: pd.DataFrame) -> pd.DataFrame:
    """Expand EIN×year filings to hospital (CCN) × year rows, same as make_trend_charts."""
    hosp_fallback: dict[str, str] = {}
    hp = INPUT / "cbi_hospitals.json"
    if hp.exists():
        hosp = pd.DataFrame(json.loads(hp.read_text()))
        pn_col = (
            "medicare_provider_numbers"
            if "medicare_provider_numbers" in hosp.columns
            else "medicare_provider_number"
        )
        hosp["pn"] = (
            hosp[pn_col].astype(str).str.replace(r"\D", "", regex=True).str.zfill(6)
        )
        hosp_fallback = dict(zip(hosp.pn, hosp.state))

    rows = []
    for r in filings.itertuples(index=False):
        pns = [
            x.strip().zfill(6)
            for x in re.split(r"\s*\|\s*", getattr(r, "medicare_provider_numbers", "") or "")
            if x.strip()
        ]
        sts = [
            x.strip()
            for x in re.split(r"\s*\|\s*", getattr(r, "states", "") or "")
            if x.strip()
        ]
        if not pns:
            continue
        for i, pn in enumerate(pns):
            if len(sts) == len(pns):
                st = sts[i]
            elif len(sts) == 1:
                st = sts[0]
            else:
                st = hosp_fallback.get(pn, "")
            rows.append(
                (
                    pn,
                    r.ein,
                    int(r.yr),
                    r.delegation_indicator == "Yes",
                    r.category,
                    r.manager_name,
                    st,
                )
            )

    h = pd.DataFrame(
        rows, columns=["pn", "ein", "yr", "yes", "category", "manager_name", "state"]
    )
    h["A"] = h.category == "A_dedicated_MSO"
    h["D"] = h.category == "D_peer_system_managed"
    h["C"] = h.category == "C_parent_shared_services"
    return h[h.yr.between(YEARS[0], YEARS[-1])].copy()


def build_obs(filtered_delegation: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dedupe → attach taxonomy → hospital-years. Returns (filings, obs)."""
    d = filtered_delegation.fillna("").copy()
    if d.empty:
        empty_f = d.copy()
        empty_f["yr"] = pd.Series(dtype=int)
        empty_f["category"] = ""
        empty_f["manager_name"] = ""
        empty_h = pd.DataFrame(
            columns=["pn", "ein", "yr", "yes", "category", "manager_name", "state", "A", "D", "C"]
        )
        return empty_f, empty_h

    d["yr"] = pd.to_numeric(d.tax_year, errors="coerce").fillna(0).astype(int)
    f = d.sort_values("object_id").drop_duplicates(["ein", "yr"], keep="last").copy()
    f = _attach_taxonomy(f)
    obs = _hospital_years(f)
    return f, obs


def chart_payload(filtered_delegation: pd.DataFrame) -> dict:
    """JSON payload for the delegation tab charts."""
    f, obs = build_obs(filtered_delegation)
    years = YEARS

    if obs.empty:
        zeros = [0.0] * len(years)
        counts = [0] * len(years)
        return {
            "years": years,
            "n_hospital_years": counts,
            "rates": {
                "any_delegation": zeros,
                "dedicated_mso": zeros,
                "peer_system": zeros,
                "parent_shared": zeros,
            },
            "adopt_exit": {"years": years[1:], "adopt": [0] * 9, "exit": [0] * 9},
            "top_states": {"labels": [], "values": []},
            "managers": {"labels": [], "years": years, "series": []},
            "meta": {
                "filtered_rows": int(len(filtered_delegation)),
                "filings": 0,
                "hospital_years": 0,
                "note": "No rows match the current filters.",
            },
        }

    g = obs.groupby("yr").agg(
        n=("pn", "size"),
        yes=("yes", "mean"),
        A=("A", "mean"),
        D=("D", "mean"),
        C=("C", "mean"),
    )
    rate = lambda col: [round(float(g.loc[y, col] * 100), 2) if y in g.index else 0.0 for y in years]
    n_hy = [int(g.loc[y, "n"]) if y in g.index else 0 for y in years]

    # adopt / exit of dedicated MSO (EIN level), same idea as fig_events
    e = obs.groupby(["ein", "yr"]).agg(yes=("yes", "max"), A=("A", "max")).reset_index()
    e["code"] = np.where(e.A, 3, np.where(e.yes, 2, 1))
    M = e.pivot(index="ein", columns="yr", values="code").reindex(columns=years).fillna(0).astype(int)
    adopt = {y: 0 for y in years}
    ends = {y: 0 for y in years}
    for _, row in M.iterrows():
        for y in years[1:]:
            if row[y] == 3 and row[y - 1] > 0 and row[y - 1] != 3:
                adopt[y] += 1
            if row[y] > 0 and row[y] != 3 and row[y - 1] == 3:
                ends[y] += 1

    # top states by dedicated-MSO hospital-years in the filtered set
    st = (
        obs[obs.A & (obs.state != "")]
        .groupby("state")
        .pn.nunique()
        .sort_values(ascending=False)
        .head(15)
    )

    # manager heatmap collapsed to totals + per-year for Chart.js stacked/grouped
    order = [
        "Quorum Health Resources",
        "HealthTech Management",
        "Cypress Healthcare",
        "Community Hospital Corp. (CHC)",
        "Alliant Management",
        "Central Ohio Orthopedic Mgmt.",
        "All other named managers",
        "Manager not named",
    ]
    A = obs[obs.A].copy()
    if len(A):
        A["mgr"] = A.manager_name.apply(_norm_mgr)
        mm = (
            A.groupby(["mgr", "yr"])
            .pn.nunique()
            .unstack(fill_value=0)
            .reindex(index=order, columns=years, fill_value=0)
        )
        mgr_series = [
            {"label": lab, "data": [int(mm.loc[lab, y]) if lab in mm.index else 0 for y in years]}
            for lab in order
            if lab in mm.index and mm.loc[lab].sum() > 0
        ]
        mgr_labels = [s["label"] for s in mgr_series]
    else:
        mgr_series, mgr_labels = [], []

    return {
        "years": years,
        "n_hospital_years": n_hy,
        "rates": {
            "any_delegation": rate("yes"),
            "dedicated_mso": rate("A"),
            "peer_system": rate("D"),
            "parent_shared": rate("C"),
        },
        "adopt_exit": {
            "years": years[1:],
            "adopt": [adopt[y] for y in years[1:]],
            "exit": [ends[y] for y in years[1:]],
        },
        "top_states": {
            "labels": list(st.index.astype(str)),
            "values": [int(v) for v in st.values],
        },
        "managers": {"labels": mgr_labels, "years": years, "series": mgr_series},
        "meta": {
            "filtered_rows": int(len(filtered_delegation)),
            "filings": int(len(f)),
            "hospital_years": int(len(obs)),
            "note": (
                "Rates are % of observed hospital-years in the current filter, "
                "2015–2024, using the same taxonomy join as make_trend_charts.py."
            ),
        },
    }
