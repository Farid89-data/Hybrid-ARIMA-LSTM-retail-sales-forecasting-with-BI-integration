"""Discovery step of the literature protocol (DECISIONS_LOG D-001, option B approved 9 Nov 2026).

Runs the themed queries against the OpenAlex works API, restricted to
publications dated 2023-2026 that have a DOI, and writes one candidate table
per run. Candidates are only *leads*: every source that is cited is verified
afterwards on its DOI/publisher page (``crossref_verify.py``) and read.

Usage (from ``Code``)::

    python scripts/literature/openalex_search.py --out ../Refrence/search/openalex_candidates.csv
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
BASE = "https://api.openalex.org/works"
FIELDS = ("id,doi,title,publication_year,publication_date,type,primary_location,authorships,"
          "cited_by_count,open_access,abstract_inverted_index,biblio,is_retracted")

QUERIES = {
    "T1_retail_forecasting": [
        "retail demand forecasting machine learning review",
        "retail sales forecasting deep learning",
        "sales forecasting retail statistical neural comparison",
    ],
    "T2_statistical": [
        "ARIMA sales forecasting retail",
        "SARIMA demand forecasting",
        "exponential smoothing demand forecasting",
    ],
    "T3_neural": [
        "LSTM time series forecasting review",
        "long short-term memory sales forecasting",
        "multilayer perceptron sales forecasting",
    ],
    "T4_hybrid": [
        "hybrid ARIMA LSTM forecasting",
        "ARIMA-LSTM hybrid model residuals",
        "hybrid ARIMA neural network linear nonlinear forecasting",
        "hybrid statistical deep learning demand forecasting",
        "ARIMA LSTM residual correction time series",
    ],
    "T5_metrics": [
        "forecast accuracy measures MASE MAPE",
        "forecast evaluation intermittent demand error measures",
    ],
    "T6_tuning_validation": [
        "Bayesian optimization hyperparameter LSTM forecasting",
        "Optuna hyperparameter optimization time series",
        "time series cross-validation rolling origin forecasting",
        "data leakage time series machine learning",
    ],
    "T7_dm_test": [
        "Diebold-Mariano test forecast comparison",
        "Diebold-Mariano LSTM ARIMA",
    ],
    "T8_intervals": [
        "prediction intervals deep learning forecasting calibration",
        "conformal prediction time series forecasting",
    ],
    "T9_bi_dashboards": [
        "business intelligence dashboard demand forecasting decision support",
        "Power BI dashboard",
        "dashboard usability System Usability Scale",
        "data visualization accessibility dashboard",
        "analytics adoption decision making business intelligence",
    ],
    "T10_ethics_sustainability": [
        "energy consumption deep learning training carbon footprint",
        "green AI sustainability machine learning",
        "food waste retail demand forecasting",
        "algorithmic decision making retail ethics",
    ],
    "T11_m5_rossmann": [
        "M5 competition forecasting",
        "M5 Walmart sales forecasting",
        "Rossmann sales forecasting",
    ],
    "T12_methodology": [
        "CRISP-DM data science methodology",
        "CRISP-DM agile data science project",
    ],
}


def fetch(query: str, per_page: int = 40, max_attempts: int = 6) -> list[dict]:
    """One OpenAlex search request, honouring HTTP 429 rate limiting with back-off."""
    params = {
        "search": query,
        "filter": "publication_year:2023-2026,has_doi:true,type:article|review|book-chapter",
        "per-page": str(per_page),
        "select": FIELDS,
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)["results"]
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == max_attempts - 1:
                raise
            wait = float(exc.headers.get("Retry-After") or 10 * (attempt + 1))
            time.sleep(min(wait, 120))
    return []


def abstract_text(inv: dict | None) -> str:
    if not inv:
        return ""
    positions = [(p, w) for w, ps in inv.items() for p in ps]
    return " ".join(w for _, w in sorted(positions))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--only-failed", action="store_true",
                        help="re-run only queries that failed in the previous log and merge")
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    log = []
    todo = {t: list(qs) for t, qs in QUERIES.items()}
    log_path = out.parent / "openalex_search_log.json"
    if args.only_failed and log_path.exists() and out.exists():
        previous = json.loads(log_path.read_text(encoding="utf-8"))["queries"]
        ok = {(q["theme"], q["query"]) for q in previous if not q.get("error")}
        log = [q for q in previous if not q.get("error")]
        todo = {t: [q for q in qs if (t, q) not in ok] for t, qs in QUERIES.items()}
        with out.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["themes"] = set(row["themes"].split("|"))
                row["best_rank"] = int(row["best_rank"])
                seen[row["doi"]] = row
    for theme, queries in todo.items():
        for q in queries:
            try:
                results = fetch(q)
            except Exception as exc:  # noqa: BLE001
                log.append({"theme": theme, "query": q, "hits": 0, "error": str(exc)})
                continue
            log.append({"theme": theme, "query": q, "hits": len(results)})
            for rank, w in enumerate(results, 1):
                doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
                if not doi:
                    continue
                src = ((w.get("primary_location") or {}).get("source") or {})
                rec = seen.setdefault(doi, {
                    "doi": doi,
                    "title": w.get("title"),
                    "year": w.get("publication_year"),
                    "date": w.get("publication_date"),
                    "type": w.get("type"),
                    "venue": src.get("display_name"),
                    "venue_type": src.get("type"),
                    "issn_l": src.get("issn_l"),
                    "publisher": src.get("host_organization_name"),
                    "authors": "; ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:6]),
                    "cited_by": w.get("cited_by_count"),
                    "oa_status": (w.get("open_access") or {}).get("oa_status"),
                    "oa_url": (w.get("open_access") or {}).get("oa_url"),
                    "is_retracted": w.get("is_retracted"),
                    "openalex_id": w.get("id"),
                    "abstract": abstract_text(w.get("abstract_inverted_index"))[:2500],
                    "themes": set(),
                    "best_rank": rank,
                })
                rec["themes"].add(theme)
                rec["best_rank"] = min(rec["best_rank"], rank)
            time.sleep(3.0)  # polite pacing for the anonymous API pool
    with out.open("w", newline="", encoding="utf-8") as handle:
        fields = ["doi", "title", "year", "date", "type", "venue", "venue_type", "issn_l", "publisher",
                  "authors", "cited_by", "oa_status", "oa_url", "is_retracted", "openalex_id", "themes",
                  "best_rank", "abstract"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rec in seen.values():
            rec = dict(rec)
            rec["themes"] = "|".join(sorted(rec["themes"]))
            writer.writerow(rec)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (out.parent / "openalex_search_log.json").write_text(
        json.dumps({"run_at_utc": stamp, "source": BASE, "queries": log}, indent=2), encoding="utf-8")
    print(f"{len(seen)} unique candidates from {len(log)} queries -> {out}")


if __name__ == "__main__":
    main()
