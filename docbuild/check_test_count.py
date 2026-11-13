"""Check that the number of automated tests in the report equals the number in the JUnit file.

The single source is ``outputs/tests/pytest_results.xml``. The number is stated in Chapter 3
(text and the table by area), in the requirements table of Chapter 4 and in Appendix E, and the
Appendix E table (``report_unit_tests.csv``) lists the same cases. ``problems()`` returns a list of
differences; the build raises an error if it is not empty.

Usage (from ``Code``)::

    python docbuild/check_test_count.py
"""

from __future__ import annotations

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
CHAPTERS = CODE_DIR / "docbuild" / "chapters"
JUNIT = CODE_DIR / "outputs" / "tests" / "pytest_results.xml"
UNIT_CSV = CODE_DIR / "outputs" / "tables" / "report_unit_tests.csv"


def junit_counts() -> dict[str, int]:
    root = ET.parse(JUNIT).getroot()
    cases = list(root.iter("testcase"))
    bad = sum(1 for c in cases if c.find("failure") is not None or c.find("error") is not None)
    skipped = sum(1 for c in cases if c.find("skipped") is not None)
    return {"total": len(cases), "failed": bad, "skipped": skipped}


def _find(path: str, pattern: str) -> list[int]:
    text = (CHAPTERS / path).read_text(encoding="utf-8")
    return [int(m) for m in re.findall(pattern, text)]


def _area_table_sum() -> int | None:
    text = (CHAPTERS / "03_development.md").read_text(encoding="utf-8")
    m = re.search(r"::: table id=tbl:tests.*?\n:::", text, re.S)
    if not m:
        return None
    total = 0
    for row in m.group(0).splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[1].isdigit():
            total += int(cells[1])
    return total


def problems() -> list[str]:
    if not JUNIT.exists():
        return [f"JUnit file missing: {JUNIT}"]
    n = junit_counts()
    out = []
    if n["failed"] or n["skipped"]:
        out.append(f"JUnit file has {n['failed']} failed and {n['skipped']} skipped tests; the report says all passed")
    stated = {
        "Chapter 3 text": _find("03_development.md", r"covered by (\d+) automated tests"),
        "Chapter 4 requirements table": _find("04_evaluation.md", r"(\d+) automated tests, all passing"),
        "Appendix E text": _find("90_appendices.md", r"The final run had (\d+) automated tests"),
    }
    for where, vals in stated.items():
        if len(vals) != 1:
            out.append(f"{where}: expected one statement of the test count, found {len(vals)}")
        elif vals[0] != n["total"]:
            out.append(f"{where}: says {vals[0]} tests, JUnit file has {n['total']}")
    area = _area_table_sum()
    if area is None or area != n["total"]:
        out.append(f"Chapter 3 table by area sums to {area}, JUnit file has {n['total']}")
    if UNIT_CSV.exists():
        with UNIT_CSV.open(encoding="utf-8", newline="") as fh:
            rows = len(list(csv.reader(fh))) - 1
        if rows != n["total"]:
            out.append(f"Appendix E table has {rows} rows, JUnit file has {n['total']}")
    return out


if __name__ == "__main__":
    found = problems()
    for p in found:
        print("TEST COUNT MISMATCH:", p)
    if not found:
        print(f"Test count consistent: {junit_counts()['total']} tests, all passed.")
    sys.exit(1 if found else 0)
