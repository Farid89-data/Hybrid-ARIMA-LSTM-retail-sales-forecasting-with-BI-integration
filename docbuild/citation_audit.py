"""Citation and cross-reference audit of the built dissertation.

Usage (from ``Code``)::

    python docbuild/citation_audit.py

Checks, written to ``Doc/citation_audit_report.md``:

1. **Library.** Every cited entry has an allowed ledger status, a publication
   year inside 2023 to 2026 (journal articles), a Crossref record whose title
   matches the library title, no update or retraction notice, and the year that
   follows the stated year rule (issue year if assigned to an issue, otherwise
   online year).
2. **Word document.** Every citation hyperlink points to an existing reference
   bookmark; every reference entry is cited at least once; every REF field
   points to an existing bookmark; no unresolved Markdown citation syntax is
   left; remaining PENDING markers are listed.
3. **PDF.** Internal links exist and point to valid pages (if the PDF exists).
4. **Citations in context.** Each citation with the sentence in which it
   appears, for checking against ``Refrence/search/reading_notes.md``.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

from lxml import etree

CODE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_DIR.parent
DOCX = PROJECT_ROOT / "Doc" / "Dissertation_Hybrid_ARIMA-LSTM.docx"
PDF = DOCX.with_suffix(".pdf")
REF_DIR = PROJECT_ROOT / "Refrence"
REPORT = PROJECT_ROOT / "Doc" / "citation_audit_report.md"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
ALLOWED = {"VERIFIED", "EXCEPTION_APPROVED", "TECHNICAL_DOC"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def library_checks(cited_keys: set[str]) -> tuple[list[list[str]], list[str]]:
    refs = {e["id"]: e for e in json.loads((REF_DIR / "references.json").read_text(encoding="utf-8"))}
    crossref = json.loads((REF_DIR / "search" / "crossref_verified.json").read_text(encoding="utf-8"))
    by_doi = {v["doi"].lower(): v for v in crossref.values() if v.get("found")}
    rows, problems = [], []
    for key in sorted(cited_keys):
        e = refs.get(key)
        if e is None:
            problems.append(f"{key}: cited but missing from references.json")
            continue
        status = e.get("ledger_status")
        year = e["issued"]["date-parts"][0][0]
        checks = {"status": status in ALLOWED}
        if e["type"] == "article-journal":
            cr = by_doi.get(e["DOI"].lower())
            checks["window"] = 2023 <= year <= 2026
            checks["crossref"] = cr is not None
            if cr:
                sim = SequenceMatcher(None, norm(e["title"]), norm(cr["title"])).ratio()
                checks["title"] = sim >= 0.9
                checks["notices"] = not cr.get("update_notices")
                # D-020: issue (print) year when the article is in an issue, otherwise the online year.
                rule_year = next(int(cr[k][0]) for k in ("published_print", "published_online", "issued")
                                 if cr.get(k) and cr[k][0])
                checks["year_rule"] = rule_year == year
            evidence = f"Crossref title similarity {sim:.2f}" if cr else "no Crossref record"
        else:
            checks["window"] = True
            evidence = ("approved pre-2023 exception (Crossref and publisher page)" if status == "EXCEPTION_APPROVED"
                        else "technical documentation (dataset page)")
        ok = all(checks.values())
        if not ok:
            problems.append(f"{key}: failed {', '.join(k for k, v in checks.items() if not v)}")
        rows.append([key, str(year), status, "pass" if ok else "FAIL", evidence])
    return rows, problems


def docx_checks() -> dict:
    with zipfile.ZipFile(DOCX) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    bookmarks = {b.get(f"{{{W}}}name") for b in root.iter(f"{{{W}}}bookmarkStart")}
    anchors = [h.get(f"{{{W}}}anchor") for h in root.iter(f"{{{W}}}hyperlink") if h.get(f"{{{W}}}anchor")]
    ref_anchors = [a for a in anchors if a.startswith("ref_")]
    ref_bookmarks = {b for b in bookmarks if b and b.startswith("ref_")}
    instr = " ".join(t.text or "" for t in root.iter(f"{{{W}}}instrText"))
    ref_fields = re.findall(r"REF\s+(\S+)", instr)
    text = "\n".join("".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in root.iter(f"{{{W}}}p"))
    contexts = []
    for p in root.iter(f"{{{W}}}p"):
        links = [h.get(f"{{{W}}}anchor") for h in p.iter(f"{{{W}}}hyperlink")
                 if (h.get(f"{{{W}}}anchor") or "").startswith("ref_")]
        if not links:
            continue
        ptext = "".join(t.text or "" for t in p.iter(f"{{{W}}}t"))
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", ptext):
            for a in sorted(set(links)):
                contexts.append((a, sentence.strip()))
    return {
        "bookmarks": bookmarks,
        "anchors": anchors,
        "ref_anchor_counts": Counter(ref_anchors),
        "ref_bookmarks": ref_bookmarks,
        "broken_anchors": sorted({a for a in anchors if a not in bookmarks}),
        "uncited_entries": sorted(ref_bookmarks - set(ref_anchors)),
        "broken_ref_fields": sorted({r for r in ref_fields if r not in bookmarks}),
        "n_ref_fields": len(ref_fields),
        "leftover_markdown": sorted(set(re.findall(r"\[@[^\]]+\]|\{(?:fig|tbl|sec|eq|app):[^}]+\}", text))),
        "pending": re.findall(r"PENDING:[^\n]{0,120}", text),
        "contexts": contexts,
    }


def pdf_checks() -> dict | None:
    if not PDF.exists():
        return None
    import fitz  # PyMuPDF

    doc = fitz.open(PDF)
    internal = bad = external = 0
    for page in doc:
        for link in page.get_links():
            if link["kind"] in (fitz.LINK_GOTO, fitz.LINK_NAMED):
                internal += 1
                target = link.get("page", -1)
                if link["kind"] == fitz.LINK_GOTO and not (0 <= target < doc.page_count):
                    bad += 1
            elif link["kind"] == fitz.LINK_URI:
                external += 1
    return {"pages": doc.page_count, "internal": internal, "bad": bad, "external": external,
            "outline_entries": len(doc.get_toc())}


def main() -> int:
    if not DOCX.exists():
        print(f"Build the document first: {DOCX} not found")
        return 1
    d = docx_checks()
    key_of = {}
    refs = json.loads((REF_DIR / "references.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(CODE_DIR / "docbuild"))
    import citations  # noqa: PLC0415

    lib = citations.load_library(REF_DIR / "references.json")
    for k, e in lib.items():
        key_of[e.bookmark()] = k
    cited_keys = {key_of.get(a, a) for a in d["ref_anchor_counts"]}
    lib_rows, lib_problems = library_checks(cited_keys)
    pdf = pdf_checks()
    notes = (REF_DIR / "search" / "reading_notes.md").read_text(encoding="utf-8")
    no_notes = sorted(k for k in cited_keys if not k.startswith("kaggle") and f"## {k}:" not in notes)

    lines = ["# Citation audit report", "", f"Generated: {date.today().isoformat()} by `Code/docbuild/citation_audit.py`.",
             "", f"Document: `{DOCX.relative_to(PROJECT_ROOT)}`", ""]
    status = not (lib_problems or d["broken_anchors"] or d["uncited_entries"] or d["broken_ref_fields"]
                  or d["leftover_markdown"] or no_notes or (pdf and pdf["bad"]))
    lines += ["## Summary", "", "| Check | Result |", "|---|---|",
              f"| References cited | {len(cited_keys)} distinct entries, {sum(d['ref_anchor_counts'].values())} citation links |",
              f"| Library checks (status, 2023-2026 window, Crossref match, notices, year rule) | {'pass' if not lib_problems else 'FAIL: ' + '; '.join(lib_problems)} |",
              f"| Citation links without a target bookmark | {len(d['broken_anchors'])} |",
              f"| Reference entries never cited | {len(d['uncited_entries'])} |",
              f"| Cross-reference fields (REF) | {d['n_ref_fields']} fields, {len(d['broken_ref_fields'])} with a missing bookmark |",
              f"| Unresolved Markdown markers | {len(d['leftover_markdown'])} |",
              f"| Cited articles without reading notes | {len(no_notes)} |",
              f"| Remaining PENDING markers | {len(d['pending'])} |"]
    if pdf:
        lines.append(f"| PDF | {pdf['pages']} pages, {pdf['internal']} internal links ({pdf['bad']} invalid), "
                     f"{pdf['external']} external links, {pdf['outline_entries']} bookmarks |")
    lines += ["", f"**Overall: {'PASS' if status else 'ATTENTION NEEDED'}** (PENDING markers are reported, not failed).", ""]
    if d["pending"]:
        lines += ["## Remaining PENDING markers", ""] + [f"- {p}" for p in d["pending"]] + [""]
    for title, items in (("Broken citation links", d["broken_anchors"]), ("Uncited reference entries", d["uncited_entries"]),
                         ("Broken REF fields", d["broken_ref_fields"]), ("Unresolved Markdown", d["leftover_markdown"]),
                         ("Cited without reading notes", no_notes)):
        if items:
            lines += [f"## {title}", ""] + [f"- {i}" for i in items] + [""]
    lines += ["## Library checks per cited entry", "", "| Key | Year | Ledger status | Checks | Evidence |", "|---|---|---|---|---|"]
    lines += [f"| {' | '.join(r)} |" for r in lib_rows]
    lines += ["", "## Citation counts", "", "| Key | Citation links |", "|---|---|"]
    lines += [f"| {key_of.get(a, a)} | {n} |" for a, n in sorted(d["ref_anchor_counts"].items(), key=lambda x: key_of.get(x[0], x[0]))]
    lines += ["", "## Citations in context", "",
              "Each row gives a sentence and the reference it cites, for checking against the reading notes.", "",
              "| Key | Sentence |", "|---|---|"]
    seen = set()
    for a, s in d["contexts"]:
        k = key_of.get(a, a)
        if (k, s) in seen:
            continue
        seen.add((k, s))
        lines.append(f"| {k} | {s.replace('|', '/')} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Audit written to {REPORT}; overall {'PASS' if status else 'ATTENTION NEEDED'}")
    return 0 if status else 2


if __name__ == "__main__":
    sys.exit(main())
