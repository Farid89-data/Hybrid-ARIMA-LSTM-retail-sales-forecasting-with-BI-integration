"""Unit tests for Harvard reference and in-text formatting (Arden guide)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docbuild"))
import citations as c  # noqa: E402


def mk(key, **d):
    d.setdefault("type", "article-journal")
    d.setdefault("author", [{"family": "Smith", "given": "John A."}])
    d.setdefault("issued", {"date-parts": [[2024]]})
    d.setdefault("title", "A title")
    return c.Entry(key, d)


def text(e):
    return "".join(t for t, _ in c.reference_runs(e))


def test_journal_issue_pages():
    e = mk("a", **{"container-title": "Journal of X", "volume": "13", "issue": "2", "page": "17–29",
                   "DOI": "10.1/x"})
    t = text(e)
    assert t == "Smith, J.A., (2024). A title. Journal of X [online], 13 (2), pp. 17-29. "
    assert "Available from" not in t and "Accessed" not in t
    assert c.reference_runs(e)[2][1] == {"italic": True}


def test_journal_article_number():
    e = mk("a", **{"container-title": "Front. Y", "volume": "15", "number": "1394045"})
    assert text(e).endswith("Front. Y [online], 15, article 1394045. ")


def test_html_unescape_and_plos():
    e = mk("a", **{"container-title": "Int. J. Logistics &amp; Management"})
    assert "Logistics & Management" in text(e)
    for n in ("PLOS One", "PLOS ONE"):
        assert "PLOS ONE [online]" in text(mk("b", **{"container-title": n}))


def test_chapter_two_editors():
    e = mk("a", type="chapter", **{"container-title": "Big Book", "publisher": "CRC Press",
           "page": "207-212", "DOI": "10.1/y",
           "editor": [{"family": "Jordan", "given": "Patrick W."}, {"family": "Thomas", "given": "B."}]})
    assert text(e) == ("Smith, J.A., (2024). A title. In: Jordan, P.W. and Thomas, B., eds. "
                       "Big Book [online]. CRC Press, pp. 207-212.")


def test_chapter_one_editor():
    e = mk("a", type="chapter", editor=[{"family": "Jordan", "given": "P."}], **{"container-title": "B"})
    assert "In: Jordan, P., ed. B" in text(e)


def test_webpage():
    e = mk("a", type="webpage", author=[{"literal": "Kaggle"}], publisher="Kaggle", URL="https://k.io/d")
    assert text(e) == ("Kaggle, (2024). A title [online]. Kaggle. "
                       "Available from: https://k.io/d [Accessed 9 November 2026].")


def test_book_edition():
    e = mk("a", type="book", edition="11", publisher="Pearson", **{"publisher-place": "London"})
    assert "11th edition. London: Pearson." in text(e)


def test_in_text_names():
    assert mk("a").in_text_names() == "Smith"
    two = mk("b", author=[{"family": "Smith"}, {"family": "Jones"}])
    assert two.in_text_names() == "Smith and Jones"
    three = mk("c", author=[{"family": "Smith"}, {"family": "Jones"}, {"family": "Lee"}])
    assert three.in_text_names() == "Smith et al."


def test_all_authors_in_reference_list():
    e = mk("a", author=[{"family": "A", "given": "X"}, {"family": "B", "given": "Y"},
                        {"family": "C", "given": "Z"}, {"family": "D", "given": "W"}])
    assert c.author_list(e) == "A, X., B, Y., C, Z. and D, W.,"


def test_order_keys_chronological():
    lib = {
        "z": mk("z", issued={"date-parts": [[2020]]}, author=[{"family": "Zed"}]),
        "a": mk("a", issued={"date-parts": [[2022]]}, author=[{"family": "Abe"}]),
        "b": mk("b", issued={"date-parts": [[2020]]}, author=[{"family": "Bee"}]),
    }
    out = c.order_keys([("a", "p. 3"), ("z", ""), ("b", "")], lib)
    assert out == [("b", ""), ("z", ""), ("a", "p. 3")]
