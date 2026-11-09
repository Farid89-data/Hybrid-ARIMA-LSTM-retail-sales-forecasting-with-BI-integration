"""Supplementary discovery through the Crossref REST API (D-001 option B).

The publisher websites of Elsevier, MDPI, Taylor & Francis, Wiley and PeerJ
refuse automated page requests (HTTP 403), so their full texts cannot be read
by the verification step. This script therefore searches, theme by theme,
within publishers whose open-access pages can be read: Springer Nature
(including BMC and Scientific Reports), Frontiers, PLOS and Emerald. All hits
are leads only; inclusion still requires verification and reading.

Usage (from ``Code``)::

    python scripts/literature/crossref_search.py --out ../Refrence/search/crossref_candidates.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "COM7014-dissertation-literature-search/1.0"
PREFIXES = {
    "10.1007": "Springer",
    "10.1038": "Nature Portfolio",
    "10.1186": "BMC/SpringerOpen",
    "10.3389": "Frontiers",
    "10.1371": "PLOS",
    "10.1108": "Emerald",
}
QUERIES = {
    "T1": ["retail demand forecasting machine learning", "retail sales forecasting deep learning",
           "demand forecasting supply chain review"],
    "T2": ["ARIMA forecasting sales", "exponential smoothing forecasting", "seasonal ARIMA forecasting"],
    "T3": ["LSTM time series forecasting", "recurrent neural network demand forecasting",
           "deep learning time series forecasting review"],
    "T4": ["hybrid ARIMA LSTM", "hybrid ARIMA neural network forecasting", "ARIMA residual neural network hybrid"],
    "T5": ["forecast accuracy measures", "mean absolute scaled error"],
    "T6": ["hyperparameter optimization deep learning Bayesian", "Optuna hyperparameter",
           "time series cross validation", "data leakage machine learning"],
    "T7": ["Diebold-Mariano test", "forecast comparison statistical test"],
    "T8": ["conformal prediction time series", "prediction intervals neural network forecasting"],
    "T9": ["business intelligence dashboard decision making", "dashboard design evaluation usability",
           "system usability scale", "data visualization accessibility", "Power BI"],
    "T10": ["energy consumption deep learning carbon", "green artificial intelligence sustainability",
            "food waste demand forecasting retail", "algorithmic decision making ethics"],
    "T11": ["M5 forecasting competition", "Walmart sales forecasting", "Rossmann store sales"],
    "T12": ["CRISP-DM", "data science project methodology"],
}


def search(query: str, prefix: str, rows: int = 15) -> list[dict]:
    params = {
        "query.bibliographic": query,
        "filter": f"from-pub-date:2023-01-01,until-pub-date:2026-12-31,prefix:{prefix},type:journal-article",
        "rows": str(rows),
        "select": "DOI,title,author,container-title,issued,type,volume,issue,page,article-number,is-referenced-by-count,abstract",
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)["message"]["items"]
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < 4:
                time.sleep(float(exc.headers.get("Retry-After") or 5 * (attempt + 1)))
                continue
            raise
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    log = []
    for theme, queries in QUERIES.items():
        for q in queries:
            for prefix in PREFIXES:
                try:
                    items = search(q, prefix)
                except Exception as exc:  # noqa: BLE001
                    log.append({"theme": theme, "query": q, "prefix": prefix, "error": str(exc)})
                    continue
                log.append({"theme": theme, "query": q, "prefix": prefix, "hits": len(items)})
                for rank, it in enumerate(items, 1):
                    doi = it["DOI"].lower()
                    rec = seen.setdefault(doi, {
                        "doi": doi,
                        "title": (it.get("title") or [""])[0],
                        "year": ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0],
                        "venue": (it.get("container-title") or [""])[0],
                        "publisher_group": PREFIXES[prefix],
                        "authors": "; ".join(f"{a.get('family', '')}, {a.get('given', '')}"
                                             for a in it.get("author", [])[:6]),
                        "cited_by": it.get("is-referenced-by-count"),
                        "has_abstract": bool(it.get("abstract")),
                        "themes": set(),
                        "best_rank": rank,
                    })
                    rec["themes"].add(theme)
                    rec["best_rank"] = min(rec["best_rank"], rank)
                time.sleep(0.2)
    with out.open("w", newline="", encoding="utf-8") as handle:
        fields = ["doi", "title", "year", "venue", "publisher_group", "authors", "cited_by",
                  "has_abstract", "themes", "best_rank"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rec in seen.values():
            rec = dict(rec)
            rec["themes"] = "|".join(sorted(rec["themes"]))
            writer.writerow(rec)
    (out.parent / "crossref_search_log.json").write_text(
        json.dumps({"run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "queries": log}, indent=2), encoding="utf-8")
    print(f"{len(seen)} candidates from {len(log)} query-prefix pairs -> {out}")


if __name__ == "__main__":
    main()
