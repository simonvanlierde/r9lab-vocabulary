"""The review page: blind cards, timed verdicts appended to the log, and refused forged requests."""

from __future__ import annotations

import re
import threading
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from conftest import tsv
from fastapi import HTTPException
from fastapi.testclient import TestClient

from r9lab_vocabulary import curate, review
from r9lab_vocabulary.review import Session, create_app
from r9lab_vocabulary.review.__main__ import main

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

RATER, OTHER = "orcid:0000-0002-1825-0097", "orcid:0000-0001-5109-3700"
VOCABULARY = """scheme: {slug: materials, title: Materials, id_letter: m}
concepts:
  m0001: {label: steel, definition: An alloy of iron and carbon., note: Not cast iron.}
  m0002: {label: copper}
"""
PROPOSALS = [
    ("stainless", "skos:broadMatch", "materials:m0001", "steel", "a guess"),
    ("cu", "skos:exactMatch", "materials:m0002", "copper", ""),
]
TOOL = "secret-matcher-v1"  # what proposed each mapping; a card must never show it


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
    return dict(re.findall(r'name="(card|token)" value="([^"]+)"', html))


def verdict_rows(root: Path, rows: list[tuple[str, tuple[str, ...]]]) -> None:
    """Write a log holding an "agree" from each (rater, proposal) pair."""
    (root / curate.REVIEWS).write_text(tsv(curate.REVIEW_COLUMNS, [
        {"subject_id": f"r9lab-tag:{tag}", "predicate_id": p, "object_id": o, "reviewer_id": rater,
         "reviewer_agreement": "1", "review_date": "2026-11-26", "mapping_justification": "semapv:AgentBasedMatching"}
        for rater, (tag, p, o, *_) in rows
    ]))  # fmt: skip


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
    assert "is a kind of" in shown  # the relation in plain words
    assert "skos:" not in shown


def test_a_proposal_of_no_concept_says_so(tmp_path: Path):
    root = make_root(tmp_path)
    predictions = root / curate.PREDICTIONS
    predictions.write_text(predictions.read_text().replace("materials:m0002\tcopper", "sssom:NoTermFound\t"))
    verdict_rows(root, [(RATER, PROPOSALS[0])])
    assert "has no concept in the vocabulary" in client(root).get("/").text


def test_a_tag_and_a_definition_are_shown_as_text_not_markup(tmp_path: Path):
    root = make_root(tmp_path)
    predictions = root / curate.PREDICTIONS
    predictions.write_text(predictions.read_text().replace("\tstainless\t", "\t<i>stainless</i>\t"))
    vocabulary = root / "vocabulary" / "materials.yaml"
    vocabulary.write_text(vocabulary.read_text().replace("An alloy", "<b>An</b> alloy"))
    verdict_rows(root, [(RATER, PROPOSALS[1])])  # leaves the steel card
    page = client(root).get("/").text
    assert "&lt;i&gt;stainless&lt;/i&gt;" in page
    assert "&lt;b&gt;An&lt;/b&gt;" in page
    assert "<i>stainless" not in page
    assert "<b>" not in page


def test_each_rater_has_their_own_order_and_keeps_it_after_a_restart(tmp_path: Path):
    root = make_root(tmp_path, extra=18)
    assert Session(root, RATER).queue() == Session(root, RATER).queue()
    assert Session(root, RATER).queue() != Session(root, OTHER).queue()
    assert len(set(Session(root, RATER).queue())) == 20


def test_a_new_proposal_keeps_the_order_of_the_others(tmp_path: Path):
    (tmp_path / "before").mkdir()
    (tmp_path / "after").mkdir()
    before = Session(make_root(tmp_path / "before", extra=18), RATER).queue()
    after = Session(make_root(tmp_path / "after", extra=19), RATER).queue()
    assert [k for k in after if k in before] == before


def test_the_card_does_not_give_away_its_place_in_the_proposals(tmp_path: Path):
    card = form(client(make_root(tmp_path)).get("/").text)["card"]
    assert card not in {"0", "1"}


def test_a_card_another_rater_judged_still_comes_up(tmp_path: Path):
    root = make_root(tmp_path)
    verdict_rows(root, [(OTHER, PROPOSALS[0]), (OTHER, PROPOSALS[1]), (RATER, PROPOSALS[1])])
    [left] = Session(root, RATER).queue()
    assert left == (f"r9lab-tag:{PROPOSALS[0][0]}", *PROPOSALS[0][1:3])


