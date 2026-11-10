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
    assert len(rows) == 8, f"Expected 8 rows, got {len(rows)}"
    assert rows[0] == ident["university"]
    assert rows[1] == ident["programme"]
    assert rows[2].startswith(ident["module"])
    assert rows[3] == ident["title"]
    # Row 4 is Student Name: label and value (concatenated, since label is now text not image)
    assert "Student Name:" in rows[4] and ident["student_name"] in rows[4]
    assert rows[5] == ident["student_number"] == "24154844"
    assert rows[6] == ident["tutor_name"]
    assert not rows[6].startswith(("Dr", "Prof"))


def test_names_only_where_expected(rows):
    ident = bd.load_identity()
    assert [i for i, r in enumerate(rows) if ident["student_name"] in r] == [4]
    assert [i for i, r in enumerate(rows) if ident["tutor_name"] in r] == [6]
    assert [i for i, r in enumerate(rows) if ident["student_number"] in r] == [5]


def test_apply_identity_idempotent(tmp_path):
    """Verify that calling apply_identity twice does not add duplicate rows."""
    if not bd.TEMPLATE.exists():
        pytest.skip("template docx missing")
    out = tmp_path / "title.docx"
    b = bd.Builder(bd.TEMPLATE, bd.REFS_JSON)
    b.strip_body_after_title_page()
    ident = bd.load_identity()
    b.apply_identity(ident)
    b.apply_identity(ident)  # Call twice
    b.doc.save(str(out))
    rows = bd.title_page_values(out)
    assert len(rows) == 8, f"Expected 8 rows after two apply_identity calls, got {len(rows)}"
    assert ident["student_name"] in rows[4]
