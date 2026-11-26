"""The review page: blind cards, timed verdicts appended to the log, and refused forged requests."""

from __future__ import annotations

import re
import threading
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from r9lab_vocabulary import curate, review
from r9lab_vocabulary.review import Session, create_app
from r9lab_vocabulary.review.__main__ import main

if TYPE_CHECKING:
    from pathlib import Path

RATER, OTHER = "orcid:0000-0002-1825-0097", "orcid:0000-0001-5109-3700"
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
TOOL = "secret-matcher-v1"  # what proposed each mapping; a card must never show it


def tsv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    return HEAD + "\n".join(["\t".join(columns), *("\t".join(r.get(c, "") for c in columns) for r in rows)]) + "\n"


def make_root(tmp_path: Path, extra: int = 0) -> Path:
    """A vocabulary and a log with `PROPOSALS`, plus `extra` more proposals for copper."""
    (tmp_path / "vocabulary").mkdir()
    (tmp_path / "vocabulary" / "materials.yaml").write_text(VOCABULARY)
    (tmp_path / curate.PREDICTIONS).parent.mkdir(parents=True)
    proposals = PROPOSALS + [(f"cu{n}", "skos:exactMatch", "materials:m0002", "copper", "") for n in range(extra)]
    rows = [
        {"subject_id": f"r9lab-tag:{tag}", "subject_label": tag, "predicate_id": p, "object_id": o,
         "object_label": label, "mapping_tool": TOOL, "comment": comment,
         "mapping_justification": "semapv:AgentBasedMatching"}
        for tag, p, o, label, comment in proposals
    ]  # fmt: skip
    (tmp_path / curate.PREDICTIONS).write_text(tsv(curate.PREDICTION_COLUMNS, rows))
    (tmp_path / curate.REVIEWS).write_text(tsv(curate.REVIEW_COLUMNS, []))
    return tmp_path


def client(root: Path, rater: str = RATER, *, follow_redirects: bool = True) -> TestClient:
    app = create_app(root, rater)
    return TestClient(app, base_url="http://127.0.0.1", follow_redirects=follow_redirects)


def form(html: str) -> dict[str, str]:
    return dict(re.findall(r'name="(i|token)" value="([^"]+)"', html))


def test_no_card_shows_what_proposed_it(tmp_path: Path):
    c = client(make_root(tmp_path))
    cards = [c.get("/").text]
    for _ in PROPOSALS:
        cards.append(c.post("/verdict", data=form(cards[-1]) | {"verdict": "agree"}, headers={"HX-Request": "1"}).text)
    shown = "".join(cards)
    for hidden in ("AgentBasedMatching", TOOL, "a guess"):  # justification, tool, the proposer's comment
        assert hidden not in shown
    assert "An alloy of iron and carbon." in shown
    assert "Not cast iron." in shown


def test_a_tag_is_shown_as_text_not_markup(tmp_path: Path):
    root = make_root(tmp_path)
    predictions = root / curate.PREDICTIONS
    predictions.write_text(predictions.read_text().replace("\tstainless\t", "\t<i>stainless</i>\t"))
    page = "".join(client(root, r).get("/").text for r in (RATER, OTHER))  # one of them gets the tag first
    assert "&lt;i&gt;stainless&lt;/i&gt;" in page
    assert "<i>stainless" not in page


def test_each_rater_has_their_own_order_and_keeps_it_after_a_restart(tmp_path: Path):
    root = make_root(tmp_path, extra=18)
    assert Session(root, RATER).order == Session(root, RATER).order
    assert Session(root, RATER).order != Session(root, OTHER).order
    assert sorted(Session(root, RATER).order) == list(range(20))


def test_a_verdict_is_appended_with_the_rater_agreement_date_and_seconds(tmp_path: Path):
    root = make_root(tmp_path)
    c = client(root)
    first = form(c.get("/").text)
    response = c.post("/verdict", data=first | {"verdict": "disagree"}, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert form(response.text)["i"] != first["i"]  # the next card came back
    [row] = curate.read(root / curate.REVIEWS)[2]
    assert (row["reviewer_id"], row["reviewer_agreement"]) == (RATER, "-1")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["review_date"])
    assert curate.check_reviews([row]) == []


def test_the_time_runs_from_the_first_showing_not_a_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clock = iter([10.0, 15.0, 17.0])  # shown, reloaded, judged
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    session = Session(make_root(tmp_path), RATER)
    card = session.card()
    assert card
    session.card()
    session.record(int(str(card["i"])), "agree")
    [row] = curate.read(tmp_path / curate.REVIEWS)[2]
    assert row["review_seconds"] == "7.0"


