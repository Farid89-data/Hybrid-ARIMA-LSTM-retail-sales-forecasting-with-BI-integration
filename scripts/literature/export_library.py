"""Export the verified reference library to Zotero-compatible formats.

Usage (from ``Code``)::

    python scripts/literature/export_library.py

Reads ``Refrence/references.json`` (CSL-JSON, the canonical library) and writes,
next to it:

* ``references.bib``  BibTeX
* ``references.ris``  RIS
* ``references.rdf``  Zotero RDF (RDF/XML)

Only entries whose ledger status allows citation (VERIFIED, EXCEPTION_APPROVED,
TECHNICAL_DOC) are exported. The CSL-JSON file itself can be imported into
Zotero directly (File, Import).
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

REF_DIR = Path(__file__).resolve().parents[3] / "Refrence"
ALLOWED = {"VERIFIED", "EXCEPTION_APPROVED", "TECHNICAL_DOC"}


def load() -> list[dict]:
    data = json.loads((REF_DIR / "references.json").read_text(encoding="utf-8"))
    return [e for e in data if e.get("ledger_status") in ALLOWED]


def year(e: dict) -> str:
    return str(e["issued"]["date-parts"][0][0])


def bib_escape(text: str) -> str:
    return text.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def to_bibtex(entries: list[dict]) -> str:
    out = []
    for e in entries:
        if e["type"] == "article-journal":
            authors = " and ".join(f"{a['family']}, {a['given']}" for a in e["author"])
            fields = [("author", authors), ("title", "{" + bib_escape(e["title"]) + "}"),
                      ("journal", bib_escape(e["container-title"])), ("year", year(e))]
            for key, csl in (("volume", "volume"), ("number", "issue"), ("pages", "page"), ("eid", "number")):
                if csl in e:
                    fields.append((key, str(e[csl]).replace("-", "--") if key == "pages" else str(e[csl])))
            fields += [("doi", e["DOI"]), ("url", e["URL"])]
            if "note" in e:
                fields.append(("note", e["note"]))
            kind = "article"
        elif e["type"] == "chapter":
            authors = " and ".join(f"{a['family']}, {a['given']}" for a in e["author"])
            editors = " and ".join(f"{a['family']}, {a['given']}" for a in e.get("editor", []))
            fields = [("author", authors), ("title", "{" + bib_escape(e["title"]) + "}"),
                      ("booktitle", bib_escape(e["container-title"])), ("editor", editors),
                      ("publisher", e.get("publisher", "")), ("year", year(e)),
                      ("pages", str(e.get("page", "")).replace("-", "--")), ("doi", e["DOI"]), ("url", e["URL"])]
            kind = "incollection"
        else:
            fields = [("author", "{" + e["author"][0]["literal"] + "}"), ("title", "{" + bib_escape(e["title"]) + "}"),
                      ("year", year(e)), ("howpublished", r"\url{" + e["URL"] + "}"),
                      ("publisher", bib_escape(e.get("publisher", ""))), ("url", e["URL"])]
            kind = "misc"
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields)
        out.append(f"@{kind}{{{e['id']},\n{body}\n}}")
    return "\n\n".join(out) + "\n"


def to_ris(entries: list[dict]) -> str:
    out = []
    for e in entries:
        lines = []
        if e["type"] == "article-journal":
            lines.append("TY  - JOUR")
            lines += [f"AU  - {a['family']}, {a['given']}" for a in e["author"]]
            lines += [f"TI  - {e['title']}", f"T2  - {e['container-title']}", f"PY  - {year(e)}"]
            if "volume" in e:
                lines.append(f"VL  - {e['volume']}")
            if "issue" in e:
                lines.append(f"IS  - {e['issue']}")
            if "page" in e:
                start, _, end = str(e["page"]).partition("-")
                lines.append(f"SP  - {start}")
                if end:
                    lines.append(f"EP  - {end}")
            elif "number" in e:
                lines.append(f"SP  - {e['number']}")
            lines += [f"DO  - {e['DOI']}", f"UR  - {e['URL']}"]
            if "publisher" in e:
                lines.append(f"PB  - {e['publisher']}")
            if "note" in e:
                lines.append(f"N1  - {e['note']}")
        elif e["type"] == "chapter":
            lines.append("TY  - CHAP")
            lines += [f"AU  - {a['family']}, {a['given']}" for a in e["author"]]
            lines += [f"A2  - {a['family']}, {a['given']}" for a in e.get("editor", [])]
            start, _, end = str(e.get("page", "")).partition("-")
            lines += [f"TI  - {e['title']}", f"T2  - {e['container-title']}", f"PY  - {year(e)}",
                      f"SP  - {start}", f"EP  - {end}", f"PB  - {e.get('publisher', '')}",
                      f"DO  - {e['DOI']}", f"UR  - {e['URL']}"]
        else:
            lines += ["TY  - ELEC", f"AU  - {e['author'][0]['literal']}", f"TI  - {e['title']}", f"PY  - {year(e)}",
                      f"UR  - {e['URL']}", f"PB  - {e.get('publisher', '')}"]
        lines += [f"ID  - {e['id']}", "ER  - "]
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def to_zotero_rdf(entries: list[dict]) -> str:
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            'xmlns:z="http://www.zotero.org/namespaces/export#" xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:bib="http://purl.org/net/biblio#" '
            'xmlns:foaf="http://xmlns.com/foaf/0.1/" xmlns:prism="http://prismstandard.org/namespaces/1.2/basic/">\n')
    items = []
    for e in entries:
        x = escape
        if e["type"] == "article-journal":
            people = "".join(
                f"<rdf:li><foaf:Person><foaf:surname>{x(a['family'])}</foaf:surname>"
                f"<foaf:givenName>{x(a['given'])}</foaf:givenName></foaf:Person></rdf:li>" for a in e["author"])
            journal = f"<dc:title>{x(e['container-title'])}</dc:title>"
            if "volume" in e:
                journal += f"<prism:volume>{x(str(e['volume']))}</prism:volume>"
            if "issue" in e:
                journal += f"<prism:number>{x(str(e['issue']))}</prism:number>"
            pages = e.get("page", e.get("number"))
            item = (f'  <bib:Article rdf:about="{x(e["URL"])}">\n'
                    f"    <z:itemType>journalArticle</z:itemType>\n"
                    f"    <dcterms:isPartOf><bib:Journal>{journal}</bib:Journal></dcterms:isPartOf>\n"
                    f"    <bib:authors><rdf:Seq>{people}</rdf:Seq></bib:authors>\n"
                    f"    <dc:title>{x(e['title'])}</dc:title>\n"
                    f"    <dc:date>{year(e)}</dc:date>\n"
                    + (f"    <bib:pages>{x(str(pages))}</bib:pages>\n" if pages else "")
                    + f"    <dc:identifier>DOI {x(e['DOI'])}</dc:identifier>\n"
                    f"    <dc:identifier><dcterms:URI><rdf:value>{x(e['URL'])}</rdf:value></dcterms:URI></dc:identifier>\n"
                    + (f"    <dc:description>{x(e['note'])}</dc:description>\n" if "note" in e else "")
                    + "  </bib:Article>\n")
        elif e["type"] == "chapter":
            people = "".join(
                f"<rdf:li><foaf:Person><foaf:surname>{x(a['family'])}</foaf:surname>"
                f"<foaf:givenName>{x(a['given'])}</foaf:givenName></foaf:Person></rdf:li>" for a in e["author"])
            eds = "".join(
                f"<rdf:li><foaf:Person><foaf:surname>{x(a['family'])}</foaf:surname>"
                f"<foaf:givenName>{x(a['given'])}</foaf:givenName></foaf:Person></rdf:li>" for a in e.get("editor", []))
            item = (f'  <bib:BookSection rdf:about="{x(e["URL"])}">\n'
                    f"    <z:itemType>bookSection</z:itemType>\n"
                    f"    <dcterms:isPartOf><bib:Book><dc:title>{x(e['container-title'])}</dc:title>"
                    f"<bib:editors><rdf:Seq>{eds}</rdf:Seq></bib:editors></bib:Book></dcterms:isPartOf>\n"
                    f"    <bib:authors><rdf:Seq>{people}</rdf:Seq></bib:authors>\n"
                    f"    <dc:title>{x(e['title'])}</dc:title>\n"
                    f"    <dc:date>{year(e)}</dc:date>\n"
                    f"    <bib:pages>{x(str(e.get('page', '')))}</bib:pages>\n"
                    f"    <dc:publisher><foaf:Organization><foaf:name>{x(e.get('publisher', ''))}</foaf:name>"
                    f"</foaf:Organization></dc:publisher>\n"
                    f"    <dc:identifier>DOI {x(e['DOI'])}</dc:identifier>\n"
                    f"  </bib:BookSection>\n")
        else:
            item = (f'  <bib:Document rdf:about="{x(e["URL"])}">\n'
                    f"    <z:itemType>webpage</z:itemType>\n"
                    f"    <bib:authors><rdf:Seq><rdf:li><foaf:Organization><foaf:name>{x(e['author'][0]['literal'])}"
                    f"</foaf:name></foaf:Organization></rdf:li></rdf:Seq></bib:authors>\n"
                    f"    <dc:title>{x(e['title'])}</dc:title>\n"
                    f"    <dc:date>{year(e)}</dc:date>\n"
                    f"    <dc:identifier><dcterms:URI><rdf:value>{x(e['URL'])}</rdf:value></dcterms:URI></dc:identifier>\n"
                    f"  </bib:Document>\n")
        items.append(item)
    return head + "".join(items) + "</rdf:RDF>\n"


def main() -> None:
    entries = load()
    (REF_DIR / "references.bib").write_text(to_bibtex(entries), encoding="utf-8")
    (REF_DIR / "references.ris").write_text(to_ris(entries), encoding="utf-8")
    (REF_DIR / "references.rdf").write_text(to_zotero_rdf(entries), encoding="utf-8")
    print(f"Exported {len(entries)} entries to BibTeX, RIS and Zotero RDF in {REF_DIR}")


if __name__ == "__main__":
    main()
