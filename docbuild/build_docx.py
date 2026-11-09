"""Build the dissertation Word file from Markdown chapters into the proposal template.

Pipeline (run from ``Code``)::

    python docbuild/build_docx.py          # writes Doc/Dissertation_Hybrid_ARIMA-LSTM.docx
    python docbuild/word_automation.py     # updates every field in Word and exports the PDF
    python docbuild/citation_audit.py      # integrity checks -> Doc/citation_audit_report.md

What the builder does:

1. Copies the proposal template and keeps only its first page (the title page
   table). Styles, theme, header (logo) and footer (centred page number) are
   inherited.
2. Adds three sections: title page (no page number), front matter (lower-case
   roman page numbers) and main text (arabic numbers from 1).
3. Writes the front matter with real Word fields (TOC, List of Figures, List
   of Tables), then the chapters parsed from ``docbuild/chapters/*.md``.
4. Captions use ``STYLEREF``/``SEQ`` fields (table captions above tables,
   figure captions below figures); cross-references are ``REF`` fields to
   bookmarks; citations are internal hyperlinks to bookmarked reference-list
   entries generated from ``Refrence/references.json``.

Markdown dialect: see ``docbuild/README.md``.
"""

from __future__ import annotations

import copy
import csv
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import docx
import latex2mathml.converter
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import citations  # noqa: E402

CODE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CODE_DIR.parent
TEMPLATE = PROJECT_ROOT / "Input" / (
    "A Hybrid ARIMA-LSTM Framework for Retail Sales Forecasting with Business Intelligence Integration.docx")
OUT_DOCX = PROJECT_ROOT / "Doc" / "Dissertation_Hybrid_ARIMA-LSTM.docx"
CHAPTER_DIR = CODE_DIR / "docbuild" / "chapters"
REFS_JSON = PROJECT_ROOT / "Refrence" / "references.json"
MML2OMML = Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL")
TITLE_PAGE_ELEMENTS = 9  # body children 0..8 form the proposal's first page
TEXT_WIDTH_TWIPS = 9026  # A4 width minus 2 x 2.54 cm margins
ALLOWED_STATUS = {"VERIFIED", "EXCEPTION_APPROVED", "TECHNICAL_DOC"}
FONT = "Arial"
HEADING_COLOURS = {1: "365F91", 2: "365F91", 3: "243F60"}
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

INLINE = re.compile(
    r"(?P<cite>\[@[^\]]+\])"
    r"|(?P<narr>(?<![\w\[@/.])@[A-Za-z][\w\-]*)"
    r"|(?P<xref>\{(?:fig|tbl|sec|eq|app):[\w\-]+\})"
    r"|(?P<pending>\[\[PENDING:[^\]]*\]\])"
    r"|(?P<math>\\\(.+?\\\))"
    r"|(?P<bold>\*\*.+?\*\*)"
    r"|(?P<ital>\*[^*\s][^*]*?\*)"
    r"|(?P<code>`[^`]+`)"
    r"|(?P<link>\[[^\]]+\]\(https?://[^)]+\))"
)


# --------------------------------------------------------------------------- low-level XML helpers


def set_run_font(run, size=None, bold=None, italic=None, font=FONT, colour=None):
    run.font.name = font
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if colour:
        run.font.color.rgb = RGBColor.from_string(colour)


def add_field(paragraph, instr: str, result: str, style: str | None = None):
    """Complex field (begin / instrText / separate / result / end)."""

    def mk(kind):
        r = paragraph.add_run()
        if style:
            r.style = style
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), kind)
        r._r.append(fc)
        return r

    mk("begin")
    r = paragraph.add_run()
    if style:
        r.style = style
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)
    mk("separate")
    res = paragraph.add_run(result)
    if style:
        res.style = style
    mk("end")
    return res


class Bookmarks:
    def __init__(self):
        self.next_id = 100
        self.names: set[str] = set()

    def start(self, paragraph, name: str):
        if name in self.names:
            raise ValueError(f"Duplicate bookmark {name}")
        self.names.add(name)
        bid = str(self.next_id)
        self.next_id += 1
        el = OxmlElement("w:bookmarkStart")
        el.set(qn("w:id"), bid)
        el.set(qn("w:name"), name)
        paragraph._p.append(el)
        return bid

    @staticmethod
    def end(paragraph, bid: str):
        el = OxmlElement("w:bookmarkEnd")
        el.set(qn("w:id"), bid)
        paragraph._p.append(el)


def internal_link(paragraph, anchor: str, text: str, style: str = "Citation Link"):
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("w:anchor"), anchor)
    hl.set(qn("w:history"), "1")
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rs = OxmlElement("w:rStyle")
    rs.set(qn("w:val"), style.replace(" ", ""))
    rpr.append(rs)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    hl.append(r)
    paragraph._p.append(hl)


def external_link(paragraph, url: str, text: str):
    rid = paragraph.part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hl = OxmlElement("w:hyperlink")
    hl.set(qn("r:id"), rid)
    hl.set(qn("w:history"), "1")
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rs = OxmlElement("w:rStyle")
    rs.set(qn("w:val"), "Hyperlink")
    rpr.append(rs)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    hl.append(r)
    paragraph._p.append(hl)


