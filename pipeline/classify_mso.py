"""
Classify the distinct Schedule O "delegation of management duties" explanations
into the MSO taxonomy, using Claude (Anthropic API).

Reads:  mso_text_distinct.csv  (1 row per distinct explanation text)
Writes: mso_classified.csv      (adds the taxonomy fields; resumable)

Each text is classified into orthogonal fields (see SCHEMA below). The derived
flag is_mso_affiliation = (category == "A_dedicated_MSO"); change that one line
if you later decide to fold in D_peer_system_managed.

Setup (Terminal):
    pip3 install anthropic pandas
    export ANTHROPIC_API_KEY='sk-ant-...'      # from console.anthropic.com
    python3 classify_mso.py

Setup (IDLE) — IDLE does NOT see env vars exported in a terminal, so instead:
    1. Install the SDK into IDLE's own Python. In the IDLE shell (>>>), run once:
           import subprocess, sys
           subprocess.run([sys.executable, "-m", "pip", "install", "anthropic"])
    2. Paste your key (just the sk-ant-... string) into a file named
       anthropic_key.txt in this folder (next to this script)
    3. Open this file in IDLE and press F5 (Run).

The script is resumable: rerun it and it skips text_ids already in
mso_classified.csv, so an interruption is safe.
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd
import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CLASSIFY, KEY_FILE


INPUT_FILE = CLASSIFY / "mso_text_distinct.csv"
OUTPUT_FILE = CLASSIFY / "mso_classified.csv"

MODEL = "claude-opus-4-8"


def resolve_api_key():
    """Env var first; otherwise read it from KEY_FILE (works when run in IDLE)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            return key
    raise SystemExit(
        f"No API key found. Put your key in {KEY_FILE} (just the sk-ant-... string), "
        "or set the ANTHROPIC_API_KEY environment variable."
    )


# Classification instructions (the taxonomy). Cached across requests so we only
# pay to process it once.
SYSTEM_PROMPT = """You classify free-text explanations from IRS Form 990 Schedule O, \
written in response to Part VI, Section A, Line 3 ("Did the organization delegate control over \
management duties... to a management company or other person?"). Each text is from a nonprofit \
hospital. Classify ONE text into the schema fields.

Definitions for `category`:
- A_dedicated_MSO: an UNRELATED, third-party management-services company manages the hospital \
(broad operations and/or provides the C-suite under a management agreement / fee). Examples of such \
firms: Quorum Health Resources (QHR) / Ovation Healthcare, Community Hospital Corporation (CHC), \
Alliant Management Services, HealthTech Management Services, Alecto. THIS IS THE TARGET CATEGORY.
- D_peer_system_managed: management is provided by ANOTHER, UNRELATED HOSPITAL or HEALTH SYSTEM \
(a peer provider, not a dedicated management-services firm and not the org's own parent) — e.g. a \
larger regional hospital supplies the CEO under a management fee. Distinct from A.
- C_parent_shared_services: management/administrative services come from the org's OWN parent, \
sole member, or a related/affiliated entity within the same system (centralized/shared services). \
Look for "parent", "sole member", "related organization", "supporting organization", "affiliate", \
"sister organization".
- E_functional: only a specific function or department is outsourced (e.g. investments, pharmacy, \
ER, food/dietary, environmental services, wound care, IT) — not whole-hospital management.
- B_exec_staffing: a firm or individual supplies one or two named executives only (often interim), \
e.g. an interim CFO via a staffing/consulting/accounting firm, with no broader management role.
- F_uninformative: the text gives no usable management info (vague boilerplate like "per the \
by-laws", or text that is actually about something else such as board composition).

Guidance:
- "unrelated" vs "related/parent" is usually stated explicitly in the text — use it.
- A management FEE plus another distinct company managing operations or providing the CEO/CFO points \
to A (if a dedicated mgmt firm) or D (if another hospital/system).
- A single interim/contract executive via a professional firm is B, not A, even if called a \
"management services contract".
- An owner-operated management company (the hospital's own CEO owns the LLC) is a captive arrangement \
— classify as A but mark confidence medium and note it in manager_name.

`manager_relationship`: unrelated_mso | unrelated_peer | related_parent | individual_or_firm | unclear
`scope`: organization_wide | executive_only | specific_function | governance_only | unclear
`manager_name`: the managing entity's name as written (or "" if none/uninformative).
`provides_named_executive`: true if the text says the manager supplies a named CEO/CFO/COO/etc.
`management_fee_mentioned`: true if a management fee/payment to the manager is mentioned.
`confidence`: high | medium | low."""


SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": [
                "A_dedicated_MSO",
                "B_exec_staffing",
                "C_parent_shared_services",
                "D_peer_system_managed",
                "E_functional",
                "F_uninformative",
            ],
        },
        "manager_relationship": {
            "type": "string",
            "enum": ["unrelated_mso", "unrelated_peer", "related_parent", "individual_or_firm", "unclear"],
        },
        "scope": {
            "type": "string",
            "enum": ["organization_wide", "executive_only", "specific_function", "governance_only", "unclear"],
        },
        "manager_name": {"type": "string"},
        "provides_named_executive": {"type": "boolean"},
        "management_fee_mentioned": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": [
        "category",
        "manager_relationship",
        "scope",
        "manager_name",
        "provides_named_executive",
        "management_fee_mentioned",
        "confidence",
    ],
    "additionalProperties": False,
}


def classify(client, text):
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Classify this Schedule O text:\n\n{text}"}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    payload = next(b.text for b in response.content if b.type == "text")
    return json.loads(payload)


def main():
    client = anthropic.Anthropic(api_key=resolve_api_key())
    distinct = pd.read_csv(INPUT_FILE, dtype=str)
    distinct["text_id"] = distinct["text_id"].astype(int)

    # Resume: skip text_ids already classified.
    done = set()
    if OUTPUT_FILE.exists():
        prior = pd.read_csv(OUTPUT_FILE, dtype=str)
        done = set(prior["text_id"].astype(int))
        print(f"Resuming — {len(done)} texts already classified.")

    todo = distinct[~distinct["text_id"].isin(done)]
    print(f"Texts to classify this run: {len(todo)} of {len(distinct)}")

    out_cols = [
        "text_id", "category", "manager_relationship", "scope", "manager_name",
        "provides_named_executive", "management_fee_mentioned", "is_mso_affiliation",
        "confidence", "n_filings",
    ]
    header_needed = not OUTPUT_FILE.exists()

    for i, row in enumerate(todo.itertuples(index=False), 1):
        try:
            r = classify(client, row.text)
        except Exception as e:
            print(f"  text_id={row.text_id} ERROR: {e}")
            continue

        # is_mso_affiliation is DERIVED (default = category A). Change here to fold in D.
        r["is_mso_affiliation"] = (r["category"] == "A_dedicated_MSO")
        r["text_id"] = int(row.text_id)
        r["n_filings"] = row.n_filings

        pd.DataFrame([r])[out_cols].to_csv(
            OUTPUT_FILE, mode="a", header=header_needed, index=False
        )
        header_needed = False

        if i % 50 == 0:
            print(f"  classified {i}/{len(todo)}")

    print("Done. Saved:", OUTPUT_FILE)

    # Summary
    full = pd.read_csv(OUTPUT_FILE, dtype=str)
    full["n_filings"] = full["n_filings"].astype(int)
    print("\nCategory distribution (distinct texts | filings covered):")
    g = full.groupby("category").agg(
        texts=("text_id", "size"), filings=("n_filings", "sum")
    ).sort_values("filings", ascending=False)
    print(g.to_string())


if __name__ == "__main__":
    main()
