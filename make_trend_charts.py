"""
Rebuild every trend chart straight from delegation_results.csv.

What comes from where
  delegation_results.csv   -> filings, Line 3 Yes/No flag, Schedule O text, tax year, state,
                              hospital (CCN) list.  EVERY rate, count and timeline is computed
                              from this file.
  mso_classified.csv +     -> taxonomy label (dedicated MSO / peer system / parent ...) and manager
  mso_text_distinct.csv       name for each distinct narrative. These are the pipeline's own
                              classify_mso.py outputs, joined back by text exactly as
                              map_to_panel.py does. The CSV alone has no category column.
  cbi_hospitals.json       -> bed size / rural / teaching flags (used only by the hospital-type chart)

Usage:
  python3 make_trend_charts.py --data-dir <folder with the files above> \
        --csv delegation_results.csv --out-dir trend_charts

Rerun it after the CSV is refreshed and every chart updates.
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Patch, Rectangle

NAVY, PRIMARY, TEAL, GOLD = "#21295C", "#065A82", "#1C7293", "#B8860B"
MUTED, GRID, GRAYL, GOLDL = "#595959", "#E4EAEC", "#EEF3F5", "#E6C766"
YEARS = list(range(2015, 2025))
plt.rcParams["font.family"] = "DejaVu Sans"
CMAP = LinearSegmentedColormap.from_list("nv", ["#F4F8FA", "#9CC3D5", PRIMARY, NAVY])


def clean(ax, grid=True):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color("#BFBFBF")
    ax.tick_params(colors=MUTED, labelsize=9.5)
    if grid:
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)


def norm_text(t):
    t = re.sub(r"^\s*explanation:\s*", "", str(t), flags=re.I)
    return re.sub(r"\s+", " ", t).strip().lower()


def norm_mgr(n):
    s = n.lower()
    if re.search(r"quorum|qhr|ovation", s): return "Quorum Health Resources"
    if "healthtech" in s: return "HealthTech Management"
    if re.search(r"\bchc\b|community hospital corp|community health consult|community hospital consult|community health corp", s):
        return "Community Hospital Corp. (CHC)"
    if "alliant" in s: return "Alliant Management"
    if "cypress" in s: return "Cypress Healthcare"
    if "central ohio orthopedic" in s: return "Central Ohio Orthopedic Mgmt."
    if n.strip() == "": return "Manager not named"
    return "All other named managers"


# --------------------------------------------------------------------------- load + build
def load(data_dir, csv_name):
    d = pd.read_csv(data_dir / csv_name, dtype=str).fillna("")
    d["yr"] = d.tax_year.astype(int)
    # 1. one filing per EIN x tax year (amended returns share the key; higher object_id is later)
    f = d.sort_values("object_id").drop_duplicates(["ein", "yr"], keep="last").copy()

    # 2. attach taxonomy labels by narrative text (same logic as map_to_panel.py)
    dist = pd.read_csv(data_dir / "mso_text_distinct.csv", dtype=str)
    dist["key"] = dist.text.map(norm_text)
    key2id = dict(zip(dist.key, dist.text_id))
    cls = pd.read_csv(data_dir / "mso_classified.csv", dtype=str).fillna("").set_index("text_id")
    f["text_id"] = f.schedule_o_line3_text.map(norm_text).map(key2id)
    f["category"] = f.text_id.map(cls.category).fillna("")
    f["manager_name"] = f.text_id.map(cls.manager_name).fillna("")

    # 3. expand each filing to the hospitals (CCNs) it covers; state from the CSV's states field
    hosp_fallback = {}
    hp = data_dir / "cbi_hospitals.json"
    hosp = pd.DataFrame(json.load(open(hp))) if hp.exists() else pd.DataFrame()
    if len(hosp):
        hosp["pn"] = hosp.medicare_provider_numbers.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6) \
            if "medicare_provider_numbers" in hosp else hosp.medicare_provider_number.astype(str).str.replace(r"\D", "", regex=True).str.zfill(6)
        hosp_fallback = dict(zip(hosp.pn, hosp.state))
    rows, fb = [], 0
    for r in f.itertuples(index=False):
        pns = [x.strip().zfill(6) for x in re.split(r"\s*\|\s*", r.medicare_provider_numbers) if x.strip()]
        sts = [x.strip() for x in re.split(r"\s*\|\s*", r.states) if x.strip()]
        for i, pn in enumerate(pns):
            if len(sts) == len(pns): st = sts[i]
            elif len(sts) == 1: st = sts[0]
            else:
                st = hosp_fallback.get(pn, ""); fb += 1
            rows.append((pn, r.ein, r.yr, r.delegation_indicator == "Yes", r.category, r.manager_name, st))
    h = pd.DataFrame(rows, columns=["pn", "ein", "yr", "yes", "category", "manager_name", "state"])
    h["A"] = h.category == "A_dedicated_MSO"
    h["D"] = h.category == "D_peer_system_managed"
    h["C"] = h.category == "C_parent_shared_services"
    obs = h[h.yr.between(2015, 2024)].copy()
    print(f"[build] {len(d):,} CSV rows -> {len(f):,} filings after de-duplication -> {len(h):,} hospital-years "
          f"({fb} state values taken from the hospital file because the CSV's state list was ambiguous)")
    return d, f, obs, hosp


# --------------------------------------------------------------------------- figures
def fig_rates(obs, out):
    g = obs.groupby("yr").agg(n=("pn", "size"), yes=("yes", "mean"), A=("A", "mean"), D=("D", "mean"), C=("C", "mean"))
    g[["yes", "A", "D", "C"]] *= 100
    print("\n[reconcile] % of observed hospital-years, straight from the CSV:\n", g.round(1).T.to_string())
    fig, ax = plt.subplots(figsize=(12.3, 3.9), dpi=200)
    for k, lab, c, off in [("yes", "Any delegation (Line 3 = Yes)", NAVY, (8, 0)), ("C", "Parent / shared services", MUTED, (8, 0)),
                           ("D", "Peer-system managed", TEAL, (8, 7)), ("A", "Dedicated MSO", GOLD, (8, -8))]:
        ax.plot(g.index, g[k], color=c, linewidth=2.6, marker="o", markersize=5.5, zorder=3)
        ax.annotate(f"{lab}  {g[k].iloc[-1]:.1f}%", (g.index[-1], g[k].iloc[-1]), xytext=off, textcoords="offset points",
                    va="center", fontsize=9.5, color=c, fontweight="bold")
    ax.annotate(f"{g['yes'].iloc[0]:.1f}%", (2015, g["yes"].iloc[0]), xytext=(-6, 0), textcoords="offset points", va="center", ha="right", fontsize=8.5, color=NAVY)
    ax.annotate(f"2015: dedicated MSO {g['A'].iloc[0]:.1f}%", (2015, g["A"].iloc[0]), xytext=(-6, 0), textcoords="offset points", va="center", ha="right", fontsize=8, color=GOLD)
    ax.set_xlim(2012.6, 2027.6); ax.set_ylim(0, 13)
    ax.set_xticks(YEARS); ax.set_xticklabels([f"{y}\nn={int(g.loc[y, 'n']):,}" for y in YEARS], fontsize=8.5)
    ax.set_ylabel("% of observed hospital-years", fontsize=10, color=MUTED)
    ax.set_title("How common is delegation, and to whom?  REAL DATA: delegation_results.csv, 2015\u20132024", fontsize=12, fontweight="bold", color=NAVY, loc="left")
    clean(ax); plt.tight_layout(); plt.savefig(out / "t1_rates_lines.png", dpi=200, facecolor="white"); plt.close()

    # single-line version used on the Management Delegation visual slide
    fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=200)
    ax.plot(g.index, g["A"], color=PRIMARY, linewidth=2.5, marker="o", markersize=6, zorder=3)
    for x, y in zip(g.index, g["A"]):
        ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=9, color=NAVY, fontweight="bold")
    ax.set_ylim(0, 3.5); ax.set_ylabel("Hospitals with a dedicated MSO (%)", fontsize=11, color=MUTED); ax.set_xlabel("Tax Year", fontsize=11, color=MUTED)
    ax.set_title("Management Delegation to an Outside Company\nReal data: delegation_results.csv, 2015\u20132024", fontsize=13, fontweight="bold", color=NAVY, pad=14)
    clean(ax); plt.tight_layout(); plt.savefig(out / "mso_rate_real_chart.png", dpi=200, facecolor="white"); plt.close()


def ein_matrix(obs):
    e = obs.groupby(["ein", "yr"]).agg(yes=("yes", "max"), A=("A", "max")).reset_index()
    e["code"] = np.where(e.A, 3, np.where(e.yes, 2, 1))
    return e.pivot(index="ein", columns="yr", values="code").reindex(columns=YEARS).fillna(0).astype(int)


def fig_events(M, out):
    ever = M[(M == 3).any(axis=1)]
    adopt = {y: 0 for y in YEARS}; ends = {y: 0 for y in YEARS}; first_clean = {}
    for ein, row in M.iterrows():
        for y in YEARS[1:]:
            if row[y] == 3 and row[y - 1] > 0 and row[y - 1] != 3:
                adopt[y] += 1; first_clean.setdefault(ein, y)
            if row[y] > 0 and row[y] != 3 and row[y - 1] == 3:
                ends[y] += 1
    print(f"\n[reconcile] starts={sum(adopt.values())} ends={sum(ends.values())} hospitals that started at least once={len(first_clean)} ever-MSO filers={len(ever)}")
    ys = YEARS[1:]
    fig, ax = plt.subplots(figsize=(6.1, 3.6), dpi=200)
    ax.bar(ys, [adopt[y] for y in ys], color=GOLD, width=0.7, zorder=3, label="Adopted a dedicated MSO")
    ax.bar(ys, [-ends[y] for y in ys], color=TEAL, width=0.7, zorder=3, label="Ended a dedicated MSO")
    for y in ys:
        if adopt[y]: ax.text(y, adopt[y] + 0.4, str(adopt[y]), ha="center", fontsize=8.5, color=GOLD, fontweight="bold")
        if ends[y]: ax.text(y, -ends[y] - 1.3, str(ends[y]), ha="center", fontsize=8.5, color=TEAL, fontweight="bold")
    ax.axhline(0, color="#8C8C8C", linewidth=0.9)
    ax.set_xticks(ys); ax.set_xticklabels([str(y) for y in ys], fontsize=8.5)
    ax.set_ylabel("Hospitals (filers)", fontsize=10, color=MUTED)
    ax.set_title("Starts vs. ends of dedicated-MSO arrangements", fontsize=11, fontweight="bold", color=NAVY, loc="left")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    mx = max(max(adopt.values()), max(ends.values())); ax.set_ylim(-mx - 4, mx + 5)
    clean(ax); plt.tight_layout(); plt.savefig(out / "t2_adopt_exit.png", dpi=200, facecolor="white"); plt.close()

    prevalent = {}
    for ein, row in ever.iterrows():
        nz = [y for y in YEARS if row[y] > 0]
        if row[nz[0]] == 3: prevalent[ein] = nz[0]

    def curve(starts):
        res = {}
        for k in range(6):
            num = den = 0
            for ein, t0 in starts.items():
                t = t0 + k
                if t <= 2024 and M.loc[ein, t] > 0:
                    den += 1; num += int(M.loc[ein, t] == 3)
            if den >= 5: res[k] = (100 * num / den, num, den)
        return res
    cA, cP = curve(first_clean), curve(prevalent)
    print("[reconcile] survival (adopted):", {k: f"{v[1]}/{v[2]}" for k, v in cA.items()})
    fig, ax = plt.subplots(figsize=(6.1, 3.6), dpi=200)
    ax.plot(list(cA), [v[0] for v in cA.values()], color=GOLD, linewidth=2.6, marker="o", markersize=5.5, label=f"Adopted during the window (n={len(first_clean)})", zorder=3)
    ax.plot(list(cP), [v[0] for v in cP.values()], color=NAVY, linewidth=2.6, marker="o", markersize=5.5, label=f"Already in place at first filing (n={len(prevalent)})", zorder=3)
    for k in range(1, 6):
        if k in cA and k in cP:
            a, b = cA[k][0], cP[k][0]
            for v, col, above in [(a, GOLD, a >= b), (b, NAVY, b > a)]:
                ax.annotate(f"{v:.0f}%", (k, v), xytext=(0, 9 if above else -15), textcoords="offset points", ha="center", fontsize=8.3, color=col, fontweight="bold")
    ax.set_ylim(0, 112); ax.set_xticks(range(6)); ax.set_xlabel("Years since first observed with a dedicated MSO", fontsize=9.5, color=MUTED)
    ax.set_ylabel("% still with a dedicated MSO", fontsize=10, color=MUTED)
    ax.set_title("How long do arrangements last?", fontsize=11, fontweight="bold", color=NAVY, loc="left")
    ax.legend(frameon=False, fontsize=8.3, loc="lower left"); clean(ax)
    plt.tight_layout(); plt.savefig(out / "t3_survival.png", dpi=200, facecolor="white"); plt.close()


def fig_swimlane(M, out):
    ever = M[(M == 3).any(axis=1)].copy()
    first = ever.apply(lambda r: next(y for y in YEARS if r[y] == 3), axis=1)
    dur = (ever == 3).sum(axis=1)
    order = pd.DataFrame({"f": first, "d": dur}).sort_values(["f", "d"], ascending=[True, False]).index
    fig, ax = plt.subplots(figsize=(7.4, 5.3), dpi=200)
    ax.imshow(ever.loc[order, YEARS].values, aspect="auto", cmap=ListedColormap([GRAYL, TEAL, "#9BB7C9", GOLD]), vmin=0, vmax=3, interpolation="nearest")
    ax.set_xticks(range(len(YEARS))); ax.set_xticklabels(YEARS, fontsize=8.5); ax.set_yticks([])
    ax.set_ylabel(f"{len(ever)} hospitals (filers) that ever had a dedicated MSO, sorted by first year", fontsize=9, color=MUTED)
    ax.xaxis.tick_top()
    for s in ax.spines.values(): s.set_visible(False)
    ax.legend(handles=[Patch(color=GOLD, label="Dedicated MSO"), Patch(color="#9BB7C9", label="Other delegation"), Patch(color=TEAL, label="No delegation"), Patch(color=GRAYL, label="No filing observed")],
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=4, frameon=False, fontsize=8.5)
    plt.tight_layout(); plt.savefig(out / "t4_swimlane.png", dpi=200, facecolor="white"); plt.close()


def fig_state(obs, out):
    st = obs[obs.A & (obs.state != "")].groupby(["state", "yr"]).pn.nunique().unstack(fill_value=0).reindex(columns=YEARS, fill_value=0)
    st = st.loc[st.sum(axis=1).sort_values(ascending=False).index].head(20)
    print("\n[reconcile] top states by dedicated-MSO hospital-years:", st.sum(axis=1).head(5).to_dict())
    fig, ax = plt.subplots(figsize=(7.6, 5.4), dpi=200)
    ax.imshow(st.values, aspect="auto", cmap=CMAP, vmin=0, vmax=max(st.values.max(), 1))
    ax.set_xticks(range(10)); ax.set_xticklabels(YEARS, fontsize=8.5); ax.set_yticks(range(len(st))); ax.set_yticklabels(st.index, fontsize=8.5)
    ax.xaxis.tick_top()
    for i in range(st.shape[0]):
        for j in range(st.shape[1]):
            v = st.values[i, j]
            if v > 0: ax.text(j, i, str(v), ha="center", va="center", fontsize=7.8, color="white" if v > st.values.max() * 0.5 else NAVY)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("Number of hospitals with a dedicated MSO (top 20 states)", fontsize=9, color=MUTED, labelpad=8)
    plt.tight_layout(); plt.savefig(out / "t5_state_heat.png", dpi=200, facecolor="white"); plt.close()


def fig_type(obs, hosp, out):
    if not len(hosp):
        print("[skip] cbi_hospitals.json not found - hospital-type chart skipped"); return
    o2 = obs.merge(hosp[["pn", "hospital_bed_size", "urban_location_f", "memb_counc_teach_hosps_f"]].drop_duplicates("pn"), on="pn", how="left")
    segs = [("<100 beds", o2.hospital_bed_size == "<100 beds"), ("100\u2013299 beds", o2.hospital_bed_size == "100-299 beds"), (">299 beds", o2.hospital_bed_size == ">299 beds"),
            ("Rural", o2.urban_location_f == "N"), ("Urban", o2.urban_location_f == "Y"),
            ("Teaching (COTH)", o2.memb_counc_teach_hosps_f == "Y"), ("Non-teaching", o2.memb_counc_teach_hosps_f == "N")]
    R = np.full((len(segs), 10), np.nan)
    for i, (lab, mask) in enumerate(segs):
        sub = o2[mask]
        for j, y in enumerate(YEARS):
            s = sub[sub.yr == y]
            if len(s) >= 30: R[i, j] = 100 * s.A.mean()
        print(f"[reconcile] {lab}: {100 * o2[mask].A.mean():.2f}% of hospital-years")
    fig, ax = plt.subplots(figsize=(12.3, 3.6), dpi=200)
    ax.imshow(np.nan_to_num(R), aspect="auto", cmap=CMAP, vmin=0, vmax=np.nanmax(R))
    ax.set_xticks(range(10)); ax.set_xticklabels(YEARS, fontsize=9); ax.set_yticks(range(len(segs))); ax.set_yticklabels([s[0] for s in segs], fontsize=9.5)
    ax.xaxis.tick_top()
    for i in range(len(segs)):
        for j in range(10):
            if not np.isnan(R[i, j]): ax.text(j, i, f"{R[i, j]:.1f}%", ha="center", va="center", fontsize=8.5, color="white" if R[i, j] > np.nanmax(R) * 0.5 else NAVY)
    for yl in (2.5, 4.5): ax.axhline(yl, color="white", linewidth=4)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("% of observed hospital-years with a dedicated MSO (groups overlap; cells with fewer than 30 hospital-years left blank)", fontsize=9, color=MUTED, labelpad=8)
    plt.tight_layout(); plt.savefig(out / "t6_type_heat.png", dpi=200, facecolor="white"); plt.close()


def fig_managers(obs, out):
    A = obs[obs.A].copy(); A["mgr"] = A.manager_name.apply(norm_mgr)
    order = ["Quorum Health Resources", "HealthTech Management", "Cypress Healthcare", "Community Hospital Corp. (CHC)", "Alliant Management",
             "Central Ohio Orthopedic Mgmt.", "All other named managers", "Manager not named"]
    mm = A.groupby(["mgr", "yr"]).pn.nunique().unstack(fill_value=0).reindex(index=order, columns=YEARS, fill_value=0)
    print("\n[reconcile] hospitals per manager by year:\n", mm.to_string())
    fig, ax = plt.subplots(figsize=(12.3, 3.7), dpi=200)
    ax.imshow(mm.values, aspect="auto", cmap=CMAP, vmin=0, vmax=mm.values.max())
    ax.set_xticks(range(10)); ax.set_xticklabels(YEARS, fontsize=9); ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontsize=9.5)
    ax.xaxis.tick_top()
    for i in range(mm.shape[0]):
        for j in range(10):
            v = mm.values[i, j]
            if v > 0: ax.text(j, i, str(v), ha="center", va="center", fontsize=9, color="white" if v > mm.values.max() * 0.5 else NAVY)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("Number of hospitals managed (dedicated-MSO category; name variants merged)", fontsize=9, color=MUTED, labelpad=8)
    plt.tight_layout(); plt.savefig(out / "t7_manager_heat.png", dpi=200, facecolor="white"); plt.close()


def fig_exec(f, out):
    y_ = f[(f.delegation_indicator == "Yes") & (f.text_status == "text_found") & f.yr.between(2015, 2024)].copy()
    ceo = re.compile(r"\b(CEO|C\.E\.O|Chief Executive|President|Administrator|Executive Director)\b", re.I)
    cfo = re.compile(r"\b(CFO|Chief Financial)\b", re.I)
    y_["ceo"] = y_.schedule_o_line3_text.apply(lambda t: bool(ceo.search(t)))
    y_["cfo"] = y_.schedule_o_line3_text.apply(lambda t: bool(cfo.search(t)))
    allr = y_.groupby("yr").agg(n=("ceo", "size"), ceo=("ceo", "mean"), cfo=("cfo", "mean"))
    Ar = y_[y_.category == "A_dedicated_MSO"].groupby("yr").agg(n=("ceo", "size"), ceo=("ceo", "mean"), cfo=("cfo", "mean"))
    anyt = (y_.ceo | y_.cfo)
    print(f"\n[reconcile] narratives naming a CEO-type or CFO title: {int(anyt.sum())} of {len(y_)} ({100*anyt.mean():.0f}%), 2015-2024; "
          f"at {y_[anyt].ein.nunique()} of {y_.ein.nunique()} filers with a Line 3 narrative")
    print("[reconcile] all narratives, % naming CEO-type / CFO title:\n", (allr[["ceo", "cfo"]] * 100).round(1).join(allr.n).T.to_string())
    print("[reconcile] dedicated-MSO narratives:\n", (Ar[["ceo", "cfo"]] * 100).round(1).join(Ar.n).T.to_string())
    print("[reconcile] dedicated-MSO CEO-type share range:", f"{Ar.ceo.min()*100:.0f}-{Ar.ceo.max()*100:.0f}%", "| CFO:", f"{Ar.cfo.min()*100:.0f}-{Ar.cfo.max()*100:.0f}%")
    fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=200)
    ax.plot(Ar.index, Ar.ceo * 100, color=GOLD, linewidth=2.6, marker="o", markersize=5.5, label="Dedicated MSO: names a CEO / president / administrator")
    ax.plot(Ar.index, Ar.cfo * 100, color=TEAL, linewidth=2.6, marker="o", markersize=5.5, label="Dedicated MSO: names a CFO")
    ax.plot(allr.index, allr.ceo * 100, color=NAVY, linewidth=2.0, linestyle="--", marker="o", markersize=4, label="All delegation narratives: names a CEO-type title")
    ax.set_ylim(0, 100); ax.set_xticks(YEARS)
    ax.set_xticklabels([f"{y}\nn={int(Ar.loc[y, 'n'])}" if y in Ar.index else str(y) for y in YEARS], fontsize=8)
    ax.set_ylabel("% of Schedule O narratives", fontsize=10, color=MUTED)
    ax.set_title("Do the narratives name the people in charge?", fontsize=11.5, fontweight="bold", color=NAVY, loc="left")
    ax.legend(frameon=False, fontsize=8.3, loc="lower left"); clean(ax)
    plt.tight_layout(); plt.savefig(out / "t8_exec_mentions.png", dpi=200, facecolor="white"); plt.close()


def example_hospital(f, out, ein="030266986"):
    """Case study for one hospital. Rows 1-2 come from the CSV; row 3 is hand-read from Form 990 Part VI."""
    h = f[f.ein == ein].set_index("yr")
    status = {y: (h.loc[y, "delegation_indicator"] if y in h.index else None) for y in YEARS}
    text = {y: (h.loc[y, "schedule_o_line3_text"] if y in h.index else "") for y in YEARS}
    print(f"\n[example] {h.taxpayer_name.iloc[0]}: ", {y: s for y, s in status.items()})
    # Row-2 labels are read from the Schedule O text in the CSV; assert the names really appear there.
    for y in YEARS:
        if status[y] == "Yes":
            assert "Bowen" in text[y], f"expected CEO name in {y} narrative"
    assert "Barbini" in text[2019], "expected interim CEO in 2019 narrative"
    print("[example] verified in CSV text: 'Bowen' in 2015/16/17/19 narratives; 'Barbini' in 2019")

    def cell(ax, x, y, w, hh, fc, t="", tc="white", fs=9, hatch=None, ec="white", ls="-", bold=False):
        ax.add_patch(Rectangle((x, y), w, hh, facecolor=fc, edgecolor=ec, linewidth=1.6, hatch=hatch, linestyle=ls))
        if t: ax.text(x + w / 2, y + hh / 2, t, ha="center", va="center", fontsize=fs, color=tc, fontweight="bold" if bold else "normal", linespacing=1.15)

    # ---- strip
    fig, ax = plt.subplots(figsize=(8.2, 2.8), dpi=200)
    ax.set_xlim(0, 10.2); ax.set_ylim(0, 3.4); ax.axis("off")
    for i, yr in enumerate(YEARS):
        ax.text(i + 0.6, 2.95, str(yr), ha="center", va="center", fontsize=9.5, color=NAVY, fontweight="bold")
        s = status[yr]
        if s == "Yes": cell(ax, i + 0.1, 1.35, 1, 1.25, GOLD, "Yes", fs=11, bold=True)
        elif s == "No": cell(ax, i + 0.1, 1.35, 1, 1.25, TEAL, "No", fs=11, bold=True)
        else: cell(ax, i + 0.1, 1.35, 1, 1.25, GRAYL, "no\nfiling", tc="#8C8C8C", fs=7.5, hatch="////", ec="#C9D3D8")
    ax.text(0.1, 0.8, "Part VI, Line 3: \u201cDid the organization delegate control over management duties \u2026 to a management company?\u201d", fontsize=8.6, color=MUTED, ha="left", va="center")
    mgr = f[(f.ein == ein) & (f.category == "A_dedicated_MSO")].manager_name.iloc[0]
    ax.text(0.1, 0.35, f"Manager named in Schedule O: {mgr}  (our classifier: dedicated MSO)", fontsize=9, color=GOLD, fontweight="bold", ha="left", va="center")
    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    plt.savefig(out / "nmc_delegation_strip_real.png", dpi=200, facecolor="white"); plt.close()

    # ---- case study
    board = {2015: ("100%", "12 of 12"), 2019: ("91%", "10 of 11")}   # hand-read from the filings, not in the CSV
    fig, ax = plt.subplots(figsize=(12.3, 5.0), dpi=200)
    ax.set_xlim(0, 13.1); ax.set_ylim(0, 6.7); ax.axis("off")
    X0, H = 3.1, 1.3
    for i, yr in enumerate(YEARS):
        ax.text(X0 + i + 0.5, 5.8, str(yr), ha="center", va="center", fontsize=11, color=NAVY, fontweight="bold")
    for (yy, t, s) in [(4.05, "1. Management delegated?", "Part VI, Line 3  (from CSV)"), (2.45, "2. Who ran the hospital?", "named in Schedule O  (from CSV)"),
                       (0.85, "3. Board independence", "Part VI, lines 1b \u00f7 1a  (from filings)")]:
        ax.text(0.05, yy + 0.95, t, ha="left", va="center", fontsize=11.5, color=NAVY, fontweight="bold")
        ax.text(0.05, yy + 0.55, s, ha="left", va="center", fontsize=9, color=MUTED)
    for i, yr in enumerate(YEARS):
        s = status[yr]; x = X0 + i
        if s == "Yes": cell(ax, x, 4.05, 1, H, GOLD, "Yes", fs=11, bold=True)
        elif s == "No": cell(ax, x, 4.05, 1, H, TEAL, "No", fs=11, bold=True)
        else: cell(ax, x, 4.05, 1, H, GRAYL, "no filing\nin corpus", tc="#8C8C8C", fs=8, hatch="////", ec="#C9D3D8")
    i = 0
    while i < len(YEARS):
        yr, x = YEARS[i], X0 + i
        t, s = text[yr], status[yr]
        if s == "Yes" and "Barbini" in t:
            cell(ax, x, 2.45, 0.5, H, GOLDL, "Bowen\nto May\n2020", tc="#1A1A1A", fs=6.6, bold=True)
            cell(ax, x + 0.5, 2.45, 0.5, H, "#D9A441", "Barbini\ninterim\nCEO", tc="#1A1A1A", fs=6.6, bold=True); i += 1
        elif s == "Yes" and "Bowen" in t:
            j = i
            while j + 1 < len(YEARS) and status[YEARS[j + 1]] == "Yes" and "Bowen" in text[YEARS[j + 1]] and "Barbini" not in text[YEARS[j + 1]]: j += 1
            cell(ax, x, 2.45, j - i + 1, H, GOLDL, "CEO Jill Berry Bowen\n(employee of Quorum\nHealth Resources)", tc="#1A1A1A", fs=9.5, bold=True); i = j + 1
        elif s is None:
            cell(ax, x, 2.45, 1, H, GRAYL, "no filing\nin corpus", tc="#8C8C8C", fs=8, hatch="////", ec="#C9D3D8"); i += 1
        else:
            cell(ax, x, 2.45, 1, H, GRAYL, "not named\n(Line 3 = No)", tc="#6B7B84", fs=8); i += 1
    for i, yr in enumerate(YEARS):
        x = X0 + i
        if yr in board: cell(ax, x, 0.85, 1, H, NAVY, f"{board[yr][0]}\n{board[yr][1]}", fs=10.5, bold=True)
        else: cell(ax, x, 0.85, 1, H, "white", "not yet\nextracted", tc="#8C8C8C", fs=8, ec="#AAB7BE", ls="--")
    ax.text(0.05, 6.4, f"{h.taxpayer_name.iloc[0].title()} (St. Albans, VT)  \u2014  REAL DATA from its Form 990 filings", ha="left", va="center", fontsize=13.5, color=NAVY, fontweight="bold")
    ax.text(0.05, 0.3, "Tax year = year the fiscal year begins (2019 = Oct 2019\u2013Sep 2020).  Gold = delegated to Quorum Health Resources;  teal = not delegated;  hatched = no filing observed in the CSV.",
            ha="left", va="center", fontsize=8.6, color=MUTED)
    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    plt.savefig(out / "nmc_case_study_real.png", dpi=200, facecolor="white"); plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=".", help="folder containing the CSV/JSON inputs")
    ap.add_argument("--csv", default="delegation_results.csv")
    ap.add_argument("--out-dir", default="trend_charts")
    a = ap.parse_args()
    data_dir, out = Path(a.data_dir), Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d, f, obs, hosp = load(data_dir, a.csv)
    fig_rates(obs, out)
    M = ein_matrix(obs)
    fig_events(M, out); fig_swimlane(M, out)
    fig_state(obs, out); fig_type(obs, hosp, out); fig_managers(obs, out); fig_exec(f, out)
    example_hospital(f, out)
    print(f"\nDone. Charts written to {out.resolve()}")


if __name__ == "__main__":
    main()
