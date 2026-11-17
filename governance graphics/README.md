# Governance graphics pipeline (Form 990 Explorer)

`governance_management_measures.csv`  →  `governance_dashboard_data.json`  →  `governance_dashboard.html`

| File | Role |
|---|---|
| `build_governance_web.py` | Main pipeline. Cleans the CSV, computes the numbers for the three graphics, writes the JSON, and assembles the HTML. |
| `governance_dashboard_template.html` | The page. Contains the placeholder `__DATA__`, which the pipeline replaces with the JSON. |
| `make_graphic_previews.py` | Draws static PNG copies of the three graphics from the JSON, for slides and write-ups. |
| `output/` | Results: the original dashboard + JSON, the full-names version, and `previews/`. |

## Run it
```bash
pip install pandas matplotlib
python3 build_governance_web.py                       # reads governance_management_measures.csv next to the script
python3 make_graphic_previews.py                      # PNGs in output/previews/
```
Useful options:
```bash
python3 build_governance_web.py --csv path/to/governance_management_measures.csv --out-dir output
python3 build_governance_web.py --names-csv delegation_results.csv     # restore full names (see write-up, issue 1)
python3 build_governance_web.py --json-in output/governance_dashboard_data.json   # rebuild only the HTML
python3 make_graphic_previews.py --ein 030266986      # graphic 3 for a different organization
```
Re-run after the dataset is refreshed and every graphic updates.

## Required CSV columns
`tax_year, ein, tax_period, object_id, organization_name, line_3_management_delegation, line_16a_investment_in_joint_venture, line_4_governing_document_changes, line_1a_voting_members, line_1b_independent_members`
The script stops with a clear message if any are missing.

## What the script does (4 steps)
1. **Load and clean.** Keep tax years 2015–2024; keep one filing per EIN and tax year (latest tax period, then latest object ID); pad EINs to 9 digits.
2. **Convert.** Yes/No text → 1/0 (anything else is missing). Board independence = line 1b ÷ line 1a × 100, only when 1a > 0 and 0 ≤ 1b ≤ 1a.
3. **Aggregate.** For each year: share answering Yes to Line 3 and to Line 16a, and mean board independence for Line 3 = Yes vs. No. For each organization with at least two observed years: its yearly values (the lookup).
4. **Write.** JSON with the numbers, then HTML = template + JSON.

It prints a data-quality summary each run (rows kept, % missing per measure, % without a valid board count).
