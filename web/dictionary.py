"""Load Data Dictionary.xlsx and export JSON for the explorer UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paths import ROOT

XLSX_PATH = ROOT / "Data Dictionary .xlsx"
JSON_PATH = ROOT / "web" / "static" / "data_dictionary.json"


def _scalar(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    return text if text else None


def export_data_dictionary_json(
    xlsx_path: Path | None = None,
    json_path: Path | None = None,
) -> Path:
    from openpyxl import load_workbook

    xlsx = xlsx_path or XLSX_PATH
    out = json_path or JSON_PATH
    if not xlsx.is_file():
        raise FileNotFoundError(f"Data dictionary workbook not found: {xlsx}")

    wb = load_workbook(xlsx, read_only=True, data_only=True)
    sheets: list[dict[str, Any]] = []
    for name in wb.sheetnames:
        ws = wb[name]
        raw_rows = [list(row) for row in ws.iter_rows(values_only=True)]
        if not raw_rows:
            sheets.append({"name": name, "columns": [], "rows": []})
            continue
        header = [str(c).strip() if c is not None else "" for c in raw_rows[0]]
        columns = [h for h in header if h]
        rows: list[dict[str, Any]] = []
        for raw in raw_rows[1:]:
            if not any(c is not None and str(c).strip() for c in raw):
                continue
            row: dict[str, Any] = {}
            for i, col in enumerate(header):
                if not col:
                    continue
                row[col] = _scalar(raw[i] if i < len(raw) else None)
            if any(v is not None for v in row.values()):
                rows.append(row)
        sheets.append({"name": name, "columns": columns or header, "rows": rows})
    wb.close()

    payload = {"sheets": sheets}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def load_data_dictionary() -> dict[str, Any]:
    if JSON_PATH.is_file():
        return json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return json.loads(export_data_dictionary_json().read_text(encoding="utf-8"))


if __name__ == "__main__":
    path = export_data_dictionary_json()
    print(f"Wrote {path}")