# Making a panel of nonprofit management delegation measures 

This project identifies which U.S. nonprofit hospitals **delegate management** by mining IRS Form 990 filings.

It runs in two stages: **(1) detect** management service organization (MSO) affiliations from IRS Form 990 XML, then **(2) build** a longitudinal hospital-year panel of the delegation measures (`build_panel.py`).

The primary data source is the public IRS bulk distribution of e-filed Form 990 XML.

------------------------------------------------------------------------

## Quick start

``` bash
# 1. Install dependencies (Python 3.10+)
pip install -r requirements.txt

# 2. Run the pipeline in order (see "Pipeline" below).
python pipeline/make_ein_list.py
python pipeline/find_xml.py
python pipeline/download_xml.py          # long-running: downloads ~tens of GB of IRS ZIPs
python -m extractors delegation
python pipeline/make_text_distinct.py
python pipeline/classify_mso.py          # needs an Anthropic API key — see below
python pipeline/map_to_panel.py
python pipeline/make_geo_xwalk.py
python pipeline/build_panel.py

```

You do **not** need to re-run everything: the intermediate CSVs under `data/`, the final labeled dataset (`data/classify/mso_filings_classified.csv`), and the built hospital-year panel (`data/panel/hosp_year_panel.csv`) are all included. The only steps that need the large XML corpus are `pipeline/download_xml.py` and `python -m extractors delegation`.

```
pipeline/          stage scripts (acquire, classify, panel)
extractors/        one module per measure group
data/input/        hospital list and Form 990 XML
data/acquire/      EIN list, IRS index matches, download log
data/extract/      extractor outputs (one CSV per measure group)
data/classify/     MSO text labels
data/panel/        hospital crosswalk and hospital-year panel
data/reference/    raw IRS XML batch, not used by the scripts
docs/              syllabus and slides
```

------------------------------------------------------------------------

## Pipeline

Scripts live in `pipeline/` and `extractors/`. Data lives under `data/`. Run the scripts from the repo root, in this order:

| \# | Script | Reads | Writes |
|----|----|----|----|
| 1 | `pipeline/make_ein_list.py` | `data/input/cbi_hospitals.json` | `data/acquire/ein_list_all.csv` |
| 2 | `pipeline/find_xml.py` | `data/acquire/ein_list_all.csv` | `data/acquire/xml_matches.csv` |
| 3 | `pipeline/download_xml.py` | `data/acquire/xml_matches.csv` | `data/input/xml_files/*.xml`, `data/input/irs_zips/`, `data/acquire/xml_download_log.csv` |
| 4 | `python -m extractors delegation` | `data/input/xml_files/`, `data/acquire/xml_download_log.csv` | `data/extract/delegation_results.csv` |
| 5 | `pipeline/make_text_distinct.py` | `data/extract/delegation_results.csv` | `data/classify/mso_text_distinct.csv` |
| 6 | `pipeline/classify_mso.py` | `data/classify/mso_text_distinct.csv` | `data/classify/mso_classified.csv` |
| 7 | `pipeline/map_to_panel.py` | `data/classify/mso_classified.csv`, `data/extract/delegation_results.csv` | `data/classify/mso_filings_classified.csv` |
| 8 | `pipeline/make_geo_xwalk.py` | `data/input/cbi_hospitals.json` | `data/panel/cbi_geo_xwalk.csv` |
| 9 | `pipeline/build_panel.py` | delegation results, classified filings, geo crosswalk | `data/panel/hosp_year_panel.csv` |

What the pipeline does, in plain terms: - **1–2** turn a list of hospitals into a list of specific IRS filings (with the `object_id` needed to locate each one). - **3** downloads and extracts the actual 990 XML documents. - **4** reads the structured **Part VI, Section A, Line 3** field ("Did the organization delegate management duties to a management company or other person?") and, for every "Yes", pulls the matching **Schedule O** explanation text. - **5–7** de-duplicate that text, classify each distinct explanation into the MSO taxonomy (below), and join the labels back onto the filing panel. - **8–9** build the hospital-level geography crosswalk and expand the EIN-level filings into a hospital (Medicare CCN) × tax-year panel, `hosp_year_panel.csv`, on a balanced grid over the full CBI hospital universe, 2014–2025. Each row carries a `filing_observed` flag: `False` means no e-filed 990 is available for that hospital-year (paper filer, not yet filed, or outside IRS bulk XML coverage) — *not* that the hospital had no MSO.

