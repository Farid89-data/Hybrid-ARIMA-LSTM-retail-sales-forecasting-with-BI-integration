"""Harvard citation and reference formatting from a CSL-JSON library.

Formats follow the Arden University Harvard guide: journal articles (5.2.1,
no URL or access date), chapters in edited books (5.1.5), books and web pages
or datasets (5.6.1, with URL and access date). All authors are listed in the
reference list.

Rules implemented:

* In text: one author ``(Smith, 2024)``; two ``(Smith and Jones, 2024)``;
  three or more ``(Smith et al., 2024)``. Several sources in one citation are
  ordered chronologically (see ``order_keys``). Same author(s) and year are
  disambiguated with letters (2024a, 2024b) ordered by title.
* Reference list ordered by first-author surname, then year, then letter.
* Bookmark names ``ref_<library key>`` (letters and digits only,
  at most 40 characters) link every citation to its entry.
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ACCESS_DATE_DEFAULT = "9 November 2026"


def ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def initials(given: str) -> str:
    """'Peter J.' -> 'P.J.'; hyphenated names keep the hyphen ('Jean-Luc' -> 'J.-L.')."""
    out = []
    for part in re.split(r"\s+", given.strip()):
        if not part:
            continue
        hy = [p for p in part.split("-") if p]
        out.append("-".join(p[0].upper() + "." for p in hy))
    return "".join(out)


@dataclass
class Entry:
    key: str
    data: dict
    letter: str = ""

    @property
    def authors(self) -> list[dict]:
        return self.data.get("author") or [{"literal": self.data.get("publisher", "Anon.")}]

    @property
    def year(self) -> str:
        parts = (self.data.get("issued") or {}).get("date-parts") or [[None]]
        return str(parts[0][0]) if parts[0][0] else "n.d."

    def surname(self, a: dict) -> str:
        return a.get("family") or a.get("literal") or ""

    def in_text_names(self) -> str:
        names = [self.surname(a) for a in self.authors]
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return f"{names[0]} et al."

    def year_label(self) -> str:
        return f"{self.year}{self.letter}"

    def bookmark(self) -> str:
        """Bookmark name built from the unique library key (letters and digits only)."""
        base = re.sub(r"[^a-z0-9]", "", ascii_fold(self.key).lower()) or "anon"
        return f"ref_{base}"[:40]

    def sort_key(self):
        return (ascii_fold(self.surname(self.authors[0])).lower(), self.year, self.letter,
                ascii_fold(self.data.get("title", "")).lower())


def load_library(path: Path) -> dict[str, Entry]:
    """Load CSL-JSON and assign year letters where author list and year collide."""
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = {it["id"]: Entry(it["id"], it) for it in items}
    groups: dict[tuple, list[Entry]] = {}
    for e in entries.values():
        groups.setdefault((e.in_text_names(), e.year), []).append(e)
    for members in groups.values():
        if len(members) > 1:
            members.sort(key=lambda e: ascii_fold(e.data.get("title", "")).lower())
            for i, e in enumerate(members):
                e.letter = "abcdefghijklmnopqrstuvwxyz"[i]
    return entries


def author_list(entry: Entry) -> str:
    """'Surname, A.B., Surname, C. and Surname, D.,' (corporate authors as written)."""
    parts = []
    for a in entry.authors:
        if a.get("literal"):
            parts.append(a["literal"])
        else:
            parts.append(f"{a.get('family', '')}, {initials(a.get('given', ''))}".strip())
    if len(parts) == 1:
        text = parts[0]
    else:
        text = ", ".join(parts[:-1]) + " and " + parts[-1]
    return text + ("," if not text.endswith(".") else ",")


# Journal names whose library spelling is inconsistent or mis-encoded: mapped here, not in the data.
JOURNAL_FIXES = {"plos one": "PLOS ONE"}


def journal_name(name: str) -> str:
    """Unescape HTML entities and normalise known spelling variants."""
    name = html.unescape(name or "").strip()
    return JOURNAL_FIXES.get(name.lower(), name)


def _names(people: list[dict]) -> str:
    """'Surname, I., Surname, J. and Surname, K.' (no trailing comma)."""
    parts = [f"{p.get('family', '')}, {initials(p.get('given', ''))}".strip() for p in people]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def order_keys(items: list[tuple[str, str]], lib: dict[str, Entry]) -> list[tuple[str, str]]:
    """Order (key, locator) pairs chronologically, then by year letter and author surname."""
    def k(item):
        e = lib[item[0]]
        return (e.year, e.letter, ascii_fold(e.surname(e.authors[0])).lower())
    return sorted(items, key=k)


def reference_runs(entry: Entry) -> list[tuple[str, dict]]:
    """Reference list entry as (text, formatting) runs; formatting keys: italic, url."""
    d = entry.data
    typ = d.get("type", "article-journal")
    accessed = d.get("accessed_text", ACCESS_DATE_DEFAULT)
    runs: list[tuple[str, dict]] = [(f"{author_list(entry)} ({entry.year_label()}). ", {})]
    title = d.get("title", "").rstrip(".")
    place, pub = d.get("publisher-place"), d.get("publisher")
    imprint = f"{place}: {pub}" if place and pub else (pub or "")
    if typ in ("article-journal", "paper-conference", "article"):
        # Guide 5.2.1: no URL or accessed date for online journal articles.
        runs.append((f"{title}. ", {}))
        runs.append((journal_name(d.get("container-title", "")), {"italic": True}))
        detail = " [online]"
        vol, iss = d.get("volume"), d.get("issue")
        if vol:
            detail += f", {vol}"
            if iss:
                detail += f" ({iss})"
        if d.get("page"):
            pages = d["page"].replace("–", "-")
            detail += f", {'pp.' if '-' in pages else 'p.'} {pages}"
        elif d.get("number"):
            detail += f", article {d['number']}"
        runs.append((detail + ". ", {}))
        return runs
    if typ == "chapter":
        runs.append((f"{title}. In: ", {}))
        eds = d.get("editor") or []
        if eds:
            runs.append((f"{_names(eds)}, {'eds' if len(eds) > 1 else 'ed'}. ", {}))
        runs.append((d.get("container-title", ""), {"italic": True}))
        tail = " [online]. " + imprint
        if d.get("page"):
            tail += f", pp. {d['page'].replace(chr(8211), '-')}"
        runs.append((tail + ".", {}))
        return runs
    if typ == "book":
        runs.append((title, {"italic": True}))
        tail = " [online]. "
        if d.get("edition"):
            ed = str(d["edition"])
            tail += f"{ed}{'' if not ed.isdigit() else _ordinal(int(ed))} edition. "
        tail += f"{imprint}. " if imprint else ""
        runs.append((tail, {}))
    else:  # webpage, dataset, software documentation (guide 5.6.1)
        runs.append((title, {"italic": True}))
        runs.append((" [online]. ", {}))
        if imprint:
            runs.append((f"{imprint}. ", {}))
    url = f"https://doi.org/{d['DOI']}" if d.get("DOI") else d.get("URL")
    if url:
        runs.append(("Available from: ", {}))
        runs.append((url, {"url": url}))
        runs.append((f" [Accessed {accessed}].", {}))
    return runs


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def parse_citation(body: str) -> list[tuple[str, str]]:
    """'@a; @b, p. 5' -> [('a', ''), ('b', 'p. 5')]."""
    out = []
    for part in body.split(";"):
        part = part.strip()
        m = re.match(r"@([A-Za-z][\w\-]*)\s*(?:,\s*(.+))?$", part)
        if not m:
            raise ValueError(f"Malformed citation: [{body}]")
        out.append((m.group(1), (m.group(2) or "").strip()))
    return out
