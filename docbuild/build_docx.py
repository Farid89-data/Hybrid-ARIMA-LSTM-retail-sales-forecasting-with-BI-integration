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
4. Captions are centred and use ``STYLEREF``/``SEQ`` fields (table captions above tables,
   figure captions below figures, a centred source line below the table or the figure caption); cross-references are ``REF`` fields to
   bookmarks; citations are internal hyperlinks to bookmarked reference-list
   entries generated from ``Refrence/references.json``.

Markdown dialect: see ``docbuild/README.md``.
"""

from __future__ import annotations

import copy
import csv
import json
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
IDENTITY_JSON = CODE_DIR / "docbuild" / "identity.json"
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


def set_table_title(table, title: str, description: str = "") -> None:
    """Give a table its own accessible title (w:tblCaption) and description.

    Word and tagged PDF export otherwise associate captions with tables by
    position only, which can attach a caption to the wrong table (D04).
    """
    tbl_pr = table._tbl.tblPr
    for tag in ("w:tblCaption", "w:tblDescription"):
        for old in tbl_pr.findall(qn(tag)):
            tbl_pr.remove(old)
    cap = OxmlElement("w:tblCaption")
    cap.set(qn("w:val"), title[:255])
    tbl_pr.append(cap)
    if description:
        desc = OxmlElement("w:tblDescription")
        desc.set(qn("w:val"), description[:1000])
        tbl_pr.append(desc)


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
    cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    src = _ensure_style(doc, "Source Note", base="Normal")
    _font(src, 9, italic=True)
    _spacing(src, before=60, after=240, line=240)
    src.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

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
        parts = citations.order_keys(citations.parse_citation(body), self.lib)
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
        # Guide 3.4.3: own work carries the text "(personal collection)".
        text = re.sub(r"^(Author's own \w+)(?! \(personal collection\))", lambda m: m.group(1) + " (personal collection)", text)
        p = self.doc.add_paragraph(style="Source Note")
        p.paragraph_format.keep_with_next = keep_next
        self.inline(p, text, {"size": 9, "italic": True})
        return p

    def figure(self, b: Block):
        path = CODE_DIR / b.attrs["file"]
        alt = b.attrs.get("alt") or b.attrs.get("caption", "")
        p = self.doc.add_paragraph(style="Figure Image")
        if not path.exists():
            # Draft builds only: a highlighted placeholder keeps the caption, so cross-references resolve.
            generator = b.attrs.get("generator", "the evaluation pipeline")
            self.warnings.append(f"Missing figure {b.attrs['file']}")
            self.inline(p, f"[[PENDING: figure {path.name} is generated by {generator} after the evaluation]]", {})
        else:
            run = p.add_run()
            run.add_picture(str(path), width=Cm(float(b.attrs.get("width", 15.5))))
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
        label = self.labels[b.attrs["id"]].number if "id" in b.attrs else ""
        set_table_title(table, f"Table {label}: {b.attrs.get('caption', '')}".strip(),
                        b.attrs.get("alt", b.attrs.get("caption", "")))
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
                # Short tables stay on one page. For long tables only the first two and the last two rows
                # are chained, so that the caption stays with the header and the source line with the end.
                if len(rows) <= 20 or i < 2 or i >= len(rows) - 2:
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
        # The title-page table is not a numbered table: give it its own title so that no
        # caption is associated with it (D04).
        if self.doc.tables:
            set_table_title(self.doc.tables[0], "Title page",
                            "Awarding body, programme, module, assessment title, student name, student number, tutor and word count")

    def apply_identity(self, identity: dict) -> None:
        """Write the config values into title-page rows, inserting Student Name row.

        Inserts a new row 4 for Student Name before the original Student Number row,
        so final order is: university, programme, module, title, student_name, student_number, tutor_name, word_count.
        Guard: does not add a second row if Student Name row already exists.
        """
        table = self.doc.tables[0]

        # Guard: check if Student Name row already exists
        student_name_row_exists = any(
            "Student Name:" in "".join(r.text for p in row.cells[0].paragraphs for r in p.runs)
            for row in table.rows
        )

        if not student_name_row_exists:
            # Copy row 4 (Student Number) and insert it before row 4
            student_number_row_elem = table.rows[4]._tr
            new_row_elem = copy.deepcopy(student_number_row_elem)
            student_number_row_elem.addprevious(new_row_elem)

            # Process the new row to set label and value
            # After insertion, the new row is at index 4 in table.rows
            new_row = table.rows[4]
            for para in new_row.cells[0].paragraphs:
                runs = list(para.runs)
                if not runs:
                    continue

                # Find and remove image runs
                image_run_indices = [i for i, r in enumerate(runs)
                                     if r._r.find(qn("w:drawing")) is not None or r._r.find(qn("w:pict")) is not None]

                if image_run_indices:
                    # This is the label paragraph - remove images and set label text
                    for i in reversed(image_run_indices):
                        para._element.remove(runs[i]._r)

                    # Add text run with "Student Name:" label (simpler than trying to replace)
                    label_run = para.add_run("Student Name:")
                    set_run_font(label_run, size=16, bold=False, font="Calibri")  # matches the label images
                else:
                    # This is the value paragraph - set student name value
                    # Only process if there are no image runs (i.e., this is a text paragraph)
                    # and if we find runs that don't end with " ("
                    if runs and not any(r.text.endswith(" (") for r in runs):
                        # This looks like the value paragraph - but only if it doesn't have suffix
                        text_run_indices = [i for i, r in enumerate(runs) if r.text and not r.text.endswith(" (")]
                        if text_run_indices:
                            # Find the first non-empty, non-suffix run and replace it with the value
                            runs[text_run_indices[0]].text = identity["student_name"]

        # Apply standard values to rows after Student Name has been inserted
        # Row indices: 0=univ, 1=prog, 2=mod, 3=title, 4=student_name (now set above), 5=student_number, 6=tutor, 7=wordcount
        values_map = [
            (0, identity["university"]),
            (1, identity["programme"]),
            (2, identity["module"]),
            (3, identity["title"]),
            (5, identity["student_number"]),
            (6, identity["tutor_name"]),
        ]

        for row_idx, value in values_map:
            if row_idx >= len(table.rows):
                continue
            row = table.rows[row_idx]
            for para in row.cells[0].paragraphs:
                runs = [r for r in para.runs if r.text]
                if not runs:
                    continue
                # Anything from the " (" of "(Project Proposal)" onward is the template's suffix.
                cut = next((i for i, r in enumerate(runs) if r.text.endswith(" (")), len(runs))
                runs[0].text = value
                for r in runs[1:cut]:
                    r.text = ""

    def finalise_title_page(self, main_word_count: int) -> None:
        """Final build only (D03): module line without "(Project Proposal)" and the real word count."""
        table = self.doc.tables[0]
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = "".join(r.text for r in para.runs)
                    if "(Project Proposal)" in text:
                        drop = False
                        for run in para.runs:
                            if run.text.strip() == "(" or run.text.endswith(" ("):
                                run.text = run.text[: -len(" (")] if run.text.endswith(" (") else ""
                                drop = True
                            elif drop:
                                run.text = ""
                    if text.strip() == "1767":
                        for run in para.runs:
                            if run.text.strip() == "1767":
                                run.text = f"{main_word_count:,}"

    def settings(self):
        st = self.doc.settings.element
        uf = st.find(qn("w:updateFields"))
        if uf is None:
            uf = OxmlElement("w:updateFields")
            st.append(uf)
        uf.set(qn("w:val"), "true")


def load_identity(path: Path = IDENTITY_JSON) -> dict:
    """The student's identity details: the single source for the title page (D11)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


