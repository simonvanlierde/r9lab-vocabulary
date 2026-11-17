"""This project's readers and commands, on small fixtures: no network."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from r9lab_vocabulary import pipeline

if TYPE_CHECKING:
    import pytest

CPC = '"CPC21code","CPC21title"\r\n"4112","Crude steel"\r\n"4131","Silver, caf\xe9"\r\n'.encode("latin-1")
PMDCO = b"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<https://w3id.org/pmd/co/PMD_0000852> rdfs:label "metal"@en .
<https://w3id.org/pmd/co/PMD_0000852> rdfs:label "Metall"@de .
<https://example.org/other> rdfs:label "not pmdco"@en .
"""


def test_the_cpc_reader_decodes_latin_1():
    columns, rows = pipeline.parse({"id": "cpc21"}, CPC)
    assert columns == ["code", "title"]
    assert rows == [{"code": "4112", "title": "Crude steel"}, {"code": "4131", "title": "Silver, café"}]


def test_the_pmdco_reader_keeps_english_labels_of_pmdco_terms():
    _, rows = pipeline.parse({"id": "pmdco"}, PMDCO)
    assert rows == [{"id": "PMD_0000852", "label": "metal"}]


def test_rdf_writes_the_vocabulary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    everything = type("All", (set,), {"__contains__": lambda *_: True})()
    monkeypatch.setattr(pipeline, "known_codes", lambda: {"cpc": everything, "pmdco": everything})
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "r9lab-vocabulary.ttl").stat().st_size > 0
    assert (tmp_path / "bafu-candidates.csv").read_text(encoding="utf-8").startswith("concept,label,pattern\n")


def test_rdf_fails_on_a_code_the_sources_lack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    monkeypatch.setattr(pipeline, "known_codes", lambda: {"cpc": set(), "pmdco": set()})
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    assert "cpc:411 is not in the pinned cpc source" in capsys.readouterr().err


def test_rdf_before_the_sources_are_built_is_an_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vocabulary").mkdir()
    assert pipeline.main(["rdf"]) == 3
    assert capsys.readouterr().err.startswith("error: data/processed/cpc21.parquet")