def latex_to_omml(latex: str):
    mathml = latex2mathml.converter.convert(latex)
    xslt = etree.XSLT(etree.parse(str(MML2OMML)))
    omml = xslt(etree.fromstring(mathml.encode("utf-8")))
    return omml.getroot()


# --------------------------------------------------------------------------- styles and numbering


def _ensure_style(doc, name: str, kind=WD_STYLE_TYPE.PARAGRAPH, base: str | None = None):
    styles = doc.styles
    try:
        st = styles[name]
    except KeyError:
        st = styles.add_style(name, kind)
    if base:
        st.base_style = styles[base]
    return st


def _font(style, size, bold=False, italic=False, colour=None, font=FONT):
    style.font.name = font
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(attr), font)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
        if rf.get(qn(attr)) is not None:
            del rf.attrib[qn(attr)]
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    if colour:
        style.font.color.rgb = RGBColor.from_string(colour)


def _spacing(style, before=0, after=0, line=None, rule="auto"):
    ppr = style.element.get_or_add_pPr()
    sp = ppr.find(qn("w:spacing"))
    if sp is None:
        sp = OxmlElement("w:spacing")
        ppr.append(sp)
    sp.set(qn("w:before"), str(before))
    sp.set(qn("w:after"), str(after))
    if line:
        sp.set(qn("w:line"), str(line))
        sp.set(qn("w:lineRule"), rule)


def _ppr_flag(style, tag: str, on: bool = True):
    ppr = style.element.get_or_add_pPr()
    el = ppr.find(qn(tag))
    if on and el is None:
        ppr.append(OxmlElement(tag))
    if not on and el is not None:
        ppr.remove(el)


def _tab(style, pos: int, align="right", leader="dot"):
    ppr = style.element.get_or_add_pPr()
    tabs = ppr.find(qn("w:tabs"))
    if tabs is None:
        tabs = OxmlElement("w:tabs")
        ppr.insert(0, tabs)
    for t in list(tabs):
        tabs.remove(t)
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), align)
    tab.set(qn("w:leader"), leader)
    tab.set(qn("w:pos"), str(pos))
    tabs.append(tab)


