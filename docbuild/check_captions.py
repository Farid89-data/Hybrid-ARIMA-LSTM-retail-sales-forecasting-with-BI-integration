"""Check the caption layout of the built Word document.

Rules (build fails if one is broken):

* a table caption is the paragraph directly above its table, centred, with keep-with-next;
* a figure caption is the paragraph directly below its figure, centred, with keep-with-next;
  the figure paragraph itself is centred and keeps with the caption;
* a source line (style "Source Note", centred) follows directly below the table, or below the
  figure caption;
* captions are Word captions: they contain a SEQ field;
* numbers are continuous within each chapter or appendix: Table 3.1, 3.2, ... and Table A.1, A.2, ...

Usage (from ``Code``)::

    python docbuild/check_captions.py [path to .docx]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

DEFAULT = Path(__file__).resolve().parents[2] / "Doc" / "Dissertation_Hybrid_ARIMA-LSTM.docx"


def _style(p) -> str:
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        return ""
    st = ppr.find(qn("w:pStyle"))
    return st.get(qn("w:val")) if st is not None else ""


def _text(p) -> str:
    return "".join(t.text or "" for t in p.iter(qn("w:t"))).replace("‎", "").replace("‏", "")


def _has(p, tag: str) -> bool:
    return p.find(".//" + qn(tag)) is not None


def _keep_next(p, style_keep: bool) -> bool:
    ppr = p.find(qn("w:pPr"))
    if ppr is not None and ppr.find(qn("w:keepNext")) is not None:
        return True
    return style_keep


def problems(path: Path = DEFAULT) -> list[str]:
    doc = Document(str(path))
    body = doc.element.body
    kids = [k for k in body if k.tag in (qn("w:p"), qn("w:tbl"))]
    styles = {s.name.lower(): s for s in doc.styles}
    styles.setdefault("caption", styles.get("caption1"))
    out: list[str] = []
    for name in ("Caption", "Source Note"):
        al = styles[name.lower()].paragraph_format.alignment
        if al is None or int(al) != 1:
            out.append(f"style {name} is not centred")
    fig_style_keep = bool(styles["figure image"].paragraph_format.keep_with_next)
    seen: dict[tuple[str, str], int] = {}
    n_tbl = n_fig = 0
    for i, el in enumerate(kids):
        if el.tag != qn("w:p") or not _style(el).lower().startswith("caption"):
            continue
        text = _text(el)
        m = re.match(r"(Table|Figure) ([A-Z0-9]+)\.(\d+): ", text)
        if not m:
            if re.match(r"(Table|Figure) ", text):
                out.append(f"caption not in the form 'Table X.Y: Title': {text[:50]}")
            continue
        kind, ctx, num = m.group(1), m.group(2), int(m.group(3))
        key = (kind, ctx)
        if seen.get(key, 0) + 1 != num:
            out.append(f"{kind} {ctx}.{num} follows {seen.get(key, 0)} (numbering not continuous)")
        seen[key] = num
        if not _has(el, "w:instrText") or "SEQ" not in "".join(t.text or "" for t in el.iter(qn("w:instrText"))):
            out.append(f"{kind} {ctx}.{num} has no SEQ field")
        if not _keep_next(el, bool(styles["caption"].paragraph_format.keep_with_next)):
            out.append(f"{kind} {ctx}.{num}: caption does not keep with next")
        nxt = kids[i + 1] if i + 1 < len(kids) else None
        prv = kids[i - 1] if i > 0 else None
        if kind == "Table":
            n_tbl += 1
            if nxt is None or nxt.tag != qn("w:tbl"):
                out.append(f"Table {ctx}.{num}: caption is not directly above its table")
            else:
                after = kids[i + 2] if i + 2 < len(kids) else None
                if after is None or after.tag != qn("w:p") or _style(after) not in ("Source Note", "SourceNote"):
                    out.append(f"Table {ctx}.{num}: no source line directly below the table")
        else:
            n_fig += 1
            if prv is None or prv.tag != qn("w:p") or _style(prv) != "FigureImage" and _style(prv) != "Figure Image":
                if prv is None or not (_has(prv, "w:drawing") or "PENDING: figure" in _text(prv)):
                    out.append(f"Figure {ctx}.{num}: caption is not directly below its figure")
            else:
                if not _keep_next(prv, fig_style_keep):
                    out.append(f"Figure {ctx}.{num}: figure does not keep with its caption")
            if nxt is None or nxt.tag != qn("w:p") or _style(nxt) != "SourceNote" and _style(nxt) != "Source Note":
                out.append(f"Figure {ctx}.{num}: no source line directly below the caption")
    if n_tbl == 0 or n_fig == 0:
        out.append("no captions found")
    return out


def pdf_problems(pdf: Path | None = None) -> list[str]:
    """Page-by-page check of the exported PDF: continuous numbers; no caption cut off from its table or figure."""
    import pymupdf

    pdf = pdf or DEFAULT.with_suffix(".pdf")
    out: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    doc = pymupdf.open(str(pdf))
    for pno, page in enumerate(doc, start=1):
        height = page.rect.height
        foot = [b[4].strip() for b in page.get_text("blocks") if b[1] > height - 70 and b[4].strip()]
        if foot and re.fullmatch(r"[ivxlc]+", foot[0].lower()):
            continue  # front matter: the lists of figures and tables repeat the captions
        blocks = [b for b in page.get_text("blocks") if b[3] < height - 55 and b[1] > 45 and b[4].strip()]
        blocks.sort(key=lambda b: b[1])
        imgs = page.get_image_info()
        for k, b in enumerate(blocks):
            m = re.match(r"(Table|Figure)\s*([A-Z0-9]+)\.(\d+):", b[4].strip())
            if not m:
                continue
            kind, ctx, num = m.group(1), m.group(2), int(m.group(3))
            key = (kind, ctx)
            if seen.get(key, 0) + 1 != num:
                out.append(f"page {pno}: {kind} {ctx}.{num} follows {seen.get(key, 0)}")
            seen[key] = num
            if kind == "Table" and k == len(blocks) - 1:
                out.append(f"page {pno}: Table {ctx}.{num} caption is the last block on the page (table starts on the next page)")
            if kind == "Figure":
                above = [i for i in imgs if i["bbox"][3] <= b[1] + 2 and b[1] - i["bbox"][3] < 40]
                if not above:
                    out.append(f"page {pno}: Figure {ctx}.{num} caption has no image directly above it on the same page")
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    found = problems(target)
    if target.with_suffix(".pdf").exists():
        found += pdf_problems(target.with_suffix(".pdf"))
    for p in found:
        print("CAPTION CHECK:", p)
    print("Caption layout OK" if not found else f"{len(found)} caption problem(s)")
    sys.exit(1 if found else 0)