SUBJECT_KEYWORDS = "ARIMA; LSTM; hybrid forecasting; retail sales; Power BI"
_BANNED_CORE = ("claude", "anthropic", "jshort", "frd ngb", "gpt", "copilot")


def _set_core_properties(document, identity: dict) -> None:
    """Set the core properties from the identity; blank inherited values that name someone else."""
    cp = document.core_properties
    name = identity["student_name"]
    cp.author = name
    cp.last_modified_by = name
    cp.title = identity["title"]
    cp.subject = f"{identity['module']} ({identity['programme']})"
    cp.keywords = SUBJECT_KEYWORDS
    cp.comments = ""
    for attr in ("category", "content_status", "identifier", "version"):
        if getattr(cp, attr):
            setattr(cp, attr, "")


def _set_app_properties(document, identity: dict) -> None:
    """docProps/app.xml: Company = university, Manager blank (python-docx does not expose it)."""
    for part in document.part.package.iter_parts():
        if str(part.partname) != "/docProps/app.xml":
            continue
        root = etree.fromstring(part.blob)
        changed = False
        for tag, value in (("Company", identity["university"]), ("Manager", "")):
            for el in root.iter("{*}" + tag):
                if (el.text or "") != value:
                    el.text = value
                    changed = True
        if changed:
            part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def apply_core_properties(docx_path: Path, identity: dict | None = None) -> None:
    """Re-open a saved .docx and (re)apply the identity metadata (Word rewrites Last Modified By)."""
    identity = identity or load_identity()
    document = docx.Document(str(docx_path))
    _set_core_properties(document, identity)
    _set_app_properties(document, identity)
    document.save(str(docx_path))


def title_page_values(docx_path: Path) -> list[str]:
    """Visible value text of each title-page table row (label images carry no text)."""
    table = docx.Document(str(docx_path)).tables[0]
    return ["".join(r.text for p in row.cells[0].paragraphs for r in p.runs).strip() for row in table.rows]


def load_chapters() -> list[tuple[str, list[Block]]]:
    files = sorted(CHAPTER_DIR.glob("*.md"))
    if not files:
        raise FileNotFoundError(f"No chapter files in {CHAPTER_DIR}")
    return [(f.stem, parse_markdown(f.read_text(encoding="utf-8"))) for f in files]