def setup_styles(doc) -> int:
    """Create or adjust the styles used by the dissertation; returns the heading numId."""
    body = _ensure_style(doc, "Body Text", base="Normal")
    _font(body, 12)
    _spacing(body, before=0, after=120, line=480)  # handbook: double line spacing
    body.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    body.paragraph_format.widow_control = True

    for level, size in ((1, 16), (2, 14), (3, 12)):
        st = doc.styles[f"Heading {level}"]
        _font(st, size, bold=True, colour=HEADING_COLOURS[level])
        _spacing(st, before={1: 0, 2: 360, 3: 240}[level], after={1: 360, 2: 120, 3: 120}[level],
                 line=276)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _ppr_flag(doc.styles["Heading 1"], "w:pageBreakBefore", True)

    toc_head = _ensure_style(doc, "TOC Heading", base="Heading 1")
    ppr = toc_head.element.get_or_add_pPr()
    ol = ppr.find(qn("w:outlineLvl"))
    if ol is None:
        ol = OxmlElement("w:outlineLvl")
        ppr.append(ol)
    ol.set(qn("w:val"), "9")
    numpr = OxmlElement("w:numPr")
    nid = OxmlElement("w:numId")
    nid.set(qn("w:val"), "0")
    numpr.append(nid)
    ppr.insert(0, numpr)

    for i in (1, 2, 3):
        st = doc.styles[f"toc {i}"] if f"toc {i}" in [s.name for s in doc.styles] else _ensure_style(doc, f"toc {i}", base="Normal")
        _font(st, 11, bold=(i == 1))
        _spacing(st, before=60 if i == 1 else 0, after=60, line=276)
        _tab(st, TEXT_WIDTH_TWIPS)
        st.paragraph_format.left_indent = Cm(0.39 * (i - 1))
    tof = _ensure_style(doc, "table of figures", base="Normal")
    _font(tof, 11)
    _spacing(tof, before=0, after=60, line=276)
    _tab(tof, TEXT_WIDTH_TWIPS)

    cap = _ensure_style(doc, "Caption", base="Normal")
    _font(cap, 10, bold=True, colour="365F91")
    _spacing(cap, before=120, after=120, line=240)
    cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    src = _ensure_style(doc, "Source Note", base="Normal")
    _font(src, 9, italic=True)
    _spacing(src, before=60, after=240, line=240)
    src.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    tt = _ensure_style(doc, "Table Text", base="Normal")
    _font(tt, 9.5)
    _spacing(tt, before=20, after=20, line=240)
    tt.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    fig = _ensure_style(doc, "Figure Image", base="Normal")
    _spacing(fig, before=120, after=0, line=240)
    fig.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fig.paragraph_format.keep_with_next = True

    code = _ensure_style(doc, "Code", base="Normal")
    _font(code, 8.5, font="Courier New")
    _spacing(code, before=60, after=120, line=240)
    code.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F2F2F2")
    code.element.get_or_add_pPr().append(shd)

    eq = _ensure_style(doc, "Equation", base="Normal")
    _font(eq, 12)
    _spacing(eq, before=120, after=120, line=276)
    ppr = eq.element.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    for val, pos in (("center", TEXT_WIDTH_TWIPS // 2), ("right", TEXT_WIDTH_TWIPS)):
        t = OxmlElement("w:tab")
        t.set(qn("w:val"), val)
        t.set(qn("w:pos"), str(pos))
        tabs.append(t)
    ppr.insert(0, tabs)

    bib = _ensure_style(doc, "Bibliography", base="Normal")
    _font(bib, 11)
    _spacing(bib, before=0, after=120, line=360)
    bib.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    bib.paragraph_format.left_indent = Cm(1.27)
    bib.paragraph_format.first_line_indent = Cm(-1.27)

    lp = doc.styles["List Paragraph"]
    _font(lp, 12)
    _spacing(lp, before=0, after=60, line=480)
    lp.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    abbr = _ensure_style(doc, "Abbreviation", base="Normal")
    _font(abbr, 11)
    _spacing(abbr, before=0, after=60, line=276)
    abbr.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    ppr = abbr.element.get_or_add_pPr()
    tabs = OxmlElement("w:tabs")
    t = OxmlElement("w:tab")
    t.set(qn("w:val"), "left")
    t.set(qn("w:pos"), "1985")
    tabs.append(t)
    ppr.insert(0, tabs)
    abbr.paragraph_format.left_indent = Cm(3.5)
    abbr.paragraph_format.first_line_indent = Cm(-3.5)

    cite = _ensure_style(doc, "Citation Link", kind=WD_STYLE_TYPE.CHARACTER)
    cite.font.underline = False
    cite.font.color.rgb = None

    return _heading_numbering(doc)


def _heading_numbering(doc) -> int:
    """Multilevel list 1 / 1.1 / 1.1.1 attached to Heading 1-3."""
    numbering = doc.part.numbering_part.element
    abs_ids = [int(a.get(qn("w:abstractNumId"))) for a in numbering.findall(qn("w:abstractNum"))]
    num_ids = [int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))]
    aid, nid = max(abs_ids) + 1, max(num_ids) + 1
    absn = OxmlElement("w:abstractNum")
    absn.set(qn("w:abstractNumId"), str(aid))
    mlt = OxmlElement("w:multiLevelType")
    mlt.set(qn("w:val"), "multilevel")
    absn.append(mlt)
    for lvl in range(3):
        el = OxmlElement("w:lvl")
        el.set(qn("w:ilvl"), str(lvl))
        for tag, val in (("w:start", "1"), ("w:numFmt", "decimal"), ("w:pStyle", f"Heading{lvl + 1}"),
                         ("w:suff", "tab"),
                         ("w:lvlText", ".".join(f"%{i + 1}" for i in range(lvl + 1))), ("w:lvlJc", "left")):
            e = OxmlElement(tag)
            e.set(qn("w:val"), val)
            el.append(e)
        ppr = OxmlElement("w:pPr")
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), str(567 + 284 * lvl))
        ind.set(qn("w:hanging"), str(567 + 284 * lvl))
        ppr.append(ind)
        el.append(ppr)
        absn.append(el)
    first_num = numbering.find(qn("w:num"))
    if first_num is not None:
        first_num.addprevious(absn)
    else:
        numbering.append(absn)
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(nid))
    an = OxmlElement("w:abstractNumId")
    an.set(qn("w:val"), str(aid))
    num.append(an)
    numbering.append(num)
    for lvl in range(3):
        st = doc.styles[f"Heading {lvl + 1}"]
        ppr = st.element.get_or_add_pPr()
        old = ppr.find(qn("w:numPr"))
        if old is not None:
            ppr.remove(old)
        numpr = OxmlElement("w:numPr")
        il = OxmlElement("w:ilvl")
        il.set(qn("w:val"), str(lvl))
        ni = OxmlElement("w:numId")
        ni.set(qn("w:val"), str(nid))
        numpr.append(il)
        numpr.append(ni)
        ppr.insert(0, numpr)
    return nid


def new_list_instance(doc, abstract_id: int) -> int:
    """A fresh w:num restarting at 1 for a numbered list."""
    numbering = doc.part.numbering_part.element
    nid = max(int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))) + 1
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(nid))
    an = OxmlElement("w:abstractNumId")
    an.set(qn("w:val"), str(abstract_id))
    num.append(an)
    ov = OxmlElement("w:lvlOverride")
    ov.set(qn("w:ilvl"), "0")
    so = OxmlElement("w:startOverride")
    so.set(qn("w:val"), "1")
    ov.append(so)
    num.append(ov)
    numbering.append(num)
    return nid


# --------------------------------------------------------------------------- markdown model


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    attrs: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)


ATTR_RE = re.compile(r"\{([^}]*)\}\s*$")