def test_two_verdicts_on_one_card_at_once_record_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    session = Session(make_root(tmp_path), RATER)
    card = session.card()
    assert card
    append = curate.append_review

    def slow_append(root: Path, row: dict[str, str]) -> None:
        time.sleep(0.2)  # widen the window between the queue check and the write
        append(root, row)

    monkeypatch.setattr(curate, "append_review", slow_append)
    outcomes: list[int] = []

    def judge(verdict: str) -> None:
        try:
            session.record(int(str(card["i"])), verdict)
            outcomes.append(200)
        except HTTPException as e:
            outcomes.append(e.status_code)

    threads = [threading.Thread(target=judge, args=(v,)) for v in ("agree", "disagree")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == [200, 409]
    assert len(curate.read(tmp_path / curate.REVIEWS)[2]) == 1


def test_progress_counts_each_rater_and_skips_withdrawn_proposals(tmp_path: Path):
    root = make_root(tmp_path)
    rows = [
        {"subject_id": f"r9lab-tag:{tag}", "predicate_id": p, "object_id": o, "reviewer_id": rater,
         "reviewer_agreement": "1", "review_date": "2026-11-26", "mapping_justification": "semapv:AgentBasedMatching"}
        for rater, (tag, p, o, *_) in [(RATER, PROPOSALS[0]), (OTHER, PROPOSALS[0]), (OTHER, PROPOSALS[1])]
    ]  # fmt: skip
    withdrawn = rows[0] | {"subject_id": "r9lab-tag:gone"}
    (root / curate.REVIEWS).write_text(tsv(curate.REVIEW_COLUMNS, [*rows, withdrawn]))
    assert Session(root, RATER).progress() == {OTHER: 2, RATER: 1, "of": 2}


def test_a_judged_card_does_not_come_back_and_the_queue_ends(tmp_path: Path):
    c = client(make_root(tmp_path))
    for _ in PROPOSALS:
        c.post("/verdict", data=form(c.get("/").text) | {"verdict": "agree"})
    assert "Nothing left to review" in c.get("/").text
    assert client(tmp_path).get("/").text.count('name="verdict"') == 0  # after a restart too


def test_forged_and_stale_verdicts_are_refused(tmp_path: Path):
    root = make_root(tmp_path)
    c = client(root)
    good = form(c.get("/").text) | {"verdict": "agree"}
    for site in ("cross-site", "same-site"):
        assert c.post("/verdict", data=good, headers={"Sec-Fetch-Site": site}).status_code == 403
    assert c.post("/verdict", data=good | {"token": "guess"}).status_code == 403
    assert c.post("/verdict", data=good | {"verdict": "maybe"}).status_code == 422
    assert c.post("/verdict", data=good, headers={"Host": "evil.example"}).status_code == 400  # DNS rebinding
    assert curate.read(root / curate.REVIEWS)[2] == []
    hx = {"HX-Request": "true", "Sec-Fetch-Site": "none"}
    assert c.post("/verdict", data=good, headers=hx).status_code == 200
    stale = c.post("/verdict", data=good, headers=hx)
    assert stale.status_code == 409
    assert '<p id="card" role="alert">this card was already judged' in stale.text  # takes the card's place


def test_the_page_cannot_be_framed(tmp_path: Path):
    headers = client(make_root(tmp_path)).get("/").headers
    assert headers["x-frame-options"] == "DENY"
    assert headers["content-security-policy"] == "frame-ancestors 'none'"


def test_an_empty_log_is_refused_rather_than_given_a_headerless_row(tmp_path: Path):
    root = make_root(tmp_path)
    (root / curate.REVIEWS).write_text("")
    with pytest.raises(ValueError, match="is empty"):
        curate.append_review(root, {})


def test_without_javascript_a_verdict_redirects_back_to_the_page(tmp_path: Path):
    c = client(make_root(tmp_path), follow_redirects=False)
    response = c.post("/verdict", data=form(c.get("/").text) | {"verdict": "unsure"})
    assert (response.status_code, response.headers["location"]) == (303, "/")


@pytest.mark.parametrize("reviewer", ["simon", "", f"{RATER}x", f"x{RATER}"])
def test_the_page_will_not_start_without_an_orcid(
    reviewer: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("R9LAB_REVIEWER", reviewer)
    monkeypatch.setattr("uvicorn.run", lambda *_, **__: pytest.fail("the server started"))
    assert main([]) == 2
    assert "R9LAB_REVIEWER" in capsys.readouterr().err


def test_the_page_serves_on_this_machine_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = []
    monkeypatch.setenv("R9LAB_REVIEWER", RATER)
    monkeypatch.chdir(make_root(tmp_path))
    monkeypatch.setattr("uvicorn.run", lambda _app, **kwargs: calls.append(kwargs))
    assert main(["--port", "9999"]) == 0
    assert calls == [{"host": "127.0.0.1", "port": 9999, "timeout_graceful_shutdown": 2}]
