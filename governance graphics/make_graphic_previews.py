#!/usr/bin/env python3
"""
make_graphic_previews.py -- static PNG versions of the three Form 990 Explorer governance graphics,
drawn from governance_dashboard_data.json (the same numbers the website uses), for slides and write-ups.

    python3 make_graphic_previews.py
    python3 make_graphic_previews.py --ein 030266986 --out-dir previews
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parent
BLUE, TEAL, GOLD, INK, MUTED, GRID = "#2456a5", "#14867d", "#b97519", "#14243a", "#627187", "#e2e8f0"
plt.rcParams["font.family"] = "DejaVu Sans"
YEARS = list(range(2015, 2025))


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c8d2df")
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.grid(axis="y", color=GRID, linewidth=0.9)
    ax.set_axisbelow(True)


def line_graphic(annual, series, ylim, ticks, title, subtitle, ylabel, out, note=None, tick=None, height=4.4):
    fig, ax = plt.subplots(figsize=(10, height), dpi=200)
    for label, color, getter, nget in series:
        ys = [getter(r) for r in annual]
        ax.plot(YEARS, ys, color=color, linewidth=2.8, marker="o", markersize=6.5, markeredgecolor="white", markeredgewidth=1.3, label=label, zorder=3)
        ax.annotate(f"{ys[0]:.1f}%", (YEARS[0], ys[0]), xytext=(-8, 0), textcoords="offset points", ha="right", va="center", fontsize=8.5, color=color)
        ax.annotate(f"{ys[-1]:.1f}%", (YEARS[-1], ys[-1]), xytext=(8, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5, color=color)
    ax.set_xlim(2014.2, 2024.8); ax.set_ylim(*ylim); ax.set_yticks(ticks); ax.set_yticklabels([f"{t}%" for t in ticks])
    ax.set_xticks(YEARS)
    ax.set_xticklabels([(tick(r) if tick else f"{r['year']}\nn={series[0][3](r):,}") for r in annual], fontsize=8.3)
    ax.set_ylabel(ylabel, fontsize=10, color=MUTED)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=24)
    ax.text(0, 1.04, subtitle, transform=ax.transAxes, fontsize=9.5, color=MUTED)
    ax.legend(frameon=False, fontsize=9.5, loc="lower left", ncol=2)
    style(ax)
    if note:
        fig.text(0.01, 0.01, note, fontsize=8, color=MUTED, style="italic")
    plt.tight_layout(rect=(0, 0.03, 1, 1)); plt.savefig(out, facecolor="white"); plt.close()


def timeline_graphic(org, out):
    rows = [("delegation", "Management delegation"), ("jointventure", "Joint-venture investment"), ("documents", "Governing docs changed"), ("independence", "Board independence")]
    by_year = {r["year"]: r for r in org["records"]}
    fig, ax = plt.subplots(figsize=(10, 3.6), dpi=200)
    ax.set_xlim(0, 12.6); ax.set_ylim(0, 6.2); ax.axis("off")
    X0, W, H, GAP = 2.6, 0.97, 0.78, 0.07
    for i, y in enumerate(YEARS):
        ax.text(X0 + i + W / 2, 5.5, str(y), ha="center", va="center", fontsize=9, color=MUTED, fontweight="bold")
    for j, (key, label) in enumerate(rows):
        yy = 4.3 - j * (H + 0.45)
        ax.add_patch(Rectangle((0, yy), X0 - 0.15, H, facecolor="#f3f6fa", edgecolor="none"))
        ax.text(0.12, yy + H / 2, label, va="center", fontsize=9, fontweight="bold", color=INK)
        for i, y in enumerate(YEARS):
            v = by_year.get(y, {}).get(key)
            if v is None: fc, tc, t = "#e9edf2", "#788497", "\u2014"
            elif key == "independence": fc, tc, t = "#eaf1ff", "#204d93", f"{v:.1f}%"
            elif v: fc, tc, t = "#e7b668", "#593708", "Yes"
            else: fc, tc, t = "#b9e2dd", "#115b55", "No"
            ax.add_patch(Rectangle((X0 + i, yy), W, H, facecolor=fc, edgecolor="none"))
            ax.text(X0 + i + W / 2, yy + H / 2, t, ha="center", va="center", fontsize=8.5, color=tc, fontweight="bold")
    ax.text(0, 6.05, f"{org['name']}  \u00b7  EIN {org['ein']}", fontsize=12, fontweight="bold", color=INK, va="center")
    ax.text(0, 0.1, "Gold = Yes   Teal = No   Gray = missing or no filing   Blue = valid board-independence %", fontsize=8.3, color=MUTED, va="center")
    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    plt.savefig(out, facecolor="white"); plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ROOT / "output" / "governance_dashboard_data.json"))
    ap.add_argument("--ein", default="030266986", help="organization for graphic 3 (default: Northwestern Medical Center)")
    ap.add_argument("--out-dir", default=str(ROOT / "output" / "previews"))
    a = ap.parse_args()
    data = json.loads(Path(a.json).read_text()); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    annual = data["annual"]

    line_graphic(annual,
        [("Management delegation (Part VI, Line 3)", BLUE, lambda r: r["delegation"]["rate"], lambda r: r["filings"]),
         ("Joint-venture investment (Part VI, Line 16a)", TEAL, lambda r: r["jointventure"]["rate"], lambda r: r["filings"])],
        (0, 50), [0, 10, 20, 30, 40, 50], "Management delegation and joint ventures",
        "Share of filings answering Yes, by tax year (n = filings that year)", "% of filings answering Yes", out / "graphic1_delegation_and_joint_ventures.png")

    line_graphic(annual,
        [("Delegation = Yes", BLUE, lambda r: r["independence_yes"]["mean"], lambda r: r["filings"]),
         ("Delegation = No", GOLD, lambda r: r["independence_no"]["mean"], lambda r: r["filings"])],
        (60, 90), [60, 65, 70, 75, 80, 85, 90], "Board independence by management delegation",
        "Mean % of voting board members who are independent (n = filings with a valid board count, per group)", "Mean independent board members (%)",
        out / "graphic2_board_independence_by_delegation.png", note="Note: the y-axis starts at 60%, which magnifies small differences. Descriptive only; no causal claim.",
        tick=lambda r: f"{r['year']}\nYes n={r['independence_yes']['valid']:,}\nNo n={r['independence_no']['valid']:,}", height=4.9)

    org = next((o for o in data["organizations"] if o["ein"] == a.ein), None) or next(o for o in data["organizations"] if len(o["records"]) >= 9)
    timeline_graphic(org, out / "graphic3_organization_governance_history.png")
    print("wrote", sorted(p.name for p in out.glob("*.png")), "| graphic 3 organization:", org["name"])


if __name__ == "__main__":
    main()