def parse_attrs(spec: str) -> dict:
    attrs = {}
    for tok in spec.split():
        if tok == "-":
            attrs["unnumbered"] = True
        elif tok.startswith("#"):
            attrs["id"] = tok[1:]
        elif tok.startswith("."):
            attrs[tok[1:]] = True
        elif "=" in tok:
            k, v = tok.split("=", 1)
            attrs[k] = v.strip('"')
    return attrs


def parse_markdown(text: str) -> list[Block]:
    lines = text.splitlines()
    blocks: list[Block] = []
    i = 0
    para: list[str] = []

    def flush():
        if para:
            blocks.append(Block("para", " ".join(s.strip() for s in para)))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("<!--"):
            while "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if not s:
            flush()
            i += 1
            continue
        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            flush()
            title = m.group(2)
            attrs = {}
            am = ATTR_RE.search(title)
            if am:
                attrs = parse_attrs(am.group(1))
                title = title[: am.start()].strip()
            blocks.append(Block("heading", title, len(m.group(1)), attrs))
            i += 1
            continue
        if s.startswith(":::"):
            flush()
            head = s[3:].strip().split(None, 1)
            kind = head[0]
            attrs = parse_attrs(head[1]) if len(head) > 1 else {}
            body = []
            i += 1
            while not lines[i].strip().startswith(":::"):
                body.append(lines[i])
                i += 1
            i += 1
            meta, rest = {}, []
            for b in body:
                mm = re.match(r"^(caption|source|alt|note):\s*(.*)$", b.strip())
                if mm and not rest:
                    meta[mm.group(1)] = mm.group(2)
                elif mm and mm.group(1) in ("source", "note"):
                    meta[mm.group(1)] = mm.group(2)
                else:
                    rest.append(b)
            attrs.update(meta)
            blocks.append(Block(kind, "", 0, attrs, rest))
            continue
        if s.startswith("```"):
            flush()
            body = []
            i += 1
            while not lines[i].strip().startswith("```"):
                body.append(lines[i].rstrip())
                i += 1
            i += 1
            blocks.append(Block("code", "", 0, {}, body))
            continue
        if s.startswith("$$"):
            flush()
            content = s[2:]
            while "$$" not in content:
                i += 1
                if i >= len(lines):
                    raise ValueError("Unclosed $$ display equation")
                content += " " + lines[i].strip()
            latex, tail = content.split("$$", 1)
            am = ATTR_RE.search(tail)
            attrs = parse_attrs(am.group(1)) if am else {}
            blocks.append(Block("equation", latex.strip(), 0, attrs))
            i += 1
            continue
        if s == "\\pagebreak":
            flush()
            blocks.append(Block("pagebreak"))
            i += 1
            continue
        lm = re.match(r"^(-|\d+\.)\s+(.*)$", s)
        if lm and not para:
            items, ordered = [], lm.group(1) != "-"
            while i < len(lines):
                ls = lines[i].strip()
                mm = re.match(r"^(-|\d+\.)\s+(.*)$", ls)
                if mm:
                    items.append(mm.group(2))
                elif ls and items and lines[i].startswith(("  ", "\t")):
                    items[-1] += " " + ls
                else:
                    break
                i += 1
            blocks.append(Block("list", "", 0, {"ordered": ordered}, items))
            continue
        para.append(line)
        i += 1
    flush()
    return blocks


# --------------------------------------------------------------------------- builder


@dataclass
class Label:
    kind: str
    number: str
    bookmark: str


