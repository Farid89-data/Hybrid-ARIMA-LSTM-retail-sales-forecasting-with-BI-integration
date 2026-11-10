"""D11: the built title page must show the identity from docbuild/identity.json."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docbuild"))
import build_docx as bd  # noqa: E402

KEYS = {"student_name", "student_number", "university", "programme", "programme_short",
        "module", "tutor_name", "title"}


def test_identity_config_keys():
    ident = bd.load_identity()
    assert set(ident) == KEYS
    assert all(isinstance(v, str) and v.strip() for v in ident.values())


@pytest.fixture(scope="module")
def rows(tmp_path_factory):
    if not bd.TEMPLATE.exists():
        pytest.skip("template docx missing")
    out = tmp_path_factory.mktemp("tp") / "title.docx"
    b = bd.Builder(bd.TEMPLATE, bd.REFS_JSON)
    b.strip_body_after_title_page()
    b.apply_identity(bd.load_identity())
    b.doc.save(str(out))
    return bd.title_page_values(out)


def test_title_page_matches_identity(rows):
    ident = bd.load_identity()
    assert rows[0] == ident["university"]
    assert rows[1] == ident["programme"]
    assert rows[2].startswith(ident["module"])
    assert rows[3] == ident["title"]
    assert rows[4] == ident["student_number"] == "24154844"
    assert rows[5] == ident["tutor_name"]
    assert not rows[5].startswith(("Dr", "Prof"))


def test_names_only_where_expected(rows):
    ident = bd.load_identity()
    assert not any(ident["student_name"] in r for r in rows)
    assert [i for i, r in enumerate(rows) if ident["tutor_name"] in r] == [5]
    assert [i for i, r in enumerate(rows) if ident["student_number"] in r] == [4]
