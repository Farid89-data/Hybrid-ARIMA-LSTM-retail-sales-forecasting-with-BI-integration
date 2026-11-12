"""Update every field in Microsoft Word, save, and export a PDF with bookmarks and links.

Requires Microsoft Word on Windows (COM automation through ``pywin32``).
Fields are updated twice so that cross-references pick up caption numbers
after the tables of contents and figures have been regenerated.

Usage (from ``Code``)::

    python docbuild/word_automation.py [path/to/file.docx]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pythoncom
import win32com.client as win32

CODE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DOCX = CODE_DIR.parent / "Doc" / "Dissertation_Hybrid_ARIMA-LSTM.docx"

WD_EXPORT_FORMAT_PDF = 17
WD_EXPORT_OPTIMIZE_FOR_PRINT = 0
WD_EXPORT_ALL_DOCUMENT = 0
WD_EXPORT_DOCUMENT_CONTENT = 0
WD_EXPORT_CREATE_HEADING_BOOKMARKS = 1
WD_STATISTIC_PAGES = 2
WD_STATISTIC_WORDS = 0


def set_pdf_metadata(pdf_path: Path, identity_path: Path | None = None) -> bool:
    """Rewrite the PDF Title/Author/Subject/Creator to the docx values (PyMuPDF; pypdf if present)."""
    import json  # noqa: PLC0415

    identity = json.loads((identity_path or Path(__file__).with_name("identity.json")).read_text(encoding="utf-8"))
    meta = {"title": identity["title"], "author": identity["student_name"],
            "subject": f"{identity['module']} ({identity['programme']})", "creator": "Microsoft Word"}
    try:
        import pymupdf as fitz  # noqa: PLC0415
    except ImportError:
        try:
            import fitz  # noqa: PLC0415
        except ImportError:
            fitz = None
    if fitz is not None:
        pdf = fitz.open(str(pdf_path))
        current = dict(pdf.metadata or {})
        current.update(meta)
        pdf.set_metadata(current)
        pdf.saveIncr()
        pdf.close()
        return True
    try:
        from pypdf import PdfReader, PdfWriter  # noqa: PLC0415
    except ImportError:
        return False
    writer = PdfWriter(clone_from=PdfReader(str(pdf_path)))
    writer.add_metadata({"/Title": meta["title"], "/Author": meta["author"],
                         "/Subject": meta["subject"], "/Creator": meta["creator"]})
    with open(pdf_path, "wb") as handle:
        writer.write(handle)
    return True


def update_and_export(docx_path: Path, pdf_path: Path | None = None) -> dict:
    docx_path = docx_path.resolve()
    pdf_path = (pdf_path or docx_path.with_suffix(".pdf")).resolve()
    pythoncom.CoInitialize()
    word = win32.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    info = {}
    try:
        doc = word.Documents.Open(str(docx_path), ConfirmConversions=False, ReadOnly=False,
                                  AddToRecentFiles=False)
        for _ in range(2):
            doc.Fields.Update()
            for toc in doc.TablesOfContents:
                toc.Update()
            for tof in doc.TablesOfFigures:
                tof.Update()
            for section in doc.Sections:
                for hf in list(section.Headers) + list(section.Footers):
                    hf.Range.Fields.Update()
        doc.Repaginate()
        for toc in doc.TablesOfContents:
            toc.UpdatePageNumbers()
        for tof in doc.TablesOfFigures:
            tof.UpdatePageNumbers()
        info["pages"] = doc.ComputeStatistics(WD_STATISTIC_PAGES)
        info["words_all_text"] = doc.ComputeStatistics(WD_STATISTIC_WORDS)
        info["fields"] = doc.Fields.Count
        info["field_errors"] = [
            f.Code.Text.strip() for f in doc.Fields
            if "Error!" in (f.Result.Text if f.Result is not None else "")
        ]
        doc.Save()
        doc.ExportAsFixedFormat(
            OutputFileName=str(pdf_path),
            ExportFormat=WD_EXPORT_FORMAT_PDF,
            OpenAfterExport=False,
            OptimizeFor=WD_EXPORT_OPTIMIZE_FOR_PRINT,
            Range=WD_EXPORT_ALL_DOCUMENT,
            Item=WD_EXPORT_DOCUMENT_CONTENT,
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=WD_EXPORT_CREATE_HEADING_BOOKMARKS,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )
        doc.Close(SaveChanges=False)
        info["pdf"] = str(pdf_path)
        info["pdf_metadata_rewritten"] = set_pdf_metadata(pdf_path)
    finally:
        word.Quit()
        time.sleep(1)
    return info


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOCX
    print(update_and_export(target))