@pytest.mark.parametrize(("verdict", "agreement"), [("agree", "1"), ("unsure", "0"), ("disagree", "-1")])
def test_a_verdict_is_appended_with_the_rater_agreement_date_and_seconds(tmp_path: Path, verdict: str, agreement: str):
    root = make_root(tmp_path)
    c = client(root)
    first = form(c.get("/").text)
    response = c.post("/verdict", data=first | {"verdict": verdict}, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert form(response.text)["card"] != first["card"]  # the next card came back
    [row] = curate.read(root / curate.REVIEWS)[2]
    assert (row["reviewer_id"], row["reviewer_agreement"]) == (RATER, agreement)
    assert curate.key(row) in {(f"r9lab-tag:{tag}", p, o) for tag, p, o, *_ in PROPOSALS}
    assert row["mapping_justification"] == "semapv:AgentBasedMatching"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["review_date"])
    assert re.fullmatch(r"\d+\.\d", row["review_seconds"])
    assert curate.check_reviews([row]) == []


def test_a_log_without_a_final_newline_takes_the_next_verdict_on_its_own_line(tmp_path: Path):
    root = make_root(tmp_path)
    verdict_rows(root, [(OTHER, PROPOSALS[0])])
    log = root / curate.REVIEWS
    log.write_text(log.read_text().rstrip("\n"))  # a row added by hand, as the protocol allows
    c = client(root)
    c.post("/verdict", data=form(c.get("/").text) | {"verdict": "agree"})
    assert len(curate.read(log)[2]) == 2
    assert curate.read_log(root)[3] == []


def test_a_failed_write_keeps_the_time_for_the_retry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = [10.0]
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: now[0]))
    root = make_root(tmp_path)
    c = client(root)
    card = form(c.get("/").text) | {"verdict": "agree"}
    log = (root / curate.REVIEWS).read_text()
    (root / curate.REVIEWS).write_text("")
    failed = c.post("/verdict", data=card, headers={"HX-Request": "true"})
    assert failed.status_code == 500
    assert 'role="alert"' in failed.text
    assert "is empty" in failed.text
    (root / curate.REVIEWS).write_text(log)
    now[0] = 14.0
    c.post("/verdict", data=card, headers={"HX-Request": "true"})
    [row] = curate.read(root / curate.REVIEWS)[2]
    assert row["review_seconds"] == "4.0"


def test_the_time_runs_from_the_first_showing_not_a_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clock = iter([10.0, 15.0, 17.0])  # shown, reloaded, judged
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    session = Session(make_root(tmp_path), RATER)
    card = session.card()
    assert card
    session.card()
    session.record(str(card["card"]), "agree")
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
            session.record(str(card["card"]), verdict)
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
    withdrawn = ("gone", *PROPOSALS[0][1:])
    verdict_rows(root, [(RATER, PROPOSALS[0]), (OTHER, PROPOSALS[0]), (OTHER, PROPOSALS[1]), (RATER, withdrawn)])
    assert Session(root, RATER).progress() == {OTHER: 2, RATER: 1, "of": 2}


def test_the_progress_stream_sends_the_counts_as_one_event(tmp_path: Path):
    root = make_root(tmp_path)
    verdict_rows(root, [(f"<b>{OTHER}</b>", PROPOSALS[0])])
    with client(root).stream("GET", "/progress") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        first = next(response.iter_lines())
    assert first.startswith('data: <p id="progress">')
    assert f"&lt;b&gt;{OTHER}&lt;/b&gt;: 1 of 2" in first


def test_a_judged_card_does_not_come_back_and_the_queue_ends(tmp_path: Path):
    c = client(make_root(tmp_path))
    for _ in PROPOSALS:
        c.post("/verdict", data=form(c.get("/").text) | {"verdict": "agree"})
    assert "You have judged every card (2)" in c.get("/").text
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
    assert '<p id="card" role="alert">This card was already judged.' in stale.text  # takes the card's place


def test_every_response_carries_the_security_headers(tmp_path: Path):
    c = client(make_root(tmp_path))
    refused = c.post("/verdict", data=form(c.get("/").text) | {"verdict": "agree", "token": "guess"})
    assert refused.status_code == 403
    for response in (c.get("/"), refused):
        for name, value in review.SECURITY_HEADERS:
            assert response.headers[name.decode()] == value.decode()


def test_every_file_the_page_loads_is_served(tmp_path: Path):
    c = client(make_root(tmp_path))
    paths = re.findall(r'(?:src|href)="(/static/[^"]+)"', c.get("/").text)
    assert len(paths) == 4
    for path in paths:
        assert c.get(path).status_code == 200


def test_an_empty_log_is_refused_rather_than_given_a_headerless_row(tmp_path: Path):
    root = make_root(tmp_path)
    (root / curate.REVIEWS).write_text("")
    with pytest.raises(ValueError, match="is empty"):
        curate.append_review(root, {})


