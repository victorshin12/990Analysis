# Form 990 Explorer — Governance Graphics: Write-Up and Pipeline

Three descriptive graphics built from structured Part VI items already in the Explorer dataset. Numbers below come from `governance_dashboard_data.json` (18,901 filings, tax years 2015–2024, one filing per EIN and tax year).

## 1. Scope check

**Why these three are in scope.** Each graphic uses only data already in the Explorer, four structured Part VI items, and arithmetic a student can follow. Nothing needs text classification, another schedule, or another dataset.

| Scope question | Answer |
|---|---|
| Which 990 items? | Part VI: Line 1a, Line 1b, Line 3, Line 4, Line 16a |
| Is the form's answer the measure? | Yes. Every item is a Yes/No box or a number. No narrative is read. |
| What processing is done? | Yes/No → 1/0; 1b ÷ 1a; yearly shares and averages |
| Other data or models? | None (no LLM labels, no outside files) |
| What do the graphics claim? | Descriptions of what filers reported. No causal claims, and no claim about acquisitions or consolidation. |

**Parked, because it goes beyond this scope:** hospital-level event studies, the classifier categories (dedicated MSO vs. parent vs. peer system), the Schedule R / H / J measures, named executives, state and hospital-type heat maps, and anything about tunneling. These are future work only if the PI wants them.

**One sentence for the PI:** "The governance section describes four structured Part VI responses over time, for all filers, and for one selected filer, using only the Explorer's own data and simple arithmetic."

## 2. The three graphics at a glance

| # | Section title | Question it answers | Form items | Type of chart |
|---|---|---|---|---|
| 1 | Management delegation and joint ventures | How often do filers report each arrangement, and is it changing? | Line 3, Line 16a | Two-line chart by year |
| 2 | Board independence by management delegation | Are boards more or less independent where management is delegated? | Lines 1a, 1b, Line 3 | Two-line chart by year |
| 3 | Organization governance history | What did one filer report each year? | Lines 3, 16a, 4, 1a/1b | Selectable year-by-measure grid |

## 3. Graphic 1 — Management delegation and joint ventures

**What it shows.** The percentage of filings answering Yes to two questions, each year from 2015 to 2024.

**Form items (as worded on the form).**
- Line 3: "Did the organization delegate control over management duties customarily performed by or under the direct supervision of officers, directors, trustees, or key employees to a management company or other person?"
- Line 16a: whether the organization invested in, contributed assets to, or participated in a joint venture or similar arrangement with a taxable entity during the year.

**How it is computed.** For each year: filings answering Yes ÷ filings with a Yes/No answer. Both items are Yes/No on the form, so the response is the measure.

**What the real numbers show.**
- Management delegation: 13.5% of filings in 2015, 11.1% in 2024 (range 11.1%–13.5%), drifting down slightly.
- Joint ventures: 35.6% in 2015, 34.5% in 2024 (range 33.4%–35.6%), essentially flat. About one filing in three answers Yes.
- Joint ventures are about 2.5 to 3.1 times as common as management delegation, depending on the year.

**Why it is useful.** It shows two reported arrangements side by side and gives a baseline for how common each is, before looking at any single organization.

**What it does not show.** Neither answer measures consolidation or acquisition. A Yes to Line 3 says management duties were delegated; it does not say to whom or why. Line 16a covers only joint ventures with a taxable entity.

**Caution.** The number of filings changes by year (1,294 in 2015, about 2,100–2,200 in 2020–2023, 1,688 in 2024), so compare shares rather than counts, and keep the n visible.

## 4. Graphic 2 — Board independence by management delegation

**What it shows.** The average percentage of voting board members who are independent, split into filings that answered Yes and No to Line 3, by year.

**Form items.** Line 1a: "Enter the number of voting members of the governing body at the end of the tax year." Line 1b: "Enter the number of voting members included in line 1a, above, who are independent."

**How it is computed.** Independence = line 1b ÷ line 1a × 100 for each filing, counted only when 1a > 0 and 0 ≤ 1b ≤ 1a. Each point is the simple average across filings in that group and year (not weighted by board size).

**What the real numbers show.**
- Filings answering Yes to Line 3 have a higher average independence in 9 of 10 years, by 2.0 to 3.6 percentage points. 2018 is the exception (0.3 points lower).
- Both groups drift down over the decade: Yes 80.5% → 76.8%, No 77.4% → 74.6%.
- The groups are very different in size: about 175–270 filings answer Yes each year, versus roughly 1,100–1,900 answering No.

**Why it is useful.** It connects two governance measures within the same groups of filers.

