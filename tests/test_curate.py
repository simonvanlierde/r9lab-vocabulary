"""The tag-mapping review log: its rules, and the published file built from it."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from r9lab_vocabulary import curate

if TYPE_CHECKING:
    import pytest

ROOT = Path(__file__).resolve().parent.parent
HEAD = "#curie_map:\n#  r9lab-tag: https://w3id.org/r9lab/vocabulary/tags/\n"
A, B, X = "orcid:0000-0002-1825-0097", "orcid:0000-0001-5109-3700", "orcid:0000-0002-1694-233X"


def tsv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    lines = ["\t".join(columns), *("\t".join(r.get(c, "") for c in columns) for r in rows)]
    return HEAD + "\n".join(lines) + "\n"


def proposal(tag: str, obj: str) -> dict[str, str]:
    return {"subject_id": f"r9lab-tag:{tag}", "subject_label": tag, "predicate_id": "skos:exactMatch",
            "object_id": obj, "object_label": obj, "mapping_justification": "semapv:AgentBasedMatching"}  # fmt: skip


def review(tag: str, obj: str, rater: str, agreement: str, **extra: str) -> dict[str, str]:
    p = proposal(tag, obj)
    return {k: p[k] for k in (*curate.KEY, "mapping_justification")} | {
        "reviewer_id": rater, "reviewer_agreement": agreement, "review_date": "2026-11-26", **extra,
    }  # fmt: skip


def write_log(root: Path, predictions: list[dict[str, str]], reviews: list[dict[str, str]]) -> None:
    (root / curate.PREDICTIONS).parent.mkdir(parents=True)
    (root / curate.PREDICTIONS).write_text(tsv(curate.PREDICTION_COLUMNS, predictions))
    (root / curate.REVIEWS).write_text(tsv(curate.REVIEW_COLUMNS, reviews))


def published_rows(text: str) -> list[tuple[str, str]]:
    rows = [line.split("\t") for line in text.splitlines() if not line.startswith("#")][1:]
    return [(r[0].removeprefix("r9lab-tag:"), r[5]) for r in rows]


def test_the_review_log_breaks_no_rule_and_the_published_file_is_current():
    assert curate.check(ROOT) == []


def test_build_publishes_what_no_rater_rejected_with_the_raters_who_agreed():
    tags = ("agreed", "rejected", "split", "outvoted", "unsure", "mixed", "untouched", "changed")
    predictions = [proposal(t, "m:1") for t in tags]
    reviews = [
        review("agreed", "m:1", B, "1"),
        review("agreed", "m:1", A, "1"),
        review("rejected", "m:1", A, "-1"),
        review("split", "m:1", A, "1"),
        review("split", "m:1", B, "-1"),
        review("outvoted", "m:1", A, "1"),
        review("outvoted", "m:1", B, "-1"),
        review("outvoted", "m:1", X, "1"),  # one rejection holds until its rater changes it
        review("unsure", "m:1", A, "0"),
        review("mixed", "m:1", A, "1"),
        review("mixed", "m:1", B, "0"),  # unsure is not a rejection
        review("changed", "m:1", A, "-1"),
        review("changed", "m:1", A, "1"),  # the rater's later row wins
    ]
    built = curate.build({"curie_map": {}}, predictions, reviews)
    assert published_rows(built) == [
        ("agreed", f"{B}|{A}"),  # sorted, so the order does not depend on who reviewed first
        ("split", ""),
        ("outvoted", ""),
        ("unsure", ""),
        ("mixed", A),
        ("untouched", ""),
        ("changed", A),
    ]


def test_check_catches_each_broken_rule(tmp_path: Path):
    bad = proposal("hand", "m:1") | {"mapping_justification": "semapv:ManualMappingCuration"}
    write_log(
        tmp_path,
        [proposal("twice", "m:1"), proposal("twice", "m:1"), proposal("twice", "m:2"), bad],
        [
            review("twice", "m:1", "simon", "yes", review_date="26 Nov", review_seconds="soon"),
            review("twice", "m:1", f"{A}x", "1", review_date="2026-13-45"),
            review("twice", "m:1", A, "1", review_date="2026-11-26x"),
        ],
    )
    assert curate.check(tmp_path) == [
        "predictions.sssom.tsv: 'twice' -> m:1 is proposed twice",
        "predictions.sssom.tsv: 'twice' -> m:2: the tag already has a proposal",
        "predictions.sssom.tsv: 'hand' -> m:1: 'semapv:ManualMappingCuration' is not a machine justification",
        "reviews.sssom.tsv row 1: reviewer_id 'simon' is not an ORCID CURIE",
        "reviews.sssom.tsv row 1: reviewer_agreement 'yes' is not 1, -1 or 0",
        "reviews.sssom.tsv row 1: review_date '26 Nov' is not YYYY-MM-DD",
        "reviews.sssom.tsv row 1: review_seconds 'soon' is not a number",
        f"reviews.sssom.tsv row 2: reviewer_id '{A}x' is not an ORCID CURIE",
        "reviews.sssom.tsv row 2: review_date '2026-13-45' is not YYYY-MM-DD",
        "reviews.sssom.tsv row 3: review_date '2026-11-26x' is not YYYY-MM-DD",
    ]


def test_check_accepts_every_valid_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reviews = [review("steel", "m:1", A, "1"), review("steel", "m:1", B, "-1"), review("steel", "m:1", X, "0")]
    write_log(tmp_path, [proposal("steel", "m:1")], reviews)
    monkeypatch.chdir(tmp_path)
    assert curate.main(["build"]) == 0
    assert curate.check(tmp_path) == []


def test_a_tag_every_rater_rejected_fails_check_until_it_gets_a_new_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write_log(tmp_path, [proposal("brass", "m:1")], [review("brass", "m:1", A, "-1")])
    monkeypatch.chdir(tmp_path)
    assert curate.main(["build"]) == 0
    assert published_rows((tmp_path / curate.PUBLISHED).read_text()) == []
    [error] = curate.check(tmp_path)
    assert error.startswith("predictions.sssom.tsv: 'brass' -> m:1: every rater rejected it")
    # Replacing the proposal fixes it; the old verdict stays in the log, with a warning.
    (tmp_path / curate.PREDICTIONS).write_text(tsv(curate.PREDICTION_COLUMNS, [proposal("brass", "m:2")]))
    assert curate.main(["build"]) == 0
    capsys.readouterr()
    assert curate.main(["check"]) == 0
    assert capsys.readouterr().err == (
        "warning: reviews.sssom.tsv row 1: r9lab-tag:brass skos:exactMatch m:1 is no longer proposed;"
        " its verdict is kept but unused\n"
    )


def test_build_refuses_a_broken_log_and_leaves_the_published_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    write_log(tmp_path, [proposal("steel", "m:1")], [review("steel", "m:1", A, "yes")])
    (tmp_path / curate.PUBLISHED).write_text("before\n")
    monkeypatch.chdir(tmp_path)
    assert curate.main(["build"]) == 1
    assert (tmp_path / curate.PUBLISHED).read_text() == "before\n"
    assert "error: reviews.sssom.tsv row 1: reviewer_agreement 'yes'" in capsys.readouterr().err


def test_check_fails_when_the_published_file_is_stale_and_build_fixes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    write_log(tmp_path, [proposal("steel", "m:1")], [review("steel", "m:1", A, "1", review_seconds="3.5")])
    monkeypatch.chdir(tmp_path)
    assert curate.check(tmp_path) == [f"{curate.PUBLISHED} is out of date: run `just curate`"]
    assert curate.main(["check"]) == 1
    assert curate.main(["build"]) == 0
    assert curate.main(["check"]) == 0
    assert published_rows((tmp_path / curate.PUBLISHED).read_text()) == [("steel", A)]
    with (tmp_path / curate.PUBLISHED).open("a") as f:
        f.write("r9lab-tag:copper\tcopper\n")  # a hand edit
    assert curate.main([]) == 1  # no command means check


def test_check_names_a_missing_column_and_a_missing_file(tmp_path: Path):
    write_log(tmp_path, [], [])
    (tmp_path / curate.REVIEWS).write_text(HEAD + "subject_id\n")
    assert curate.check(tmp_path)[0] == "reviews.sssom.tsv: no predicate_id column"
    (tmp_path / curate.PREDICTIONS).write_text(HEAD + "subject_id\n")
    assert curate.check(tmp_path)[0] == "predictions.sssom.tsv: no subject_label column"
    (tmp_path / curate.PREDICTIONS).unlink()
    assert curate.check(tmp_path) == [f"{tmp_path / curate.PREDICTIONS}: missing"]


def test_an_unknown_command_is_a_usage_error(capsys: pytest.CaptureFixture[str]):
    assert curate.main(["serve"]) == 2
    assert "unknown command 'serve'" in capsys.readouterr().err
