from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import pytest
from conftest import ROOT

from r9lab_vocabulary import checks, ords

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def products():
    return ords.product_ids(ROOT / "vocabulary")


def test_committed_ords_proposal_has_all_dispositions(products: set[str]):
    review, errors = ords.read_review(ROOT / ords.TABLE, products, ords.category_codes())
    assert errors == []
    assert len({row.category for row in review}) == 40


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([("41", "", "no_match", "Outside the codelist.")], "unknown ORDS code '41'"),
        ([("1", "p9999", "broad", "Unknown product.")], "product 'p9999' is not a live leaf type"),
        ([("1", "p0001", "broad", "Navigation family.")], "product 'p0001' is not a live leaf type"),
        ([("1", "", "close", "Missing product.")], "product '' is not a live leaf type"),
        ([("1", "p0007", "no_match", "Unexpected product.")], "no_match requires an empty product ID"),
        ([("1", "p0007", "related", "Unsupported predicate.")], "unknown relation 'related'"),
        ([("1", "", "no_match", "")], "needs a review note"),
        ([("1", "", "no_match", "First."), ("1", "", "no_match", "Duplicate.")], "duplicate disposition"),
        (
            [("1", "p0007", "exact", "First."), ("1", "p0007", "close", "Duplicate.")],
            "duplicate disposition",
        ),
        (
            [("1", "p0007", "close", "Candidate."), ("1", "", "no_match", "No candidate.")],
            "has both candidates and no_match",
        ),
        ([], "missing dispositions for ORDS codes 1"),
    ],
)
def test_ords_rejects_invalid_disposition(
    tmp_path: Path, products: set[str], rows: list[tuple[str, ...]], expected: str
):
    path = tmp_path / "test.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(ords.COLUMNS)
        writer.writerows(rows)
    _, errors = ords.read_review(path, products, {"1"})
    assert any(expected in error for error in errors)


def test_a_product_has_at_most_one_ords_rollup(tmp_path: Path, products: set[str]):
    table = tmp_path / "test.csv"
    table.write_text(
        ",".join(ords.COLUMNS) + "\n1,p0007,broad,First category.\n2,p0007,exact,Second category.\n",
        encoding="utf-8",
    )
    _, errors = ords.read_review(table, products, {"1", "2"})
    assert any("p0007 would roll up to ORDS codes 1 and 2" in error for error in errors)


def test_ords_refuses_a_changed_source_pin(tmp_path: Path):
    path = tmp_path / "codelist.csv"
    path.write_text("product_category_id,product_category\n1,Test fixture\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        ords.category_codes(path)


def test_ords_draft_sssom_preserves_the_proposed_links(tmp_path: Path, products: set[str]):
    review, errors = ords.read_review(ROOT / ords.TABLE, products, ords.category_codes())
    assert errors == []
    path = tmp_path / "draft.sssom.tsv"
    path.write_text(ords.draft_sssom(review), encoding="utf-8")

    metadata, rows = checks.read_sssom(path)
    assert "Draft" in metadata["mapping_set_title"]
    assert metadata["curie_map"]["ords-source"] == ords.SOURCE_BASE
    expected = [(row.product, row.relation, row.category, row.note) for row in review if row.product]
    actual = []
    for row in rows:
        assert row["object_id"] == ""
        assert row["object_type"] == "rdfs literal"
        assert row["object_source"] == f"ords-source:{ords.SOURCE_CSV}"
        assert row["object_source_version"] == "0.3"
        actual.append(
            (
                row["subject_id"].removeprefix("products:"),
                row["predicate_id"].removeprefix("skos:").removesuffix("Match"),
                row["object_label"],
                row["comment"],
            )
        )
    assert actual == expected


def test_ords_command_rejects_unknown_code_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    vocabulary = tmp_path / "vocabulary"
    vocabulary.mkdir()
    products = (ROOT / "vocabulary" / "products.yaml").read_text(encoding="utf-8")
    (vocabulary / "products.yaml").write_text(products, encoding="utf-8")
    table = tmp_path / ords.TABLE
    table.parent.mkdir()
    draft = (ROOT / ords.TABLE).read_text(encoding="utf-8")
    table.write_text(draft.replace("\n1,,no_match", "\n41,,no_match", 1), encoding="utf-8")

    assert ords.main(["--sssom"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "unknown ORDS code '41'" in output.err