class Builder:
    def __init__(self, template: Path, refs: Path | None):
        self.doc = docx.Document(str(template))
        self.bm = Bookmarks()
        self.lib = citations.load_library(refs) if refs and refs.exists() else {}
        self.cited: list[str] = []
        self.labels: dict[str, Label] = {}
        self.warnings: list[str] = []
        self.heading_num_id = setup_styles(self.doc)
        self.bullet_num_id = 5
        self.decimal_abstract = 3
        self.word_counts: dict[str, int] = {}
        self.current_part = "front"
        self.figure_alts: list[str] = []
        self.citations_by_part: dict[str, int] = {}
        self.current_section = ""
        self.cite_sections: dict[str, list[str]] = {}

    # ---------------- pass 1: numbering of labelled objects
    def assign_numbers(self, chapters: list[tuple[str, list[Block]]]):
        chap, sec2, sec3 = 0, 0, 0
        ctx = None
        counters = {"fig": 0, "tbl": 0, "eq": 0}
        for _, blocks in chapters:
            for b in blocks:
                if b.kind == "heading":
                    if b.level == 1:
                        sec2 = sec3 = 0
                        counters = {"fig": 0, "tbl": 0, "eq": 0}
                        if b.attrs.get("appendix"):
                            ctx = b.attrs.get("letter")
                        elif b.attrs.get("unnumbered"):
                            ctx = None
                        else:
                            chap += 1
                            ctx = str(chap)
                        num = ctx or ""
                    elif b.level == 2:
                        sec2 += 1
                        sec3 = 0
                        num = f"{ctx}.{sec2}" if ctx and not b.attrs.get("unnumbered") else ""
                    else:
                        sec3 += 1
                        num = f"{ctx}.{sec2}.{sec3}" if ctx and not b.attrs.get("unnumbered") else ""
                    b.attrs["_num"] = num
                    if "id" in b.attrs:
                        self._label(b.attrs["id"], "sec", num)
                elif b.kind in ("figure", "table") or (b.kind == "equation" and "id" in b.attrs):
                    key = {"figure": "fig", "table": "tbl", "equation": "eq"}[b.kind]
                    counters[key] += 1
                    if ctx is None:
                        raise ValueError(f"{b.kind} outside a numbered chapter or appendix")
                    b.attrs["_number"] = f"{ctx}.{counters[key]}"
                    b.attrs["_ctx"] = ctx
                    b.attrs["_seq"] = counters[key]
                    if "id" in b.attrs:
                        self._label(b.attrs["id"], key, b.attrs["_number"])

    def _label(self, ident: str, kind: str, number: str):
        if ident in self.labels:
            raise ValueError(f"Duplicate label {ident}")
        bm = re.sub(r"[^A-Za-z0-9_]", "_", ident)
        if kind in ("fig", "tbl", "eq"):
            bm = "_Ref_" + bm
        self.labels[ident] = Label(kind, number, bm[:40])

    # ---------------- inline rendering
    def inline(self, p, text: str, base: dict | None = None):
        base = base or {}
        pos = 0
        for m in INLINE.finditer(text):
            if m.start() > pos:
                self._run(p, text[pos: m.start()], base)
            kind = m.lastgroup
            tok = m.group(0)
            if kind == "cite":
                self._cite(p, tok[1:-1])
            elif kind == "narr":
                self._narrative(p, tok[1:])
            elif kind == "xref":
                self._xref(p, tok[1:-1])
            elif kind == "pending":
                r = p.add_run(tok[2:-2])
                set_run_font(r, bold=True, size=base.get("size"))
                r.font.highlight_color = 7  # yellow
            elif kind == "math":
                p._p.append(latex_to_omml(tok[2:-2]))
            elif kind == "bold":
                self._run(p, tok[2:-2], {**base, "bold": True})
            elif kind == "ital":
                self._run(p, tok[1:-1], {**base, "italic": True})
            elif kind == "code":
                self._run(p, tok[1:-1], {**base, "font": "Courier New", "size": (base.get("size") or 12) - 1.5})
            elif kind == "link":
                lm = re.match(r"\[([^\]]+)\]\((https?://[^)]+)\)", tok)
                external_link(p, lm.group(2), lm.group(1))
            pos = m.end()
        if pos < len(text):
            self._run(p, text[pos:], base)

    def _run(self, p, text, fmt):
        if not text:
            return
        r = p.add_run(text)
        if fmt.get("font") or fmt.get("size") or fmt.get("bold") or fmt.get("italic"):
            set_run_font(r, size=fmt.get("size"), bold=fmt.get("bold"), italic=fmt.get("italic"),
                         font=fmt.get("font", FONT))
        return r

    def _entry(self, key: str):
        if key not in self.lib:
            raise KeyError(f"Citation key not in references.json: {key}")
        e = self.lib[key]
        status = e.data.get("ledger_status")
        if status not in ALLOWED_STATUS:
            raise ValueError(f"{key} has ledger status {status!r}; only {sorted(ALLOWED_STATUS)} may be cited")
        if key not in self.cited:
            self.cited.append(key)
        sec = self.current_section
        if sec and sec not in self.cite_sections.setdefault(key, []):
            self.cite_sections[key].append(sec)
        self.citations_by_part[self.current_part] = self.citations_by_part.get(self.current_part, 0) + 1
        return e

    def _cite(self, p, body: str):
        parts = citations.parse_citation(body)
        self._run(p, "(", {})
        for i, (key, loc) in enumerate(parts):
            e = self._entry(key)
            label = f"{e.in_text_names()}, {e.year_label()}" + (f", {loc}" if loc else "")
            internal_link(p, e.bookmark(), label)
            if i < len(parts) - 1:
                self._run(p, "; ", {})
        self._run(p, ")", {})

    def _narrative(self, p, key: str):
        e = self._entry(key)
        internal_link(p, e.bookmark(), f"{e.in_text_names()} ({e.year_label()})")

    def _xref(self, p, ident: str):
        if ident.startswith("app:"):
            letter = ident.split(":", 1)[1]
            self._run(p, "Appendix ", {})
            lab = self.labels.get(ident)
            if lab is None:
                raise KeyError(f"Unknown appendix label {ident}")
            add_field(p, f"REF {lab.bookmark} \\h", letter)
            return
        lab = self.labels.get(ident)
        if lab is None:
            raise KeyError(f"Unknown cross-reference {ident}")
        if lab.kind == "sec":
            self._run(p, "Section ", {})
            add_field(p, f"REF {lab.bookmark} \\r \\h", lab.number)
        elif lab.kind == "eq":
            add_field(p, f"REF {lab.bookmark} \\h", f"({lab.number})")
        else:
            word = "Figure" if lab.kind == "fig" else "Table"
            add_field(p, f"REF {lab.bookmark} \\h", f"{word} {lab.number}")

    # ---------------- block rendering
    def body_paragraph(self, text: str):
        p = self.doc.add_paragraph(style="Body Text")
        self.inline(p, text)
        self._count(text)
        return p

    def _count(self, text: str):
        clean = re.sub(r"\[@[^\]]+\]", " ", text)
        clean = re.sub(r"\{(fig|tbl|sec|eq|app):[\w\-]+\}", " ref ", clean)
        clean = re.sub(r"\\\(.+?\\\)", " x ", clean)
        n = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-\.%]*", clean))
        self.word_counts[self.current_part] = self.word_counts.get(self.current_part, 0) + n

    def heading(self, b: Block):
        if b.attrs.get("toc_heading"):
            p = self.doc.add_paragraph(b.text, style="TOC Heading")
            return p
        p = self.doc.add_paragraph(style=f"Heading {b.level}")
        if b.level <= 2:
            self.current_section = b.attrs.get("_num", "")
        if b.attrs.get("appendix") and b.level == 1:
            self.current_section = "App. " + b.attrs.get("letter", "")
        if b.attrs.get("unnumbered") or b.attrs.get("appendix"):
            ppr = p._p.get_or_add_pPr()
            numpr = OxmlElement("w:numPr")
            ni = OxmlElement("w:numId")
            ni.set(qn("w:val"), "0")
            numpr.append(ni)
            ppr.insert(0, numpr)
        if b.attrs.get("appendix"):
            # Bookmark only the letter so that {app:X} cross-references read "Appendix X".
            m = re.match(r"^Appendix\s+([A-Z])\s*:\s*(.*)$", b.text)
            if not m or "id" not in b.attrs:
                raise ValueError(f"Appendix heading must read 'Appendix X: Title' and carry an id: {b.text}")
            self._run(p, "Appendix ", {})
            bid = self.bm.start(p, self.labels[b.attrs["id"]].bookmark)
            self._run(p, m.group(1), {})
            Bookmarks.end(p, bid)
            self._run(p, ": ", {})
            self.inline(p, m.group(2))
            return p
        bid = None
        if "id" in b.attrs:
            bid = self.bm.start(p, self.labels[b.attrs["id"]].bookmark)
        self.inline(p, b.text)
        if bid:
            Bookmarks.end(p, bid)
        return p

    def _caption(self, kind: str, b: Block):
        word = "Figure" if kind == "fig" else "Table"
        p = self.doc.add_paragraph(style="Caption")
        p.paragraph_format.keep_with_next = True
        ident = b.attrs.get("id")
        bm = self.labels[ident].bookmark if ident else f"_Ref_auto_{kind}_{self.bm.next_id}"
        bid = self.bm.start(p, bm)
        self._run(p, f"{word} ", {})
        if b.attrs["_ctx"].isdigit():
            add_field(p, "STYLEREF 1 \\s", b.attrs["_ctx"])
        else:
            self._run(p, b.attrs["_ctx"], {})
        self._run(p, ".", {})
        add_field(p, f"SEQ {word} \\* ARABIC \\s 1", str(b.attrs["_seq"]))
        Bookmarks.end(p, bid)
        self._run(p, ": ", {})
        self.inline(p, b.attrs.get("caption", ""))
        return p

    def _source(self, text: str, keep_next=False):
        p = self.doc.add_paragraph(style="Source Note")
        p.paragraph_format.keep_with_next = keep_next
        self.inline(p, text, {"size": 9, "italic": True})
        return p

    def figure(self, b: Block):
        path = CODE_DIR / b.attrs["file"]
        if not path.exists():
            raise FileNotFoundError(path)
        p = self.doc.add_paragraph(style="Figure Image")
        run = p.add_run()
        run.add_picture(str(path), width=Cm(float(b.attrs.get("width", 15.5))))
        alt = b.attrs.get("alt") or b.attrs.get("caption", "")
        doc_pr = run._r.find(".//" + qn("wp:docPr"))
        doc_pr.set("descr", alt)
        doc_pr.set("title", b.attrs.get("caption", "")[:120])
        self.figure_alts.append(alt)
        cap = self._caption("fig", b)
        cap.paragraph_format.keep_with_next = True
        self._source(b.attrs.get("source", "Author's own work."))

    def table(self, b: Block):
        rows = self._table_rows(b)
        self._caption("tbl", b)
        n_cols = len(rows[0])
        table = self.doc.add_table(rows=len(rows), cols=n_cols)
        table.style = self.doc.styles["Table Grid"]
        widths = [float(w) for w in b.attrs["widths"].split(",")] if "widths" in b.attrs else None
        size = float(b.attrs.get("size", 9.5))
        aligns = b.attrs.get("align", "")
        for i, row in enumerate(rows):
            tr = table.rows[i]._tr
            trpr = tr.get_or_add_trPr()
            cant = OxmlElement("w:cantSplit")
            trpr.append(cant)
            if i == 0:
                hdr = OxmlElement("w:tblHeader")
                trpr.append(hdr)
            for j, cell_text in enumerate(row):
                cell = table.cell(i, j)
                para = cell.paragraphs[0]
                para.style = self.doc.styles["Table Text"]
                if aligns and j < len(aligns) and aligns[j] == "r":
                    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif aligns and j < len(aligns) and aligns[j] == "c":
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                self.inline(para, cell_text.strip(), {"size": size, "bold": i == 0})
                if i == 0:
                    tcpr = cell._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), "DBE5F1")
                    tcpr.append(shd)
                if i < len(rows) - 1:
                    para.paragraph_format.keep_with_next = True
                if widths:
                    cell.width = Cm(widths[j])
        self._source(b.attrs.get("source", "Author's own work."))

    def _table_rows(self, b: Block) -> list[list[str]]:
        if "csv" in b.attrs:
            path = CODE_DIR / b.attrs["csv"]
            if not path.exists():
                # Draft builds only: the final build requires every table (see final_check).
                self.warnings.append(f"Missing table source {b.attrs['csv']}")
                return [["Pending"], [f"[[PENDING: table generated from {b.attrs['csv']}]]"]]
            with path.open(encoding="utf-8") as handle:
                return [row for row in csv.reader(handle)]
        rows = []
        for line in b.lines:
            s = line.strip()
            if not s or re.match(r"^\|?\s*:?-{2,}", s):
                continue
            cells = [c for c in s.strip("|").split("|")]
            rows.append(cells)
        return rows

    def equation(self, b: Block):
        p = self.doc.add_paragraph(style="Equation")
        p.add_run("\t")
        p._p.append(latex_to_omml(b.text))
        p.add_run("\t")
        if "id" in b.attrs:
            bid = self.bm.start(p, self.labels[b.attrs["id"]].bookmark)
            self._run(p, "(", {})
            ctx = b.attrs["_ctx"]
            if ctx.isdigit():
                add_field(p, "STYLEREF 1 \\s", ctx)
            else:
                self._run(p, ctx, {})
            self._run(p, ".", {})
            add_field(p, "SEQ Equation \\* ARABIC \\s 1", str(b.attrs["_seq"]))
            self._run(p, ")", {})
            Bookmarks.end(p, bid)

    def bullet_list(self, b: Block):
        num_id = new_list_instance(self.doc, self.decimal_abstract) if b.attrs.get("ordered") else self.bullet_num_id
        for item in b.lines:
            p = self.doc.add_paragraph(style="List Paragraph")
            ppr = p._p.get_or_add_pPr()
            numpr = OxmlElement("w:numPr")
            il = OxmlElement("w:ilvl")
            il.set(qn("w:val"), "0")
            ni = OxmlElement("w:numId")
            ni.set(qn("w:val"), str(num_id))
            numpr.append(il)
            numpr.append(ni)
            ppr.insert(1, numpr)
            self.inline(p, item)
            self._count(item)

    def code(self, b: Block):
        p = self.doc.add_paragraph(style="Code")
        for i, line in enumerate(b.lines):
            r = p.add_run(line)
            set_run_font(r, size=8.5, font="Courier New")
            if i < len(b.lines) - 1:
                r.add_break()

    def abbreviations(self, b: Block):
        for line in b.lines:
            if "|" not in line:
                continue
            term, meaning = [x.strip() for x in line.strip().strip("|").split("|", 1)]
            p = self.doc.add_paragraph(style="Abbreviation")
            self._run(p, term, {"bold": True, "size": 11})
            self._run(p, "\t" + meaning, {"size": 11})

    def render(self, blocks: list[Block], part: str):
        self.current_part = part
        for b in blocks:
            if b.kind == "heading":
                self.heading(b)
            elif b.kind == "para":
                self.body_paragraph(b.text)
            elif b.kind == "figure":
                self.figure(b)
            elif b.kind == "table":
                self.table(b)
            elif b.kind == "equation":
                self.equation(b)
            elif b.kind == "list":
                self.bullet_list(b)
            elif b.kind == "code":
                self.code(b)
            elif b.kind == "abbreviations":
                self.abbreviations(b)
            elif b.kind == "pagebreak":
                self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            else:
                raise ValueError(f"Unknown block kind {b.kind}")

    # ---------------- front matter, references, sections
    def field_list(self, title: str, instr: str, placeholder: str):
        self.doc.add_paragraph(title, style="TOC Heading")
        p = self.doc.add_paragraph()
        add_field(p, instr, placeholder)

    def references(self):
        h = self.doc.add_paragraph(style="Heading 1")
        ppr = h._p.get_or_add_pPr()
        numpr = OxmlElement("w:numPr")
        ni = OxmlElement("w:numId")
        ni.set(qn("w:val"), "0")
        numpr.append(ni)
        ppr.insert(0, numpr)
        run = h.add_run("References")
        entries = sorted((self.lib[k] for k in self.cited), key=lambda e: e.sort_key())
        for e in entries:
            p = self.doc.add_paragraph(style="Bibliography")
            bid = self.bm.start(p, e.bookmark())
            for text, fmt in citations.reference_runs(e):
                if fmt.get("url"):
                    external_link(p, fmt["url"], text)
                else:
                    r = p.add_run(text)
                    if fmt.get("italic"):
                        r.italic = True
            Bookmarks.end(p, bid)
        unused = sorted(set(self.lib) - set(self.cited))
        if unused:
            self.warnings.append(f"{len(unused)} library entries not cited (omitted): {unused}")
        return run

    def section_break(self, page_format: str | None, start: int | None, footer: bool):
        """Insert a section break (new page) ending the current section."""
        final = self.doc.element.body.sectPr
        sect = copy.deepcopy(final)
        for fr in sect.findall(qn("w:footerReference")):
            if not footer:
                sect.remove(fr)
        old = sect.find(qn("w:pgNumType"))
        if old is not None:
            sect.remove(old)
        if page_format:
            pg = OxmlElement("w:pgNumType")
            pg.set(qn("w:fmt"), page_format)
            if start:
                pg.set(qn("w:start"), str(start))
            sect.find(qn("w:pgMar")).addnext(pg)
        typ = OxmlElement("w:type")
        typ.set(qn("w:val"), "nextPage")
        sect.insert(0 if sect.find(qn("w:headerReference")) is None else
                    len(sect.findall(qn("w:headerReference"))) + len(sect.findall(qn("w:footerReference"))), typ)
        p = self.doc.add_paragraph()
        p._p.get_or_add_pPr().append(sect)
        return p

    def finalise_sections(self):
        final = self.doc.element.body.sectPr
        old = final.find(qn("w:pgNumType"))
        if old is not None:
            final.remove(old)
        pg = OxmlElement("w:pgNumType")
        pg.set(qn("w:fmt"), "decimal")
        pg.set(qn("w:start"), "1")
        final.find(qn("w:pgMar")).addnext(pg)

    def strip_body_after_title_page(self):
        body = self.doc.element.body
        children = list(body.iterchildren())
        for child in children[TITLE_PAGE_ELEMENTS:]:
            if child.tag != qn("w:sectPr"):
                body.remove(child)

    def settings(self):
        st = self.doc.settings.element
        uf = st.find(qn("w:updateFields"))
        if uf is None:
            uf = OxmlElement("w:updateFields")
            st.append(uf)
        uf.set(qn("w:val"), "true")


