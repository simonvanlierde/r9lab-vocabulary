"""This project's readers and commands, on small fixtures: no network."""

from __future__ import annotations

import io
import sqlite3
import tarfile
import zipfile
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
    monkeypatch.setattr(pipeline, "bafu_names", dict)
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "r9lab-vocabulary.ttl").stat().st_size > 0
    header = (tmp_path / "bafu-candidates.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "concept,label,release,pattern,matches"


def test_rdf_fails_on_a_code_the_sources_lack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    monkeypatch.setattr(pipeline, "known_codes", lambda: {"cpc": set(), "pmdco": set()})
    monkeypatch.setattr(pipeline, "bafu_names", dict)
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    assert "cpc:411 is not in the pinned cpc source" in capsys.readouterr().err


def test_rdf_before_the_sources_are_built_is_an_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vocabulary").mkdir()
    assert pipeline.main(["rdf"]) == 3
    assert capsys.readouterr().err.startswith("error: data/processed/cpc21.parquet")


def test_rdf_fails_on_a_bafu_pattern_that_matches_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    everything = type("All", (set,), {"__contains__": lambda *_: True})()
    monkeypatch.setattr(pipeline, "known_codes", lambda: {"cpc": everything, "pmdco": everything})
    monkeypatch.setattr(pipeline, "bafu_names", lambda: {"2026-v1": ["Copper, primary, at refinery"]})
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "'^cast iron' matches no live activity in BAFU 2026-v1" in err
    assert "'^copper, (primary|secondary|at regional storage)'" not in err


ECOSPOLD1 = """<?xml version='1.0' encoding='UTF-8'?>
<ecoSpold><dataset><metaInformation><processInformation>
<referenceFunction name="{name}" unit="kg"/><geography location="CH"/>
</processInformation></metaInformation></dataset></ecoSpold>"""


def test_the_bafu_reader_takes_an_ecospold1_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bafu-2026-v1/", "")
        z.writestr("bafu-2026-v1/process_b2.xml", ECOSPOLD1.format(name="Tin, at regional storage"))
        z.writestr("bafu-2026-v1/process_a1.xml", ECOSPOLD1.format(name="Brass, at plant"))
    columns, rows = pipeline.parse({"id": "bafu-2026-v1"}, buf.getvalue())
    assert columns == ["code", "name", "location"]
    assert rows == [
        {"code": "a1", "name": "Brass, at plant", "location": "CH"},
        {"code": "b2", "name": "Tin, at regional storage", "location": "CH"},
    ]


def test_the_bafu_reader_takes_a_brightway_project_and_skips_biosphere_flows(tmp_path: Path):
    db = tmp_path / "databases.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE activitydataset (code TEXT, database TEXT, location TEXT, name TEXT, type TEXT)")
    con.executemany(
        "INSERT INTO activitydataset VALUES (?, ?, ?, ?, ?)",
        [
            ("p1", "BAFU-2025-v2", "RER", "Brass, at plant", "processwithreferenceproduct"),
            ("e1", "bio", None, "CO2", "emission"),
        ],
    )
    con.commit()
    con.close()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(db, arcname="BAFU-2025-v2.abc/lci/databases.db")
    _, rows = pipeline.parse({"id": "bafu-2025-v2"}, buf.getvalue())
    assert rows == [{"code": "p1", "name": "Brass, at plant", "location": "RER"}]


def test_rdf_reports_a_broken_pattern_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    voc = tmp_path / "vocabulary"
    voc.mkdir()
    (voc / "t.yaml").write_text(
        "scheme: {slug: t, title: t, id_letter: t}\nconcepts:\n  t01: {label: a, bafu: ['(']}\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "known_codes", lambda: {"cpc": set(), "pmdco": set()})
    monkeypatch.setattr(pipeline, "bafu_names", lambda: {"2026-v1": ["Brass, at plant"]})
    assert pipeline.main(["rdf", "--out", str(tmp_path / "dist")]) == 1
    assert "t/t01: bafu pattern '(':" in capsys.readouterr().err


def test_bafu_reports_a_broken_pattern_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    voc = tmp_path / "vocabulary"
    voc.mkdir()
    (voc / "t.yaml").write_text(
        "scheme: {slug: t, title: t, id_letter: t}\nconcepts:\n  t01: {label: a, bafu: ['(']}\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "bafu_names", lambda: {"2026-v1": ["Brass, at plant"]})
    assert pipeline.main(["bafu"]) == 1
    assert "t/t01: bafu pattern '(':" in capsys.readouterr().err
