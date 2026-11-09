"""Assemble the verified reference library and the reference ledger.

Inputs (all in ``Refrence/search``):
    selected_v1.csv           citation keys and DOIs of sources read in full
    crossref_verified.json    Crossref metadata and update notices (crossref_verify.py)
    venue_indexing.json       indexing evidence from publisher journal pages
    annotations.json          topic and dissertation-section mapping per key

Outputs (in ``Refrence``):
    references.json           CSL-JSON library (single source of truth for the Word build)
    reference_ledger.csv      ledger with the columns required by the protocol

Year rule (DECISIONS_LOG D-020): the year of the journal issue when the
article has been assigned to one (Crossref ``published-print``), otherwise
the year of online publication.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEARCH = ROOT / "Refrence" / "search"
OUT_JSON = ROOT / "Refrence" / "references.json"
OUT_LEDGER = ROOT / "Refrence" / "reference_ledger.csv"
VERIFIED_ON = "2026-11-09"
LEDGER_FIELDS = [
    "key", "authors", "year", "title", "venue", "volume", "issue", "pages_or_article_no", "doi", "url",
    "scholar_url", "publisher_url", "publication_type", "indexing_evidence", "quartile_or_venue_note",
    "relevance_topic", "supports_claim_in_section", "date_verified", "status", "notes",
]

TECHNICAL_DOCS = [
    {
        "id": "kaggle2020m5", "type": "webpage",
        "author": [{"literal": "Kaggle"}], "issued": {"date-parts": [[2020]]},
        "title": "M5 Forecasting - Accuracy: competition data",
        "publisher": "Kaggle (data provided by Walmart through the M5 competition)",
        "URL": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data",
        "ledger_status": "TECHNICAL_DOC",
        "note": "Dataset provenance as instructed by the student; files downloaded by the student. Year = competition year (2020); page title verified on 9 Nov 2026.",
    },
    {
        "id": "kaggle2015rossmann", "type": "webpage",
        "author": [{"literal": "Kaggle"}], "issued": {"date-parts": [[2015]]},
        "title": "Rossmann Store Sales: competition data",
        "publisher": "Kaggle (data provided by Rossmann)",
        "URL": "https://www.kaggle.com/competitions/rossmann-store-sales/data",
        "ledger_status": "TECHNICAL_DOC",
        "note": "Dataset provenance as instructed by the student; files downloaded by the student. Year = competition year (2015); page title verified on 9 Nov 2026.",
    },
]


def year_of(rec: dict) -> int:
    """Issue year if the article is assigned to an issue, otherwise the online year."""
    for key in ("published_print", "published_online", "issued"):
        parts = rec.get(key) or [None]
        if parts and parts[0]:
            return int(parts[0])
    raise ValueError(f"No year for {rec['doi']}")


def pages_or_number(rec: dict) -> tuple[str | None, str | None]:
    page = rec.get("page")
    if page and not page.lower().startswith("e"):
        return page, None
    if page:  # PLOS-style article identifiers
        return None, page
    return None, rec.get("article_number")


def main() -> None:
    selected = list(csv.DictReader((SEARCH / "selected_v1.csv").open(encoding="utf-8")))
    crossref = json.loads((SEARCH / "crossref_verified.json").read_text(encoding="utf-8"))
    venues = json.loads((SEARCH / "venue_indexing.json").read_text(encoding="utf-8"))
    notes = json.loads((SEARCH / "annotations.json").read_text(encoding="utf-8"))
    library, ledger = [], []
    for row in selected:
        key, doi = row["key"], row["doi"].lower()
        rec = crossref[doi]
        if not rec.get("found"):
            raise ValueError(f"{key}: DOI not found in Crossref")
        if rec.get("update_notices"):
            raise ValueError(f"{key}: has update notices {rec['update_notices']}")
        year = year_of(rec)
        if not 2023 <= year <= 2026:
            raise ValueError(f"{key}: year {year} outside 2023-2026")
        page, number = pages_or_number(rec)
        venue = rec["container"]
        ven = venues[venue]
        ann = notes[key]
        item = {
            "id": key,
            "type": "article-journal",
            "author": [{"family": a["family"], "given": a.get("given", "")} for a in rec["authors"]],
            "issued": {"date-parts": [[year]]},
            "title": rec["title"].strip(),
            "container-title": ann.get("container_display", venue),
            "volume": rec.get("volume"),
            "issue": rec.get("issue") if rec.get("page") or ann.get("show_issue") else None,
            "page": page,
            "number": number,
            "DOI": rec["doi"] if rec["doi"] == doi else doi,
            "URL": f"https://doi.org/{doi}",
            "publisher": rec.get("publisher"),
            "ledger_status": "VERIFIED",
        }
        if item["volume"] is None and ann.get("online_first"):
            item["note"] = "Advance online publication"
        library.append({k: v for k, v in item.items() if v not in (None, "")})
        ledger.append({
            "key": key,
            "authors": "; ".join(f"{a['family']}, {a.get('given', '')}" for a in rec["authors"]),
            "year": year,
            "title": rec["title"].strip(),
            "venue": venue,
            "volume": rec.get("volume") or "",
            "issue": rec.get("issue") or "",
            "pages_or_article_no": page or number or "",
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "scholar_url": "",
            "publisher_url": ann["publisher_url"],
            "publication_type": "journal article",
            "indexing_evidence": ven["evidence"],
            "quartile_or_venue_note": ven["note"],
            "relevance_topic": ann["topic"],
            "supports_claim_in_section": ann["sections"],
            "date_verified": VERIFIED_ON,
            "status": "VERIFIED",
            "notes": ann.get("notes", "") + " Discovery: OpenAlex/Crossref API (D-001 option B, approved 9 Nov 2026); "
                     "metadata checked against Crossref; full text read on the publisher page (see search/reading_notes.md).",
        })
    for doc in TECHNICAL_DOCS:
        library.append({k: v for k, v in doc.items() if k != "note"})
        ledger.append({
            "key": doc["id"], "authors": "Kaggle", "year": doc["issued"]["date-parts"][0][0], "title": doc["title"],
            "venue": "Kaggle", "volume": "", "issue": "", "pages_or_article_no": "", "doi": "", "url": doc["URL"],
            "scholar_url": "", "publisher_url": doc["URL"], "publication_type": "dataset documentation",
            "indexing_evidence": "n/a (technical documentation)", "quartile_or_venue_note": "n/a",
            "relevance_topic": "dataset provenance", "supports_claim_in_section": "3.3; Appendix B",
            "date_verified": VERIFIED_ON, "status": "TECHNICAL_DOC", "notes": doc["note"],
        })
    OUT_JSON.write_text(json.dumps(library, indent=2, ensure_ascii=False), encoding="utf-8")
    previous = list(csv.DictReader(OUT_LEDGER.open(encoding="utf-8"))) if OUT_LEDGER.exists() else []
    keep = [r for r in previous if r["key"] not in {x["key"] for x in ledger}]
    with OUT_LEDGER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        for r in ledger + keep:
            writer.writerow({k: r.get(k, "") for k in LEDGER_FIELDS})
    print(f"{len(library)} library entries; ledger rows: {len(ledger) + len(keep)}")


if __name__ == "__main__":
    main()
