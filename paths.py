"""Shared locations for pipeline inputs and outputs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent

INPUT = ROOT / "data" / "input"
REFERENCE = ROOT / "data" / "reference"
ACQUIRE = ROOT / "data" / "acquire"
EXTRACT = ROOT / "data" / "extract"
CLASSIFY = ROOT / "data" / "classify"
PANEL = ROOT / "data" / "panel"

XML_DIR = INPUT / "xml_files"
IRS_ZIPS = INPUT / "irs_zips"
CBI_HOSPITALS = INPUT / "cbi_hospitals.json"
KEY_FILE = ROOT / "anthropic_key.txt"
