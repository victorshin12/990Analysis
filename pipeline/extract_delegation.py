"""Backward-compatible entry point for the management-delegation extractor.

Prefer:
    python -m extractors delegation

Running this overwrites data/extract/delegation_results.csv using the XMLs in
data/input/xml_files/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractors.delegation import main


if __name__ == "__main__":
    main()
