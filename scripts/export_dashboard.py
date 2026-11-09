"""Export the Power BI star schema (run after scripts/run_evaluation.py).

Usage (from ``Code``)::

    python scripts/export_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import export_powerbi, utils  # noqa: E402

if __name__ == "__main__":
    utils.setup_logging()
    print(export_powerbi.export())