MAIN_PARTS = ("01", "02", "03", "04", "05")


def back_citation_keys(back: list, lib: dict) -> list[str]:
    """Library keys cited in the back matter, including CSV tables referenced there."""
    texts = []
    for _, blocks in back:
        for blk in blocks:
            texts.append(blk.text or "")
            texts.extend(blk.lines or [])
            if blk.attrs.get("csv") and (CODE_DIR / blk.attrs["csv"]).exists():
                texts.append((CODE_DIR / blk.attrs["csv"]).read_text(encoding="utf-8"))
    found = []
    for key in re.findall(r"@([A-Za-z][A-Za-z0-9_]*)", "\n".join(texts)):
        if key in lib and key not in found:
            found.append(key)
    return found


def main_word_count(word_counts: dict) -> int:
    """Words in the body text of Chapters 1 to 5 (tables, captions, references and appendices excluded)."""
    return sum(n for part, n in word_counts.items() if part[:2] in MAIN_PARTS)


def build(out_path: Path = OUT_DOCX, final: bool = False) -> dict:
    from check_test_count import problems as test_count_problems  # noqa: PLC0415
    mismatches = test_count_problems()
    if mismatches:
        raise RuntimeError("Test count differs between the JUnit file and the report: " + "; ".join(mismatches))
    chapters = load_chapters()
    front = [c for c in chapters if c[0].startswith("00")]
    main = [c for c in chapters if c[0][:2].isdigit() and 1 <= int(c[0][:2]) < 90]
    back = [c for c in chapters if c[0][:2].isdigit() and int(c[0][:2]) >= 90]
    b = Builder(TEMPLATE, REFS_JSON)
    b.assign_numbers(front + main + back)
    b.strip_body_after_title_page()
    b.apply_identity(load_identity())
    b.settings()
    # Section 1 ends after the title page: no page number on it.
    b.section_break(page_format=None, start=None, footer=False)
    for name, blocks in front:
        if "abbrev" not in name:
            b.render(blocks, part=name)
    b.field_list("Table of Contents", 'TOC \\o "1-3" \\h \\z \\u', "Table of contents: update fields in Word (F9).")
    b.field_list("List of Figures", 'TOC \\h \\z \\c "Figure"', "List of figures: update fields in Word (F9).")
    b.field_list("List of Tables", 'TOC \\h \\z \\c "Table"', "List of tables: update fields in Word (F9).")
    for name, blocks in front:
        if "abbrev" in name:  # the list of abbreviations follows the lists of figures and tables
            b.render(blocks, part=name)
    b.section_break(page_format="lowerRoman", start=1, footer=True)
    for name, blocks in main:
        b.render(blocks, part=name)
    # The reference list precedes the appendices, so keys cited only in appendices (text or
    # generated CSV tables) are collected first; otherwise their links would have no target.
    for key in back_citation_keys(back, b.lib):
        if key not in b.cited:
            b.cited.append(key)
    ref_run = b.references()
    for name, blocks in back:
        b.render(blocks, part=name)
    b.finalise_sections()
    if final:
        b.finalise_title_page(main_word_count(b.word_counts))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _set_core_properties(b.doc, load_identity())
    _set_app_properties(b.doc, load_identity())
    b.doc.save(str(out_path))
    from check_captions import problems as caption_problems  # noqa: PLC0415
    bad = caption_problems(out_path)
    if bad:
        raise RuntimeError("Caption layout check failed: " + "; ".join(bad[:10]))
    return {"out": str(out_path), "cited": b.cited, "word_counts": b.word_counts,
            "warnings": b.warnings, "labels": {k: v.number for k, v in b.labels.items()},
            "citations_by_part": b.citations_by_part, "cite_sections": b.cite_sections}


def check_fields_updated(docx_path: Path) -> list[str]:
    """Return any field placeholder text left in the document after the Word update (D05)."""
    import zipfile

    xml = zipfile.ZipFile(docx_path).read("word/document.xml").decode("utf-8")
    return sorted(set(re.findall(r"(Table of contents|List of figures|List of tables): update fields in Word", xml)))


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build the dissertation .docx")
    parser.add_argument("--final", action="store_true",
                        help="final build: update the title page and run Word to update all fields and export the PDF")
    parser.add_argument("--no-word", action="store_true", help="skip the Word field update (draft builds only)")
    args = parser.parse_args()
    info = build(final=args.final)
    info["main_word_count"] = main_word_count(info["word_counts"])
    if not args.no_word:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from word_automation import update_and_export  # noqa: PLC0415

        info["word"] = update_and_export(Path(info["out"]))
        apply_core_properties(Path(info["out"]))
        leftovers = check_fields_updated(Path(info["out"]))
        if leftovers:
            raise SystemExit(f"Fields not updated: {leftovers}")
        info["fields_updated"] = True
    build_dir = CODE_DIR / "docbuild" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "build_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    (build_dir / "cite_sections.json").write_text(json.dumps(info["cite_sections"], indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k not in ("labels", "cite_sections")}, indent=2))
