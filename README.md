# 990 Analysis Explorer

IRS Form 990 hospital extracts, a research pipeline that builds them, and a small web app for browsing the CSVs.

Live site (Render): https://form990-explorer.onrender.com

---

## Technical

### Repo layout

```
web/              Flask explorer (UI + API)
extractors/       One module per Form 990 measure group → CSV under data/extract/
pipeline/         Acquire XMLs, classify narratives, build the hospital-year panel
data/
  input/          Hospital universe + XML filings (xml_files/ is local / large)
  acquire/        EIN list, IRS index matches, download log
  extract/        Extractor outputs the website reads
  classify/       Distinct texts + labels (used by charts / panel)
  panel/          Final hospital × year panel
paths.py          Shared paths into data/
render.yaml       Render free-tier web service
requirements.txt  Python deps
```

`paths.py` is the single place that points code at `data/`. The website and extractors both use it.

### Website

#### What it is

A Flask app that loads extract CSVs into memory, serves a tabbed browser UI, and exposes JSON APIs for filtering, pagination, CSV download, and chart series. There is no database.

Typical flow:

1. Browser loads `web/templates/index.html` (+ `web/static/`)
2. Front end calls `/api/...` with the current filters
3. `web/data_store.py` filters the in-memory DataFrame and returns a page of rows (or a full CSV download)
4. Optional chart endpoints aggregate the **filtered** rows and return JSON; the front end draws charts with Chart.js

#### Key files

| Path | Role |
|------|------|
| `web/app.py` | Flask routes (`/`, `/api/query/...`, `/api/download/...`, `/api/charts/...`) |
| `web/data_store.py` | Which CSVs are loaded, search/filter rules, pagination |
| `web/charts.py` | Server-side aggregates for chart endpoints |
| `web/templates/index.html` | Page shell, tabs, controls, chart canvases |
| `web/static/app.js` | Tabs, filters, table, chart wiring |
| `web/static/style.css` | Layout / styling |

When you add a dataset tab, a filter, or a visual, you usually touch `data_store.py` (data + filters), optionally `charts.py` + an API route, then the template/JS. Charts and filters will change over time; this split should stay the same.

#### Run locally

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m web                      # http://127.0.0.1:5050
```

The app binds `HOST` / `PORT` from the environment (defaults `0.0.0.0` and `5050`). It expects the extract CSVs under `data/extract/` (and classify files if you use chart endpoints that join labels).

#### Refreshing data the site shows

Regenerate extracts, then restart the local server (or redeploy):

```bash
python -m extractors delegation
python -m extractors governance
```

The site reads whatever is currently in those CSVs; it does not re-parse XML itself.

### Hosting (Render)

The app is a free Render **web service** defined in `render.yaml`.

- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn -b 0.0.0.0:$PORT -w 1 --timeout 120 web.app:app`
- **Repo:** GitHub `victorshin12/990Analysis` (private), auto-deploy on push to `main`
- **URL:** https://form990-explorer.onrender.com
- **Dashboard:** https://dashboard.render.com/web/srv-dbgh9omc6qcc73bukmq0

Free instances sleep when idle; the first request after sleep can take ~30–60 seconds. For self-hosting, feel free to clone this project and host on a separate Render account.

#### Shipping a UI change

1. Edit under `web/` (and CSVs under `data/` if needed)
2. Commit and push to `main`
3. Render rebuilds and redeploys

Do not commit the full `data/input/xml_files/` corpus (gitignored; too large). The live site only needs the extract/classify CSVs that are already in the repo.

### Pipeline (high level)

Data moves in one direction: acquire → extract → classify → panel. Scripts live in `pipeline/` and `extractors/`; run them from the repo root.

```
CBI hospitals → EINs → IRS XML matches → download XMLs
        → extractors (Part VI fields / Schedule O text)
        → optional text de-dupe + LLM classify
        → hospital-year panel
```

| Stage | Where | Output area |
|-------|--------|-------------|
| Identity & download | `pipeline/make_ein_list.py`, `find_xml.py`, `download_xml.py` | `data/acquire/`, `data/input/` |
| Measure extraction | `python -m extractors <group>` | `data/extract/` |
| Narrative labels | `make_text_distinct.py`, `classify_mso.py`, `map_to_panel.py` | `data/classify/` |
| Panel | `make_geo_xwalk.py`, `build_panel.py` | `data/panel/` |

Extractors are registered in `extractors/__init__.py`. Add a new measure group as its own module with `KEY`, `GROUP`, and `main()`, then register it. That keeps the website’s CSV inputs independent of one another.

`classify_mso.py` is the only step that needs an Anthropic API key (`ANTHROPIC_API_KEY` or gitignored `anthropic_key.txt`). Intermediate and final CSVs are already in `data/` for most workflows; you only need the large XML download to re-run extraction from scratch.

### Notes

- Python 3.10+ recommended.
- No DB, Redis, or build step beyond `pip install` — the UI is server-rendered HTML + static JS.
- Offline static PNGs can still be produced with `make_trend_charts.py`; the hosted UI prefers live JSON + Chart.js from the current filter.

---

## Qualitative

### Scope and approach

- Select Form 990 governance measures for descriptive website graphics.
- Use Part VI fields and Schedule O narratives; see `Data Dictionary .xlsx` for definitions.
- Keep earlier MSO narrative classifications separate from Part VI responses.

### Measure selection and preparation

- Use delegation (VI.3), joint ventures (VI.16a), board composition (VI.1a–1b), and governing-document changes (VI.4).
- Restrict proposal charts to 2015–2024; retain one filing per EIN–year.
- Treat records as filing organizations; distinguish missing responses from `No`.

### Graphics methodology

- **Trend overlay:** Plot annual `Yes` rates for delegation and joint ventures.
- **Board comparison:** Plot annual mean board independence by delegation `Yes`/`No`.
- **Organization timeline:** Show VI.3, VI.4, and VI.16a responses by EIN and year (`Yes`/`No`/missing).

### Website use and interpretation

- Follow the existing Flask/Chart.js pattern described above: load extracts in `web/data_store.py`, calculate filtered chart series in `web/charts.py`, expose them through `web/app.py`, and render them in the template/JS.
- Display each graphic's Form 990 source, tax years, valid-response denominator, and missing-data treatment; allow organization-level lookup by EIN where supported.
- Use the **Data Dictionary** to explain fields and calculations. Check the original filing before interpreting an individual organization's change.
- These are **descriptive reporting measures**: joint ventures, delegation, and governing-document changes do not independently establish hospital acquisitions, consolidation, or governance effectiveness.

### Reproduce proposal graphics

```bash
python -m pip install pandas numpy matplotlib python-pptx
python build_vip_useful_graphics.py
```

- Run alongside `governance_management_measures.csv`; the script exports three PNG figures and a proposal PowerPoint.
- This script is separate from the repository's production pipeline and does **not** deploy graphics to Render.
