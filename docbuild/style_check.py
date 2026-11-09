"""Style checks for the chapter Markdown (British English and AWE writing rules).

Usage (from ``Code``)::

    python docbuild/style_check.py

Reports, per chapter and line:

* American spellings from a list of common variants;
* contractions;
* em and en dashes (the house style uses none);
* stand-alone numerals one to ten in running text (words are required,
  except with units, percentages, ranges, versions, labels and tables);
* one-sentence paragraphs (excluding list lead-ins ending with a colon).

Quoted text is ignored, because quotations keep the source's spelling.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHAPTERS = Path(__file__).resolve().parent / "chapters"

AMERICAN = {
    r"\b(\w+)iz(e|es|ed|ing|ation|ations)\b": "-ise",
    r"\bcolor": "colour", r"\bbehavior": "behaviour", r"\bmodeling\b": "modelling", r"\bmodeled\b": "modelled",
    r"\blabeled\b": "labelled", r"\blabeling\b": "labelling", r"\bcenter": "centre", r"\banalyz": "analys",
    r"\butiliz": "utilis", r"\bfavor": "favour", r"\bprogram\b": "programme", r"\bdefense\b": "defence",
    r"\blicense\b": "licence (noun)", r"\bcatalog\b": "catalogue", r"\btraveled\b": "travelled",
    r"\bfulfill\b": "fulfil", r"\benrollment\b": "enrolment", r"\bgray\b": "grey", r"\bmeter\b": "metre",
}
ISE_EXCEPTIONS = {"size", "sizes", "sized", "prize", "seize", "capsize", "resize", "resized", "citizen"}
CONTRACTION = re.compile(r"\b\w+(n't|'re|'ve|'ll|'d|'m)\b|\b(it's|that's|there's|let's|what's)\b", re.I)
DASHES = re.compile("[–—]")
SMALL_NUM = re.compile(r"(?<![\w.,/\-(\\{$])(?:[1-9]|10)(?![\w.%,\-/:)}]|\s*(?:%|days?\b|weeks?\b|months?\b|years?\b|pt\b|cm\b|W\b|GB\b|points?\b|steps?\b|step-ahead))")
QUOTE = re.compile(r'"[^"]*"')


def strip_noise(line: str) -> str:
    line = QUOTE.sub('""', line)
    line = re.sub(r"\[@[^\]]+\]|@\w+|\{[^}]*\}|\\\(.+?\\\)|`[^`]*`|\[\[[^\]]*\]\]|<[^>]+>", " ", line)
    return line


def check(path: Path) -> list[str]:
    issues = []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_block = False
    para: list[tuple[int, str]] = []

    def flush_para():
        if para:
            text = " ".join(t for _, t in para)
            sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z@{])", text) if s.strip()]
            if len(sentences) == 1 and not text.rstrip().endswith(":") and not text.startswith(("**", "[[")):
                issues.append(f"{path.name}:{para[0][0]}: one-sentence paragraph: {text[:80]}")
            para.clear()

    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith(":::") or s.startswith("```"):
            in_block = not in_block if s.startswith("```") or s == ":::" or s.startswith("::: ") else in_block
            if s.startswith("::: "):
                in_block = True
            elif s == ":::":
                in_block = False
            flush_para()
            continue
        if in_block or s.startswith(("|", "$$", "caption:", "source:", "alt:")):
            flush_para()
            continue
        if not s or s.startswith("#"):
            flush_para()
            continue
        text = strip_noise(s)
        for pattern, fix in AMERICAN.items():
            for m in re.finditer(pattern, text, flags=re.I):
                word = m.group(0).lower()
                if fix == "-ise" and (word in ISE_EXCEPTIONS or word.startswith(("size", "prize"))):
                    continue
                issues.append(f"{path.name}:{i}: American spelling '{m.group(0)}' (use {fix})")
        if CONTRACTION.search(text):
            issues.append(f"{path.name}:{i}: contraction '{CONTRACTION.search(text).group(0)}'")
        if DASHES.search(raw):
            issues.append(f"{path.name}:{i}: en or em dash")
        if not re.match(r"^(-|\d+\.)\s", s):
            for m in SMALL_NUM.finditer(text):
                issues.append(f"{path.name}:{i}: numeral '{m.group(0)}' in text: ...{text[max(0, m.start()-30):m.end()+30]}...")
            para.append((i, s))
        else:
            flush_para()
            for m in SMALL_NUM.finditer(re.sub(r"^(-|\d+\.)\s", "", text)):
                issues.append(f"{path.name}:{i}: numeral '{m.group(0)}' in list item")
    flush_para()
    return issues


def main() -> int:
    all_issues = []
    for path in sorted(CHAPTERS.glob("*.md")):
        all_issues += check(path)
    print("\n".join(all_issues) if all_issues else "No style issues found.")
    print(f"\n{len(all_issues)} issue(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