def load_chapters() -> list[tuple[str, list[Block]]]:
    files = sorted(CHAPTER_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No chapter files in {CHAPTER_DIR}")
    return [(f.stem, parse_markdown(f.read_text(encoding="utf-8"))) for f in files]


def build(out_path: Path = OUT_DOCX) -> dict:
    chapters = load_chapters()
    front = [c for c in chapters if c[0].startswith("00")]
    main = [c for c in chapters if c[0][:2].isdigit() and 1 <= int(c[0][:2]) < 90]
    back = [c for c in chapters if c[0][:2].isdigit() and int(c[0][:2]) >= 90]
    b = Builder(TEMPLATE, REFS_JSON)
    b.assign_numbers(front + main + back)
    b.strip_body_after_title_page()
    b.settings()
    # Section 1 ends after the title page: no page number on it.
    b.section_break(page_format=None, start=None, footer=False)
    for name, blocks in front:
        b.render(blocks, part=name)
    b.field_list("Table of Contents", 'TOC \\o "1-3" \\h \\z \\u', "Table of contents: update fields in Word (F9).")
    b.field_list("List of Figures", 'TOC \\h \\z \\c "Figure"', "List of figures: update fields in Word (F9).")
    b.field_list("List of Tables", 'TOC \\h \\z \\c "Table"', "List of tables: update fields in Word (F9).")
    b.section_break(page_format="lowerRoman", start=1, footer=True)
    for name, blocks in main:
        b.render(blocks, part=name)
    ref_run = b.references()
    for name, blocks in back:
        b.render(blocks, part=name)
    b.finalise_sections()
    try:
        b.doc.add_comment(
            [ref_run],
            text=("Provisional format: standard Harvard modelled on the Arden examples in the module "
                  "materials, pending the Arden Referencing Guide (AU_Guide_to_Harvard_Citation.pdf)."),
            author="Dissertation build", initials="DB")
    except Exception as exc:  # noqa: BLE001 - comments are a convenience, not essential
        b.warnings.append(f"Could not add comment: {exc}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    b.doc.save(str(out_path))
    return {"out": str(out_path), "cited": b.cited, "word_counts": b.word_counts,
            "warnings": b.warnings, "labels": {k: v.number for k, v in b.labels.items()},
            "citations_by_part": b.citations_by_part, "cite_sections": b.cite_sections}


if __name__ == "__main__":
    import json

    info = build()
    build_dir = CODE_DIR / "docbuild" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "build_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (build_dir / "cite_sections.json").write_text(json.dumps(info["cite_sections"], indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k not in ("labels", "cite_sections")}, indent=2))
