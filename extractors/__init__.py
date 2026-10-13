"""Atomic Form 990 extractors.

Each module is one measure group. It reads data/input/xml_files/*.xml and writes its own CSV.
Add a group by creating a module with KEY, GROUP, and main(), then register it
in REGISTRY below.
"""

from extractors import delegation, governance


REGISTRY = {
    delegation.KEY: delegation,
    governance.KEY: governance,
}