> **Coverage note.** The IRS hosts bulk XML only for index years ≥ 2017, so ~4% of indexed 990s are unavailable from this source, and the most recent tax years (2024–2025) are thin because of filing lags.

------------------------------------------------------------------------

## Extractors

Extraction is a registry of independent measure groups in `extractors/`. Each one reads `data/input/xml_files/*.xml` and writes its own CSV under `data/extract/`. `pipeline/extract_delegation.py` still runs the delegation group.

```bash
python -m extractors governance    # Governance & Management Measures
python -m extractors delegation    # Part VI Line 3
```

Governance & Management Measures is one row per filing: Part VI lines 1a, 1b, 2, 3, 4, 5, 8a, 8b, 10a, 10b, 11a, 12a–c, 13, 14, 15a, 15b, 16a, and 16b, plus the Schedule O text for line 11b. Lines 10b and 16b are blank when the form did not ask them.

------------------------------------------------------------------------

## The classification step (`classify_mso.py`)

This is the one step that calls an LLM (Claude, via the Anthropic API).

**Each collaborator needs their own Anthropic API key** (a Claude Pro/Max subscription does **not** cover API usage — the API is billed separately, pay-as-you-go; the full run costs only a few dollars). Get a key at <https://console.anthropic.com> → API Keys, then either:

- set an environment variable: `export ANTHROPIC_API_KEY='sk-ant-...'`, **or**
- put the key (just the `sk-ant-...` string) in `anthropic_key.txt` in the repo root. (Useful when running in IDLE, which does not inherit shell environment variables. `anthropic_key.txt` is git-ignored — never commit it.)

The script is resumable (rerun to continue) and writes one labeled row per distinct text to `mso_classified.csv`.

> **Reproducibility note.** LLM labels are not perfectly deterministic, so the **canonical labeled dataset is the included `mso_classified.csv`** — treat it as the dataset of record (model: `claude-opus-4-8`). `classify_mso.py` documents *how* it was produced and lets you re-classify if the taxonomy changes; it is not meant for each collaborator to regenerate their own copy.

------------------------------------------------------------------------

## MSO taxonomy

Every "Yes" Schedule O explanation is coded into one `category`:

| category | meaning | MSO? |
|----|----|----|
| `A_dedicated_MSO` | An **unrelated, third-party** management-services firm manages the hospital (e.g. Quorum Health Resources / Ovation, Community Hospital Corporation, Alliant, HealthTech). | **Yes (target)** |
| `D_peer_system_managed` | Managed by **another, unrelated hospital/health system** (a peer provider, not a dedicated MSO and not the org's own parent). | tracked separately |
| `C_parent_shared_services` | Services from the org's **own parent / sole member / related entity** (internal shared services). | No |
| `B_exec_staffing` | A firm/individual supplies only **one or two named executives** (often interim). | No |
| `E_functional` | Only a **specific function** is outsourced (pharmacy, food, ER, IT, investments…). | No |
| `F_uninformative` | No usable management information. | n/a |

Plus orthogonal fields: `manager_relationship`, `scope`, `manager_name`, `provides_named_executive`, `management_fee_mentioned`, `confidence`.

**`is_mso_affiliation`** is a *derived* flag = `category == "A_dedicated_MSO"`. The panel's `is_mso` / `is_peer_managed` columns follow the same convention. To fold in peer-system management, edit `MSO_CATEGORIES` at the top of `map_to_panel.py` and the category constants in `build_panel.py` together.

### Headline results

- **117 hospitals (EINs)** have a dedicated-MSO affiliation (`A`) in at least one year, across **497 filing-years**.
- **99 hospitals** are peer-system managed (`D`).
- Validation: `mso_classified_pilot.csv` is a 50-text hand-labeled set; the automated labels agreed with it on **94%** of cases (and **100%** on the binary is-it-an-MSO question).
- Reliability: an independent second classification pass (`mso_classified_og.csv`) agreed with the canonical labels on **87%** of distinct texts overall and **95.8%** on the MSO target (`A`). Disagreements concentrate on the inherently fuzzy parent-vs-peer (`C`/`D`) and MSO-vs-staffing (`A`/`B`) boundaries — i.e. the headline MSO finding is robust; the gray areas are the conceptual ones.

------------------------------------------------------------------------

## Data source & provenance

- Hospital crosswalk / geography: Community Benefit Insight (`communitybenefitinsight.org`).
- Form 990 XML: IRS bulk e-file (`apps.irs.gov/pub/epostcard/990/xml/`).
- Classification: Anthropic Claude (`claude-opus-4-8`).
