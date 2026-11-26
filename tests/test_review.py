"""The review page: blind cards, timed verdicts appended to the log, and refused forged requests."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from r9lab_vocabulary import curate
from r9lab_vocabulary.review import create_app
from r9lab_vocabulary.review.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

RATER = "orcid:0000-0002-1825-0097"
VOCABULARY = """scheme: {slug: materials, title: Materials, id_letter: m}
concepts:
  m0001: {label: steel, definition: An alloy of iron and carbon., note: Not cast iron.}
  m0002: {label: copper}
"""
HEAD = "#curie_map:\n#  r9lab-tag: https://w3id.org/r9lab/vocabulary/tags/\n"
PROPOSALS = [
    ("stainless", "skos:broadMatch", "materials:m0001", "steel", "a guess"),
    ("cu", "skos:exactMatch", "materials:m0002", "copper", ""),
]


def tsv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    return HEAD + "\n".join(["\t".join(columns), *("\t".join(r.get(c, "") for c in columns) for r in rows)]) + "\n"


def make_root(tmp_path: Path) -> Path:
    (tmp_path / "vocabulary").mkdir()
    (tmp_path / "vocabulary" / "materials.yaml").write_text(VOCABULARY)
    (tmp_path / curate.PREDICTIONS).parent.mkdir(parents=True)
    rows = [
        {"subject_id": f"r9lab-tag:{tag}", "subject_label": tag, "predicate_id": p, "object_id": o,
         "object_label": label, "comment": comment, "mapping_justification": "semapv:AgentBasedMatching"}
        for tag, p, o, label, comment in PROPOSALS
    ]  # fmt: skip
    (tmp_path / curate.PREDICTIONS).write_text(tsv(curate.PREDICTION_COLUMNS, rows))
    (tmp_path / curate.REVIEWS).write_text(tsv(curate.REVIEW_COLUMNS, []))
    return tmp_path


def form(html: str) -> dict[str, str]:
    return dict(re.findall(r'name="(i|token)" value="([^"]+)"', html))


def test_a_card_is_blind_to_what_proposed_it(tmp_path: Path):
    page = TestClient(create_app(make_root(tmp_path), RATER)).get("/").text
    assert "AgentBasedMatching" not in page
    assert "a guess" not in page  # the proposer's comment stays hidden
    assert "An alloy of iron and carbon." in page or "copper" in page


def test_a_tag_is_shown_as_text_not_markup(tmp_path: Path):
    root = make_root(tmp_path)
    predictions = root / curate.PREDICTIONS
    predictions.write_text(predictions.read_text().replace("\tstainless\t", "\t<i>stainless</i>\t"))
    raters = (RATER, "orcid:0000-0001-5109-3700")  # their orders differ, so one of them gets the tag first
    page = "".join(TestClient(create_app(root, r)).get("/").text for r in raters)
    assert "&lt;i&gt;stainless&lt;/i&gt;" in page
    assert "<i>stainless" not in page


def test_a_verdict_is_appended_with_the_rater_agreement_date_and_seconds(tmp_path: Path):
    root = make_root(tmp_path)
    client = TestClient(create_app(root, RATER))
    first = form(client.get("/").text)
    response = client.post("/verdict", data=first | {"verdict": "disagree"}, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert form(response.text)["i"] != first["i"]  # the next card came back
    [row] = curate.read(root / curate.REVIEWS)[2]
    assert (row["reviewer_id"], row["reviewer_agreement"]) == (RATER, "-1")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["review_date"])
    assert float(row["review_seconds"]) >= 0
    assert curate.check_reviews([row]) == []


def test_a_judged_card_does_not_come_back_and_the_queue_ends(tmp_path: Path):
    client = TestClient(create_app(make_root(tmp_path), RATER))
    for _ in PROPOSALS:
        client.post("/verdict", data=form(client.get("/").text) | {"verdict": "agree"})
    assert "Nothing left to review" in client.get("/").text
    assert TestClient(create_app(tmp_path, RATER)).get("/").text.count('name="verdict"') == 0  # after a restart too


def test_forged_and_stale_verdicts_are_refused(tmp_path: Path):
    root = make_root(tmp_path)
    client = TestClient(create_app(root, RATER))
    good = form(client.get("/").text) | {"verdict": "agree"}
    assert client.post("/verdict", data=good, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/verdict", data=good | {"token": "guess"}).status_code == 403
    assert client.post("/verdict", data=good | {"verdict": "maybe"}).status_code == 422
    assert curate.read(root / curate.REVIEWS)[2] == []
    assert client.post("/verdict", data=good, headers={"HX-Request": "true"}).status_code == 200
    assert client.post("/verdict", data=good, headers={"HX-Request": "true"}).status_code == 409


def test_without_javascript_a_verdict_redirects_back_to_the_page(tmp_path: Path):
    client = TestClient(create_app(make_root(tmp_path), RATER), follow_redirects=False)
    response = client.post("/verdict", data=form(client.get("/").text) | {"verdict": "unsure"})
    assert (response.status_code, response.headers["location"]) == (303, "/")


def test_the_page_will_not_start_without_an_orcid(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setenv("R9LAB_REVIEWER", "simon")
    assert main([]) == 2
    assert "R9LAB_REVIEWER" in capsys.readouterr().err
