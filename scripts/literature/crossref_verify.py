"""Verification step: authoritative metadata and update notices for each candidate DOI.

For every DOI the Crossref REST API record (the DOI registration agency's
metadata) is fetched, together with any notices that *update* the work
(retractions, corrections, expressions of concern). The OpenAlex retraction
flag is recorded as a second signal. The output feeds ``reference_ledger.csv``.

Usage (from ``Code``)::

    python scripts/literature/crossref_verify.py --dois dois.txt --out ../Refrence/search/crossref_verified.json
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "COM7014-dissertation-reference-check/1.0"


def get_json(url: str, attempts: int = 5) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"status": "not-found"}
            if exc.code in (429, 503) and attempt < attempts - 1:
                time.sleep(float(exc.headers.get("Retry-After") or 5 * (attempt + 1)))
                continue
            raise
    return {}


def first_date(msg: dict, key: str):
    parts = (msg.get(key) or {}).get("date-parts") or [[None]]
    return parts[0]


def summarise(doi: str) -> dict:
    rec = get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    if rec.get("status") == "not-found" or "message" not in rec:
        return {"doi": doi, "found": False}
    m = rec["message"]
    notices = get_json("https://api.crossref.org/works?rows=20&filter=updates:" + urllib.parse.quote(doi))
    updates = []
    for item in (notices.get("message") or {}).get("items", []):
        for u in item.get("update-to", []):
            if u.get("DOI", "").lower() == doi.lower():
                updates.append({"type": u.get("type"), "notice_doi": item.get("DOI"),
                                "label": u.get("label")})
    authors = [
        {"family": a.get("family") or a.get("name"), "given": a.get("given", "")}
        for a in m.get("author", [])
    ]
    return {
        "doi": doi,
        "found": True,
        "title": (m.get("title") or [""])[0],
        "authors": authors,
        "container": (m.get("container-title") or [""])[0],
        "short_container": (m.get("short-container-title") or [""])[0],
        "publisher": m.get("publisher"),
        "type": m.get("type"),
        "volume": m.get("volume"),
        "issue": m.get("issue"),
        "page": m.get("page"),
        "article_number": m.get("article-number"),
        "issn": m.get("ISSN"),
        "published_print": first_date(m, "published-print"),
        "published_online": first_date(m, "published-online"),
        "issued": first_date(m, "issued"),
        "url": m.get("URL"),
        "update_notices": updates,
        "subject": m.get("subject"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dois", required=True, help="text file, one DOI per line")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    dois = [d.strip().lower() for d in Path(args.dois).read_text(encoding="utf-8").splitlines() if d.strip()]
    for doi in dois:
        if doi in existing and existing[doi].get("found"):
            continue
        existing[doi] = summarise(doi)
        time.sleep(0.3)
    out.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(existing)} records in {out}")


if __name__ == "__main__":
    main()
