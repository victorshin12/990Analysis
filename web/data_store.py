"""In-memory CSV loaders and filter helpers for the explorer."""

from __future__ import annotations

from io import StringIO

import pandas as pd

from paths import EXTRACT

DATASETS = {
    "delegation": {
        "label": "Delegation (Part VI Line 3)",
        "path": EXTRACT / "delegation_results.csv",
        "search_cols": [
            "ein",
            "organization_name",
            "taxpayer_name",
            "hospital_names",
            "states",
            "schedule_o_line3_text",
            "object_id",
            "xml_file",
        ],
        "flag_cols": ["delegation_indicator"],
        "default_sort": ["tax_year", "ein"],
    },
    "governance": {
        "label": "Governance & Management Measures",
        "path": EXTRACT / "governance_management_measures.csv",
        "search_cols": [
            "ein",
            "organization_name",
            "object_id",
            "xml_file",
            "line_11b_form_990_review_text",
        ],
        "flag_cols": [
            "line_2_family_or_business_relationship",
            "line_3_management_delegation",
            "line_4_governing_document_changes",
            "line_5_asset_diversion",
            "line_8a_minutes_governing_body",
            "line_8b_minutes_committees",
            "line_10a_local_chapters",
            "line_11a_form_990_provided_to_board",
            "line_12a_conflict_of_interest_policy",
            "line_12b_annual_disclosure",
            "line_12c_coi_monitoring",
            "line_13_whistleblower_policy",
            "line_14_document_retention_policy",
            "line_15a_compensation_process_ceo",
            "line_15b_compensation_process_other",
            "line_16a_investment_in_joint_venture",
        ],
        "default_sort": ["tax_year", "ein"],
    },
}

_frames: dict[str, pd.DataFrame] = {}


def load_all() -> None:
    for key, meta in DATASETS.items():
        path = meta["path"]
        if not path.exists():
            raise FileNotFoundError(f"Missing dataset for {key}: {path}")
        _frames[key] = pd.read_csv(path, dtype=str).fillna("")


def get_frame(key: str) -> pd.DataFrame:
    if key not in _frames:
        load_all()
    return _frames[key]


def filter_frame(key: str, args: dict) -> pd.DataFrame:
    meta = DATASETS[key]
    df = get_frame(key)
    out = df

    q = (args.get("q") or "").strip()
    if q:
        # A bare 4-digit year means tax_year, not object_id / xml_file / period end.
        # (tax_period is YYYYMM of the period end, so 2015 filings often show 201606.)
        if q.isdigit() and len(q) == 4 and "tax_year" in out.columns:
            out = out[out["tax_year"] == q]
        else:
            mask = pd.Series(False, index=out.index)
            search_cols = list(meta["search_cols"])
            for extra in ("tax_year", "tax_period"):
                if extra in out.columns and extra not in search_cols:
                    search_cols.append(extra)
            for col in search_cols:
                if col in out.columns:
                    mask |= out[col].str.contains(q, case=False, na=False, regex=False)
            out = out[mask]

    year_min = args.get("year_min")
    year_max = args.get("year_max")
    if "tax_year" in out.columns and (year_min or year_max):
        years = pd.to_numeric(out["tax_year"], errors="coerce")
        if year_min:
            out = out[years >= int(year_min)]
            years = pd.to_numeric(out["tax_year"], errors="coerce")
        if year_max:
            out = out[years <= int(year_max)]

    # Exact Yes/No (or blank) filters for known flag columns
    for col in meta["flag_cols"]:
        val = (args.get(col) or "").strip()
        if val and col in out.columns:
            out = out[out[col] == val]

    # Delegation also filters by state token inside the pipe-separated states field
    state = (args.get("state") or "").strip().upper()
    if key == "delegation" and state and "states" in out.columns:
        out = out[
            out["states"].str.upper().str.contains(
                rf"(?:^|\|\s*){state}(?:\s*\||$)", regex=True, na=False
            )
        ]

    sort_cols = [c for c in meta["default_sort"] if c in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, kind="mergesort")
    return out


def paginate(df: pd.DataFrame, page: int, page_size: int) -> dict:
    total = len(df)
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    start = (page - 1) * page_size
    chunk = df.iloc[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "columns": list(df.columns),
        "rows": chunk.to_dict(orient="records"),
    }


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


OTHER_DATASET = {"delegation": "governance", "governance": "delegation"}


def aggregate_frame(key: str, filtered: pd.DataFrame) -> pd.DataFrame:
    """Left-join the other extract onto the filtered tab rows by object_id."""
    other_key = OTHER_DATASET.get(key)
    if other_key is None or filtered.empty or "object_id" not in filtered.columns:
        return filtered
    other = get_frame(other_key)
    # Keep only columns unique to the other extract (plus join key).
    drop = [c for c in other.columns if c in filtered.columns and c != "object_id"]
    other_slim = other.drop(columns=drop, errors="ignore")
    return filtered.merge(other_slim, on="object_id", how="left")


def filter_options(key: str) -> dict:
    df = get_frame(key)
    years = sorted(
        {int(y) for y in pd.to_numeric(df.get("tax_year", pd.Series(dtype=str)), errors="coerce").dropna()}
    )
    options: dict = {"years": years, "flags": {}}
    for col in DATASETS[key]["flag_cols"]:
        if col in df.columns:
            vals = sorted({v for v in df[col].unique() if v in ("Yes", "No", "")})
            # Prefer Yes/No order
            ordered = [v for v in ("Yes", "No", "") if v in vals]
            options["flags"][col] = ordered
    if key == "delegation" and "states" in df.columns:
        states = set()
        for cell in df["states"]:
            for part in str(cell).split("|"):
                s = part.strip().upper()
                if s and len(s) == 2:
                    states.add(s)
        options["states"] = sorted(states)
    return options
