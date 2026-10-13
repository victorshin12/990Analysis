"""Run one extractor, or every registered extractor.

Examples:
  python -m extractors governance
  python -m extractors delegation
  python -m extractors all
  python -m extractors governance --xml-dir data/input/xml_files --output data/extract/governance_management_measures.csv
"""

import argparse
from pathlib import Path

from extractors import REGISTRY


def main():
    parser = argparse.ArgumentParser(description="Run a Form 990 extractor.")
    parser.add_argument(
        "extractor",
        choices=[*REGISTRY.keys(), "all"],
        help="Measure group to extract. 'governance' is Governance & Management Measures.",
    )
    parser.add_argument("--xml-dir", type=Path, default=None, help="Folder of Form 990 XML files.")
    parser.add_argument("--output", type=Path, default=None, help="Output CSV. Ignored when extractor is 'all'.")
    args = parser.parse_args()

    keys = list(REGISTRY) if args.extractor == "all" else [args.extractor]
    if args.extractor == "all" and args.output is not None:
        parser.error("--output applies to a single extractor, not 'all'.")

    for key in keys:
        module = REGISTRY[key]
        print(f"=== {module.GROUP} ({key}) ===")
        module.main(xml_dir=args.xml_dir, output_file=args.output)
        print()


if __name__ == "__main__":
    main()
