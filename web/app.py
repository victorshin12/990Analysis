"""Local explorer for delegation + governance extracts.

Run from the repo root:
  .venv/bin/python -m web.app
Then open http://127.0.0.1:5050
"""

from __future__ import annotations

from pathlib import Path

import markdown
from flask import Flask, Response, jsonify, render_template, request

from paths import ROOT
from web.charts import chart_payload, governance_chart_payload
from web.dictionary import load_data_dictionary
from web.data_store import (
    DATASETS,
    aggregate_frame,
    filter_frame,
    filter_options,
    load_all,
    paginate,
    to_csv_bytes,
)

README_PATH = ROOT / "README.md"

app = Flask(__name__)


def _args_dict() -> dict:
    return {k: v for k, v in request.args.items()}


@app.before_request
def _ensure_loaded():
    # Lazy-load once; cheap check via trying get through filter_options path
    from web import data_store

    if not data_store._frames:
        load_all()


def _readme_html() -> str:
    text = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else "_README.md not found._"
    return markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )


@app.get("/")
def index():
    return render_template("index.html", datasets=DATASETS)


@app.get("/dictionary")
def dictionary_page():
    return render_template("dictionary.html")


@app.get("/about")
def about_page():
    return render_template("about.html", readme_html=_readme_html())


@app.get("/api/readme")
def api_readme():
    return jsonify({"html": _readme_html()})


@app.get("/api/dictionary")
def api_dictionary():
    try:
        return jsonify(load_data_dictionary())
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404


@app.get("/api/meta/<dataset>")
def api_meta(dataset: str):
    if dataset not in DATASETS:
        return jsonify({"error": "unknown dataset"}), 404
    return jsonify(
        {
            "key": dataset,
            "label": DATASETS[dataset]["label"],
            "options": filter_options(dataset),
            "total_rows": len(filter_frame(dataset, {})),
        }
    )


@app.get("/api/query/<dataset>")
def api_query(dataset: str):
    if dataset not in DATASETS:
        return jsonify({"error": "unknown dataset"}), 404
    args = _args_dict()
    page = int(args.get("page") or 1)
    page_size = int(args.get("page_size") or 50)
    filtered = filter_frame(dataset, args)
    return jsonify(paginate(filtered, page, page_size))


@app.get("/api/download/<dataset>")
def api_download(dataset: str):
    if dataset not in DATASETS:
        return jsonify({"error": "unknown dataset"}), 404
    args = _args_dict()
    mode = (args.get("mode") or "tab").strip().lower()
    filtered = filter_frame(dataset, args)
    if mode == "aggregated":
        out = aggregate_frame(dataset, filtered)
        filename = f"{dataset}_aggregated_{len(out)}rows.csv"
    else:
        out = filtered
        filename = f"{dataset}_filtered_{len(out)}rows.csv"
    return Response(
        to_csv_bytes(out),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/charts/delegation")
def api_charts_delegation():
    filtered = filter_frame("delegation", _args_dict())
    return jsonify(chart_payload(filtered))


@app.get("/api/charts/governance")
def api_charts_governance():
    filtered = filter_frame("governance", _args_dict())
    return jsonify(governance_chart_payload(filtered))


def main():
    import os

    load_all()
    print("Loaded:")
    for key, meta in DATASETS.items():
        from web.data_store import get_frame

        print(f"  {key}: {len(get_frame(key)):,} rows  ({meta['path'].name})")
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5050"))
    print(f"Open http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
