"""Integrity check for the raw Kaggle files supplied by the student.

For every expected file this script reports the file name, size, SHA-256
checksum, number of data rows (header excluded), number of columns and the
column names, and confirms that pandas can parse the whole file. The raw files
are opened read-only and are never modified.

Usage (from the ``Code`` directory)::

    python scripts/check_raw_data.py            # full report
    python scripts/check_raw_data.py --verify   # checksums only, against data/checksums.sha256

The report is written to ``outputs/data_check/raw_data_check.json`` and
``outputs/data_check/raw_data_check.md``. ``--verify`` compares the SHA-256
checksum of each file with the reference list committed in
``data/checksums.sha256``, so that another user can confirm that their Kaggle
download is identical to the files used in the dissertation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CODE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_DIR.parent
RAW_ROOT = Path(os.environ.get("RAW_DATA_DIR", PROJECT_ROOT / "Dataset"))
CHECKSUMS = CODE_DIR / "data" / "checksums.sha256"
OUT_DIR = CODE_DIR / "outputs" / "data_check"

EXPECTED = {
    "m5-forecasting-accuracy": [
        "calendar.csv",
        "sales_train_validation.csv",
        "sales_train_evaluation.csv",
        "sell_prices.csv",
        "sample_submission.csv",
    ],
    "rossmann-store-sales": [
        "train.csv",
        "test.csv",
        "store.csv",
        "sample_submission.csv",
    ],
}

SOURCES = {
    "m5-forecasting-accuracy": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data",
    "rossmann-store-sales": "https://www.kaggle.com/competitions/rossmann-store-sales/data",
}


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    """Return the SHA-256 hex digest of a file, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def summarise_columns(columns: list[str]) -> list[str]:
    """Collapse long runs of M5 day columns (d_1 ... d_N) into a single range label."""
    day_cols = [c for c in columns if re.fullmatch(r"d_\d+", c)]
    if len(day_cols) < 10:
        return columns
    days = sorted(int(c[2:]) for c in day_cols)
    other = [c for c in columns if c not in day_cols]
    return other + [f"d_{days[0]} ... d_{days[-1]} ({len(days)} day columns)"]


def check_file(path: Path) -> dict:
    """Parse one CSV completely and return its structural summary."""
    try:
        shown = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        shown = str(path)
    record: dict = {"file": shown, "exists": path.exists()}
    if not path.exists():
        record["status"] = "MISSING"
        return record
    record["size_bytes"] = path.stat().st_size
    record["size_mb"] = round(path.stat().st_size / 1_000_000, 2)
    record["sha256"] = sha256_of(path)
    try:
        rows = 0
        columns: list[str] | None = None
        null_cells = 0
        # Chunked parsing keeps peak memory low on the 5.9 GB development machine.
        for chunk in pd.read_csv(path, chunksize=200_000, low_memory=False):
            if columns is None:
                columns = list(chunk.columns)
            rows += len(chunk)
            null_cells += int(chunk.isna().sum().sum())
        record["rows"] = rows
        record["n_columns"] = len(columns or [])
        record["columns"] = summarise_columns(columns or [])
        record["null_cells"] = null_cells
        record["status"] = "OK" if rows > 0 else "EMPTY"
    except Exception as exc:  # noqa: BLE001 - any parse failure must be reported verbatim
        record["status"] = "CORRUPTED_OR_UNREADABLE"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def verify() -> int:
    """Compare the checksum of every expected file with the committed reference list."""
    expected = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(None, 1)
            expected[name.strip()] = digest
    failures = 0
    for name, digest in expected.items():
        path = RAW_ROOT / name
        if not path.exists():
            print(f"MISSING   {name}")
            failures += 1
            continue
        actual = sha256_of(path)
        status = "OK" if actual == digest else "MISMATCH"
        failures += status != "OK"
        print(f"{status:9} {name}")
    print("All files match the reference checksums." if not failures else f"{failures} file(s) failed.")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="check checksums against data/checksums.sha256")
    if parser.parse_args().verify:
        return verify()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_root": str(RAW_ROOT),
        "sources": SOURCES,
        "files": [],
    }
    for folder, names in EXPECTED.items():
        for name in names:
            report["files"].append(check_file(RAW_ROOT / folder / name))

    (OUT_DIR / "raw_data_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Raw data check",
        "",
        f"Checked at (UTC): {report['checked_at_utc']}",
        "",
        "| File | Size (MB) | Rows | Columns | Null cells | Status | SHA-256 (first 16) |",
        "|---|---|---|---|---|---|---|",
    ]
    for rec in report["files"]:
        lines.append(
            f"| {rec['file']} | {rec.get('size_mb', '')} | {rec.get('rows', '')} | "
            f"{rec.get('n_columns', '')} | {rec.get('null_cells', '')} | {rec['status']} | "
            f"{rec.get('sha256', '')[:16]} |"
        )
    lines.append("")
    lines.append("## Column names")
    for rec in report["files"]:
        lines.append(f"- **{rec['file']}**: {', '.join(rec.get('columns', []))}")
    (OUT_DIR / "raw_data_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    bad = [r for r in report["files"] if r["status"] != "OK"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