**What it does not show.** Board independence is not a direct measure of oversight quality, and the differences are small and descriptive. The Yes and No groups may differ in other ways (for example, in the types or sizes of organizations), and the page makes no causal claim.

**Cautions.** (a) The y-axis starts at 60%, which makes small differences look larger; the PNG preview carries a note, and the site should too. (b) Show each group's n, since the Yes group is much smaller.

## 5. Graphic 3 — Organization governance history

**What it shows.** Choose one filing organization and see, year by year: Line 3 (Yes/No), Line 16a (Yes/No), Line 4 (Yes/No), and board independence (%). Gold is Yes, teal is No, gray is missing, blue is a valid percentage.

**Form items.** Line 3, Line 16a, Line 4 ("Did the organization make any significant changes to its governing documents since the prior Form 990 was filed?"), and Lines 1a/1b.

**How it is computed.** One row of values per filing, shown as filed. There is no averaging or scoring across measures.

**Worked example: Northwestern Medical Center (EIN 030266986).**
- Line 3 is Yes for 2015, 2016, 2017 and 2019, then No for 2020–2023. There is no filing for 2018 or 2024 in the extract.
- Line 16a and Line 4 are No in every observed year.
- Board independence: 100% (2015–2017), 90.9% (2019), 81.8% (2020), 90.9% (2021), 100% (2022), 90.9% (2023).
- These values match the filings I read by hand earlier (12 of 12 in the 2015 filing; 10 of 11 in the 2019 filing).

**Why it is useful.** It shows several governance items for the same filer without combining unrelated variables into one score.

**What it does not show.** An EIN is a filing organization, which may not correspond to a single hospital, and the grid is not a history of acquisitions. Gray cells mean "missing or no filing," not "No."

**Coverage.** The lookup lists the 2,276 organizations with at least two observed years; 1,925 of them have eight or more.

## 6. How the numbers are built (pipeline)

See `README.md` for commands. In short: `governance_management_measures.csv` → clean (2015–2024, one filing per EIN and tax year, 9-digit EINs) → convert Yes/No to 1/0 and compute 1b ÷ 1a → aggregate by year and by organization → write the JSON → assemble the HTML from the template. `make_graphic_previews.py` redraws the three graphics as PNGs from the same JSON.

## 7. Checks run

- **Rebuild reproduces the page.** The new script, run on the uploaded JSON and template, produces a dashboard HTML that is byte-for-byte identical to the one uploaded.
- **Same results as the original script.** On identical synthetic data containing amended returns, mixed capitalization and invalid board counts, the new script and the original produce identical JSON.
- **Graphic 1 matches the team's own CSV.** Rebuilding the delegation counts from `delegation_results.csv` gives the same number of filings and the same number of Yes answers in all 10 years.
- **The page works.** In a headless browser the page draws both charts (two lines, 20 points each), the name and EIN search finds organizations, and the timeline shows the Northwestern values above.
- **Internal consistency.** Annual filings sum to 18,901, and group counts never exceed totals.

**Not checked:** Line 16a, Line 4 and board-independence values against the raw dataset, because `governance_management_measures.csv` was not available to me. The live site also blocks automated access, so I did not view it.

## 8. Issues and suggested fixes (most important first)

1. **Some organization names are cut off (258 of 2,276 = 11.3%).** The names come from the first name line only, e.g. "AITKIN COMMUNITY HOSPITAL DBA" (full: "… DBA RIVERWOOD HEALTHCARE CENTER") and "ALBANY MEDICAL CENTER GROUP" (full: "… GROUP ORGANIZATION"). This hurts the search: typing "riverwood" finds nothing in the current page. **Fix:** run with `--names-csv delegation_results.csv`, which restores the full name from the IRS index when it begins with the XML name. A rebuilt page (`governance_dashboard_fixed_names.html`) is included; after the fix, the same search finds the hospital.
2. **Graphic 2's axis starts at 60%.** Either add a visible note (as the preview has) or start the axis at 0, and show each group's n under the axis.
3. **Counts per year vary.** Show n under each year (the previews do) so a dip in one year isn't read as a trend.
4. **Numbers differ from the earlier slides.** The Explorer counts filings (one per EIN and year); the earlier slides counted hospital-years (one per hospital, so a filing covering several hospitals counts several times). For example, delegation is 13.5% of filings in 2015, versus 10.5% of hospital-years. Use the Explorer's numbers on the site and say which unit is used.
5. **The lookup omits single-year organizations.** The page says so; mention it in the notes.

## 9. Files

`build_governance_web.py`, `make_graphic_previews.py`, `governance_dashboard_template.html`, `README.md`, and `output/` (original dashboard and JSON, full-names version, three preview PNGs).
