"""Verification checks for the submission build (D, P1 to P6). Prints one line per check:
``ID PASS|FAIL evidence``.  Usage (from ``Code``): python scripts/verify_all.py [ID ...]

Reads files with grep-style scans only; it does not build the document.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
ROOT = CODE.parent
CH = CODE / "docbuild" / "chapters"
RESULTS: list[tuple[str, bool, str]] = []


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=CODE, capture_output=True, text=True, encoding="utf-8").stdout


def text(name: str) -> str:
    return (CH / name).read_text(encoding="utf-8")


def rec(cid: str, ok: bool, ev: str) -> None:
    RESULTS.append((cid, ok, ev))


def d1() -> None:
    files = git("ls-files").splitlines()
    bad = [f for f in files if re.search(r"outputs/forecasts/|fact_actuals|fact_forecast|Dashboard_screenshots|\.pbix$", f)]
    for f in files:
        p = CODE / f
        if f.endswith((".csv", ".csv.gz")) and p.exists():
            op = gzip.open if f.endswith(".gz") else open
            try:
                with op(p, "rt", encoding="utf-8") as fh:
                    head = fh.readline().lower().split(",")
                if "actual" in head or "sales" in head:
                    bad.append(f)
            except Exception:
                pass
    ign = (CODE / ".gitignore").read_text(encoding="utf-8")
    need = ["fact_actuals.csv", "fact_forecast.csv", "outputs/forecasts/", "Dashboard_screenshots.pdf", "*.pbix"]
    miss = [n for n in need if n not in ign]
    rec("D1", not bad and not miss, f"tracked data files: {bad or 'none'}; missing in .gitignore: {miss or 'none'}")


def d2() -> None:
    p = CODE / "reports" / "history_cleanup.md"
    t = p.read_text(encoding="utf-8") if p.exists() else ""
    need = ["clone --mirror", "filter-repo", "--force-with-lease", "verify_repo", "Consequences"]
    miss = [n for n in need if n not in t]
    rec("D2", p.exists() and not miss, f"missing sections: {miss or 'none'}")


def p1() -> None:
    src = (CODE / "scripts" / "run_evaluation.py").read_text(encoding="utf-8")
    old = re.findall(r"scaled absolute error|Scaled absolute error", src)
    labels = re.findall(r"set_ylabel\(\"([^\"]*)\"", src)
    mase_label = [l for l in labels if "MASE" in l or "absolute scaled" in l]
    figs = sorted((CODE / "outputs" / "figures").glob("res_*_mase_by_horizon.png"))
    newer = all(f.stat().st_mtime >= (CODE / "scripts" / "run_evaluation.py").stat().st_mtime for f in figs)
    rec("P1a", not old and bool(mase_label) and newer and len(figs) == 2,
        f"old-name hits {len(old)}; MASE y-labels {len(mase_label)}; by-horizon PNGs {len(figs)} newer than the script: {newer}")
    # the old name may remain only as the name of the conformal quantity (src/evaluation.py docstring)
    commit = git("log", "--format=%h", "--grep=FIG-1").split()
    if commit:
        diff = git("diff", "--stat", f"{commit[0]}~1", commit[0], "--", "outputs/metrics", "outputs/tables").strip()
        rec("P1b", diff == "", f"FIG-1 commit {commit[0]}: changes to outputs/metrics or tables: {diff or 'none'}")
    else:
        rec("P1b", False, "no FIG-1 commit found")
    q = (CODE / "reports" / "review_queue.md").read_text(encoding="utf-8")
    rec("P1c", "FIG-1" in q and "identical" in q, "FIG-1 log entry with the checksum result present" if "FIG-1" in q else "no log entry")


def pbix_theme() -> list[str]:
    pb = ROOT / "PowerBI" / "Dashboard.pbix"
    with zipfile.ZipFile(pb) as z:
        name = [n for n in z.namelist() if n.endswith("RegisteredResources/ForecastTheme.json")][0]
        return [c.upper() for c in json.loads(z.read(name))["dataColors"][:4]]


def p2() -> None:
    names = ["forecast", "models", "planning"]
    pngs = [(CODE / "outputs" / "figures" / f"dash_built_{n}.png").exists() for n in names]
    app = text("90_appendices.md") + text("04_evaluation.md")
    refd = [f"dash_built_{n}.png" in app for n in names]
    rec("P2a", all(pngs) and all(refd), f"images {sum(pngs)}/3, referenced {sum(refd)}/3")
    ck = (CODE / "dashboard" / "MEASURE_CHECKLIST.md").read_text(encoding="utf-8")
    rows = [l for l in ck.splitlines() if l.startswith("|") and "Acceptance" not in l and "---" not in l]
    unexplained = [l[:60] for l in rows if re.search(r"mismatch", l, re.I) and "not reconciled" not in l.lower()]
    unmarked = [l[:60] for l in rows if "not visible" in l and "to be run" not in l]
    rec("P2b", bool(re.search(r"not\*{0,2} DAX", ck)) and not unexplained and not unmarked,
        f"checklist rows {len(rows)}; says not DAX: {bool(re.search(r'not\*{0,2} DAX', ck))}; unexplained mismatch {len(unexplained)}; unmarked unseen {len(unmarked)}")
    e = text("90_appendices.md")
    tp = [l for l in e.splitlines() if re.match(r"\| TP-(01|02|03|04|05|06|07|08|09|15|16) ", l)]
    rec("P2c", len(tp) == 11 and all("To be run by the author" in l for l in tp), f"interactive TP rows marked to be run: {sum('To be run by the author' in l for l in tp)}/11")
    tracked = git("ls-files", "*.pbix").strip()
    rec("P2d", tracked == "" and "*.pbix" in (CODE / ".gitignore").read_text(encoding="utf-8"), f"tracked pbix: {tracked or 'none'}")
    ch4 = text("04_evaluation.md")
    claims = re.findall(r"all aspects|every aspect|fully accessible|fully tested|fully verified|accessibility (was|were) tested", ch4 + text("90_appendices.md"), re.I)
    hexes = pbix_theme()
    appf = text("90_appendices.md").upper()
    missing_hex = [h for h in hexes if h not in appf]
    rec("P2e", "designed for accessibility" in ch4 and not claims and not missing_hex,
        f"'designed for' present: {'designed for accessibility' in ch4}; absolute claims: {len(claims)}; file palette {hexes}; missing from Appendix F: {missing_hex or 'none'}")


def p3() -> None:
    out = subprocess.run([sys.executable, str(CODE / "docbuild" / "check_captions.py")], cwd=CODE, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    last = (out.stdout.strip().splitlines() or ["(no output)"])[-1]
    b = (CODE / "docbuild" / "build_docx.py").read_text(encoding="utf-8")
    rec("P3a", out.returncode == 0 and "check_captions" in b and "caption_problems" in b, f"{last}; build calls the check: {'caption_problems' in b}")
    rec("P3b", out.returncode == 0, "numbering continuity and page-break checks are part of the same run (docx and PDF)")


def p4() -> None:
    refs = json.loads((ROOT / "Refrence" / "references.json").read_text(encoding="utf-8"))
    e = [r for r in refs if r["id"] == "negahbani2026"]
    ok1 = len(e) == 1 and e[0]["URL"].endswith("Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration") and bool(e[0].get("accessed_text"))
    rec("P4a", ok1, f"entries {len(e)}; URL ok and access date {e[0].get('accessed_text') if e else None}")
    k = "[@negahbani2026]"
    ap = text("90_appendices.md")
    parts = {m.group(1): seg for m, seg in zip(re.finditer(r"^# Appendix ([A-I]):", ap, re.M), re.split(r"^# Appendix [A-I]:", ap, flags=re.M)[1:])}
    where = {"Ch3": k in text("03_development.md"), "Ch4": k in text("04_evaluation.md"),
             "AppE": k in parts.get("E", ""), "AppF": k in parts.get("F", ""), "AppI": k in parts.get("I", "")}
    rec("P4b", all(where.values()), f"cited in: {where}")
    q = (CODE / "reports" / "review_queue.md").read_text(encoding="utf-8")
    top = q[: q.index("## Resolved")] if "## Resolved" in q else q[:4000]
    need = ["history_cleanup", "public", "v1.0-submission"]
    rec("P4c", all(n in top for n in need), f"AUTHOR items at the top mention: {[n for n in need if n in top]}")


def p5() -> None:
    allf = {f.name: f.read_text(encoding="utf-8") for f in CH.glob("*.md")}
    pend = {n: len(re.findall(r"\[\[PENDING", t)) for n, t in allf.items() if "[[PENDING" in t}
    other = {n: c for n, c in pend.items() if not n.startswith("90_")}
    ap = allf["90_appendices.md"]
    lines = [l for l in ap.splitlines() if "[[PENDING" in l]
    ok_lines = [l for l in lines if re.search(r"author|declaration|protocol|align", l, re.I)]
    rec("P5a", not other and len(ok_lines) == len(lines), f"PENDING markers {sum(pend.values())} (author items in appendices A and G: {len(ok_lines)}); outside appendices: {other or 'none'}")
    audit = subprocess.run([sys.executable, str(CODE / "docbuild" / "citation_audit.py")], cwd=CODE, capture_output=True, text=True, encoding="utf-8")
    rec("P5b", "overall PASS" in audit.stdout, (audit.stdout.strip().splitlines() or ["(no output)"])[-1][-60:])
    defs, refs = set(), set()
    for t in allf.values():
        defs |= set(re.findall(r"^::: (?:figure|table) id=([\w:\-]+)", t, re.M))
        refs |= set(re.findall(r"\{((?:fig|tbl):[\w\-]+)\}", re.sub(r"^::: (?:figure|table) id=[^\n]*", "", t, flags=re.M)))
    rec("P5c", not (defs - refs), f"{len(defs)} figure/table ids; never referred to: {sorted(defs - refs) or 'none'}")
    old = [n for n, t in allf.items() if re.search(r"mean scaled absolute|scaled absolute error \(MASE", t, re.I)]
    st = subprocess.run([sys.executable, str(CODE / "docbuild" / "style_check.py")], cwd=CODE, capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    amer = [l for l in st.stdout.splitlines() if "American spelling" in l and "'Program'" not in l and "'meter'" not in l]
    hyb = [n for n, t in allf.items() if not n.startswith("90_") and re.search(r"Hybrid-(Z|D|MS)", t)]
    rec("P5d", not old and not amer and not hyb, f"old metric name in {old or 'none'}; American spellings {len(amer)}; dashboard model names in main text {hyb or 'none'}")


def p6() -> None:
    out = subprocess.run([sys.executable, str(CODE / "docbuild" / "check_test_count.py")], cwd=CODE, capture_output=True, text=True, encoding="utf-8")
    rec("P6a", out.returncode == 0, out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "no output")
    info = json.loads((CODE / "docbuild" / "build" / "build_info.json").read_text(encoding="utf-8"))
    n = info.get("main_word_count") or sum(v for k, v in info["word_counts"].items() if k[:2] in ("01", "02", "03", "04", "05"))
    rec("P6b", n <= 11900, f"main body {n} words (last build)")
    log = git("log", "main..HEAD", "--format=%B%n%ae")
    hits = re.findall(r"co-authored-by|generated with claude|noreply@anthropic\.com", log, re.I)
    rec("P6c", not hits, f"{len(hits)} hits in {len(git('log', 'main..HEAD', '--oneline').splitlines())} commits ahead of main")
    head, rem = git("rev-parse", "HEAD").strip(), git("rev-parse", "origin/audit-fixes").strip()
    rec("P6d", head == rem, f"local {head[:7]} remote {rem[:7]}")


CHECKS = {"D1": d1, "D2": d2, "P1": p1, "P2": p2, "P3": p3, "P4": p4, "P5": p5, "P6": p6}

if __name__ == "__main__":
    want = [a.upper() for a in sys.argv[1:]]
    for key, fn in CHECKS.items():
        if want and not any(w.startswith(key) for w in want):
            continue
        try:
            fn()
        except Exception as exc:  # report, do not stop
            rec(key, False, f"check raised {type(exc).__name__}: {exc}")
    for cid, ok, ev in RESULTS:
        if want and not any(w == cid.upper() or cid.upper().startswith(w) for w in want):
            continue
        print(f"{cid} {'PASS' if ok else 'FAIL'} {ev[:230]}")