def test_without_javascript_a_verdict_redirects_back_to_the_page(tmp_path: Path):
    c = client(make_root(tmp_path), follow_redirects=False)
    response = c.post("/verdict", data=form(c.get("/").text) | {"verdict": "unsure"})
    assert (response.status_code, response.headers["location"]) == (303, "/")


@pytest.mark.parametrize("reviewer", [None, "simon", "", f"{RATER}x", f"x{RATER}"])
def test_the_page_will_not_start_without_an_orcid(
    reviewer: str | None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    if reviewer is None:
        monkeypatch.delenv("R9LAB_REVIEWER", raising=False)
    else:
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
    assert main([]) == 0
    assert calls == [{"host": "127.0.0.1", "port": port, "timeout_graceful_shutdown": 2} for port in (9999, 8740)]


def test_undo_shows_the_last_card_again_and_its_new_verdict_counts(tmp_path: Path):
    root = make_root(tmp_path)
    c = client(root)
    hx = {"HX-Request": "true"}
    first = form(c.get("/").text)
    after = c.post("/verdict", data=first | {"verdict": "agree"}, headers=hx).text
    assert "Recorded:" in after
    assert 'data-key="z"' in after
    again = c.post("/undo", data={"token": first["token"]}, headers=hx)
    assert form(again.text)["card"] == first["card"]
    assert 'data-key="z"' not in again.text  # one step only
    c.post("/verdict", data=first | {"verdict": "disagree"}, headers=hx)
    rows = curate.read(root / curate.REVIEWS)[2]
    assert [r["reviewer_agreement"] for r in rows] == ["1", "-1"]  # appended, the latest counts
    assert c.post("/undo", data={"token": first["token"]}).status_code == 200  # the disagree, undone in turn
    assert c.post("/undo", data={"token": first["token"]}, headers=hx).status_code == 409


def test_undo_needs_the_form_token(tmp_path: Path):
    c = client(make_root(tmp_path))
    first = form(c.get("/").text)
    c.post("/verdict", data=first | {"verdict": "agree"})
    assert c.post("/undo", data={"token": "guess"}).status_code == 403
    assert c.post("/undo", data=first, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_time_hidden_or_paused_is_left_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clock = iter([10.0, 17.0, 20.0, 21.0])  # card one shown, judged; card two shown, judged
    monkeypatch.setattr(review, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    session = Session(make_root(tmp_path), RATER)
    for away in (5.0, 9.0):  # 9 s away from a 1 s card is a page that lies: no negative time
        card = session.card()
        assert card
        session.record(str(card["card"]), "agree", away)
    assert [r["review_seconds"] for r in curate.read(tmp_path / curate.REVIEWS)[2]] == ["2.0", "0.0"]


@pytest.mark.parametrize("away", ["-1", "nan", "inf", "soon"])
def test_a_bad_away_time_is_refused(tmp_path: Path, away: str):
    c = client(make_root(tmp_path))
    assert c.post("/verdict", data=form(c.get("/").text) | {"verdict": "agree", "away": away}).status_code == 422


@pytest.mark.parametrize("path", ["/", "/progress"])
def test_another_site_cannot_load_the_page_or_its_stream(tmp_path: Path, path: str, monkeypatch: pytest.MonkeyPatch):
    async def one_event(*_: object) -> AsyncIterator[str]:
        yield "data: x\n\n"  # the real stream never ends, so a missing check would hang the test

    monkeypatch.setattr(review, "progress_stream", one_event)
    root = make_root(tmp_path)
    c = client(root)
    assert c.get(path).status_code == 200
    assert c.get(path, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert Session(root, RATER).shown_at == {}


def test_the_progress_event_names_you_and_the_others(tmp_path: Path):
    root = make_root(tmp_path)
    verdict_rows(root, [(RATER, PROPOSALS[0]), (OTHER, PROPOSALS[0])])
    event = review.progress_event(Session(root, RATER))
    assert event.startswith('data: <p id="progress">')
    assert event.endswith("\n\n")
    assert f"{OTHER}: 1 of 2" in event
    assert "You: 1 of 2" in event


@pytest.mark.parametrize("log", [None, ""])
def test_the_page_will_not_start_without_a_review_log(
    log: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    root = make_root(tmp_path)
    if log is None:
        (root / curate.REVIEWS).unlink()
    else:
        (root / curate.REVIEWS).write_text(log)
    monkeypatch.setenv("R9LAB_REVIEWER", RATER)
    monkeypatch.chdir(root)
    monkeypatch.setattr("uvicorn.run", lambda *_, **__: pytest.fail("the server started"))
    assert main([]) == 2
    assert "missing or empty" in capsys.readouterr().err
