"""This project's readers and commands, on small fixtures: no network."""

from __future__ import annotations

import io
import json
import sqlite3
import tarfile
import zipfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Never

import pytest
import rdflib
from rdflib import DCTERMS

from r9lab_vocabulary import _bafu_cache, pipeline, scheme

if TYPE_CHECKING:
    import urllib.request
    from collections.abc import Callable

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


def test_rdf_writes_the_vocabulary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stub_sources: Callable[..., None]):
    stub_sources()
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")  # 2026-01-01T00:00:00Z
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 0
    g = rdflib.Graph().parse(tmp_path / "r9lab-vocabulary.ttl")
    vocab = rdflib.URIRef(scheme.BASE)
    assert g.value(vocab, DCTERMS.modified) == rdflib.Literal(date(2026, 1, 1))
    assert g.value(vocab, DCTERMS.creator) == rdflib.URIRef("https://orcid.org/0009-0006-6953-909X")
    assert (tmp_path / "r9lab.shacl.ttl").read_bytes() == Path("shapes/r9lab.shacl.ttl").read_bytes()
    header = (tmp_path / "name-matches.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "concept,label,source,pattern,matches"


def test_commit_date_takes_source_date_epoch_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    assert pipeline.commit_date() == date(2026, 1, 1)


def test_commit_date_reads_the_package_checkout_not_one_around_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git: Callable[..., None]
):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    git(tmp_path, "init", "-q")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x", day="2026-03-04")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    assert pipeline.commit_date() == date(2026, 3, 4)
    (tmp_path / "unpacked").mkdir()
    monkeypatch.setattr(pipeline, "ROOT", tmp_path / "unpacked")
    assert pipeline.commit_date() is None


def test_commit_date_is_the_utc_date_of_a_commit_made_near_midnight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git: Callable[..., None]
):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    git(tmp_path, "init", "-q")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x", day="2026-03-04", time="23:30:00-05:00")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    assert pipeline.commit_date() == date(2026, 3, 5)  # 04:30 UTC, as SOURCE_DATE_EPOCH would give


def test_rdf_without_a_commit_date_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stub_sources: Callable[..., None],
):
    stub_sources()
    monkeypatch.setattr(pipeline, "commit_date", lambda: None)
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    assert "error: no commit date" in capsys.readouterr().err
    assert not (tmp_path / "r9lab-vocabulary.ttl").exists()


@pytest.mark.parametrize("citation", [None, "", "authors:\n  - family-names: x\n"])
def test_rdf_without_an_orcid_in_citation_cff_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stub_sources: Callable[..., None],
    citation: str | None,
):
    stub_sources(concepts="t01: {label: a, definition: d, example: e, note: n}")
    if citation is not None:
        (tmp_path / "CITATION.cff").write_text(citation)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    assert pipeline.main(["rdf", "--out", str(tmp_path / "dist")]) == 1
    assert capsys.readouterr().err.startswith("error: CITATION.cff")


def test_rdf_fails_on_a_code_the_sources_lack(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources(codes=set())
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    assert "cpc:411 is not in the pinned cpc source" in capsys.readouterr().err


def test_rdf_before_the_sources_are_built_is_an_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "vocabulary").mkdir()
    (tmp_path / "vocabulary" / "t.yaml").write_text("scheme: {slug: t, title: t}\n")
    assert pipeline.main(["rdf"]) == 3
    assert capsys.readouterr().err.startswith("error: data/processed/cpc21.parquet")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (None, "vocabulary: no *.yaml scheme files"),
        ("", "t.yaml: needs a `scheme` mapping"),
        ("- a\n", "t.yaml: needs a `scheme` mapping"),
        ("scheme: t\n", "t.yaml: needs a `scheme` mapping"),
        ("scheme: {title: t}\n", "t.yaml: needs a `scheme` mapping with a `slug`"),
        ("scheme: {slug: t}\nconcepts: [t01]\n", "t.yaml: `concepts` must map"),
        ("scheme: {slug: t\n", "while parsing a flow mapping"),
    ],
)
def test_rdf_reports_a_malformed_vocabulary_instead_of_crashing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str | None, message: str
):
    (tmp_path / "vocabulary").mkdir()
    if text is not None:
        (tmp_path / "vocabulary" / "t.yaml").write_text(text)
    monkeypatch.chdir(tmp_path)
    assert pipeline.main(["rdf"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert message in err


def test_rdf_reports_a_missing_tag_mappings_file_as_a_rule_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources(concepts="t01: {label: a, definition: d, example: e, note: n}")
    (tmp_path / "mappings" / "r9lab-tags.sssom.tsv").unlink()
    assert pipeline.main(["rdf", "--out", str(tmp_path / "dist")]) == 1
    assert capsys.readouterr().err == "error: mappings/r9lab-tags.sssom.tsv: missing\n"


# Prefixes no source pins: Wikidata is checked live by `just wikidata`, and a CPV code only
# for its 8-digit shape, as no CPV list is pinned.
UNCHECKED = {"wd", "cpv"}


def test_every_outside_prefix_has_its_codes_checked_or_is_exempt():
    routes = set(scheme.FIXED_CODES) | set(pipeline.SOURCE_CODES) | UNCHECKED
    assert set(scheme.PREFIXES) | set(scheme.CODE_LISTS) == routes


def test_rdf_fails_on_a_name_pattern_that_matches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources({"2026-v1": ["Copper, primary, at refinery"]})
    assert pipeline.main(["rdf", "--out", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "bafu pattern '^cast iron' matches no live name in bafu-2026-v1" in err
    assert "'^copper, (primary|secondary|at regional storage)'" not in err


# Namespaced, as the BAFU files are.
ECOSPOLD1 = """<?xml version='1.0' encoding='UTF-8'?>
<ecoSpold xmlns="http://www.EcoInvent.org/EcoSpold01"><dataset><metaInformation><processInformation>
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


def brightway_archive(tmp_path: Path, name: str | bytes) -> Path:
    db = tmp_path / "databases.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE activitydataset (code TEXT, database TEXT, location TEXT, name TEXT, type TEXT)")
    con.executemany(
        "INSERT INTO activitydataset VALUES (?, ?, ?, ?, ?)",
        [
            ("p1", "BAFU-2025-v2", "RER", name, "processwithreferenceproduct"),
            ("e1", "bio", None, "CO2", "emission"),
        ],
    )
    con.commit()
    con.close()
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, mode="w:gz") as t:
        t.add(db, arcname="BAFU-2025-v2.abc/lci/databases.db")
    return archive


def test_the_bafu_reader_takes_a_brightway_project_and_skips_biosphere_flows(tmp_path: Path):
    archive = brightway_archive(tmp_path, "Brass, at plant")
    _, rows = pipeline.parse({"id": "bafu-2025-v2"}, archive.read_bytes())
    assert rows == [{"code": "p1", "name": "Brass, at plant", "location": "RER"}]


def test_the_bafu_reader_refuses_a_process_without_a_reference_function():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bafu-2026-v1/process_a1.xml", ECOSPOLD1.format(name="x").replace("referenceFunction", "other"))
    with pytest.raises(ValueError, match=r"process_a1\.xml: no referenceFunction"):
        pipeline.parse({"id": "bafu-2026-v1"}, buf.getvalue())


def test_the_bafu_reader_refuses_a_brightway_archive_without_one_database():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.addfile(tarfile.TarInfo("BAFU-2025-v2.abc/README"), io.BytesIO())
    with pytest.raises(ValueError, match="found 0"):
        pipeline.parse({"id": "bafu-2025-v2"}, buf.getvalue())


def test_rdf_reports_a_broken_pattern_instead_of_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources(
        {"2026-v1": ["Brass, at plant"]},
        concepts="t01: {label: a, definition: d, example: e, note: n, names: {bafu: ['(']}}",
    )
    assert pipeline.main(["rdf", "--out", str(tmp_path / "dist")]) == 1
    assert "t/t01: bafu pattern '(':" in capsys.readouterr().err


def test_names_reports_a_broken_pattern_instead_of_crashing(
    capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources(
        {"2026-v1": ["Brass, at plant"]},
        concepts="t01: {label: a, definition: d, example: e, note: n, names: {bafu: ['(']}}",
    )
    assert pipeline.main(["names"]) == 1
    assert "t/t01: bafu pattern '(':" in capsys.readouterr().err


def test_withdrawn_bafu_datasets_are_not_live():
    live = pipeline.NAME_LISTS["bafu"].live
    assert live("Steel sheet, at plant")
    assert not live("xx Steel sheet, old, at plant")
    assert not live("XXX Tin, at plant")


def test_the_ecospold1_head_stops_before_the_exchanges():
    # Malformed past the parser's first read: a full parse would raise.
    junk = "</processInformation>" + " " * 70_000 + "<<broken"
    head = ECOSPOLD1.format(name="Brass, at plant").replace("</processInformation>", junk)
    assert pipeline.ecospold1_head(head.encode()) == ("Brass, at plant", "CH")


THREE_NAMES = {"2025-v2": ["Brass, at plant"], "2026-v1": ["Brass, at plant", "Brass, at regional storage"]}
BRASS = "t01: {label: a, definition: d, example: e, note: n, names: {bafu: ['^brass']}}"


def test_names_lists_every_match_of_one_source(capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]):
    stub_sources(THREE_NAMES, concepts=BRASS)
    assert pipeline.main(["names", "--source", "bafu-2026-v1"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "t/t01\tbafu-2026-v1\t^brass\tBrass, at plant",
        "t/t01\tbafu-2026-v1\t^brass\tBrass, at regional storage",
    ]


def test_names_summary_counts_per_source(capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]):
    stub_sources(THREE_NAMES, concepts=BRASS)
    assert pipeline.main(["names", "--summary"]) == 0
    assert capsys.readouterr().out.splitlines() == ["t/t01\tbafu-2025-v2\t1\t^brass", "t/t01\tbafu-2026-v1\t2\t^brass"]


def test_names_rejects_an_unknown_source(capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]):
    stub_sources(THREE_NAMES, concepts=BRASS)
    assert pipeline.main(["names", "--source", "bafu-2031-v1"]) == 2
    assert "known: bafu-2025-v2, bafu-2026-v1" in capsys.readouterr().err


def test_build_reuses_bafu_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    source = {"id": "bafu-2030-v1", "url": "https://example.org/bafu.zip", "status": "implemented"}
    (tmp_path / "sources.toml").write_text(
        '[[source]]\nid = "bafu-2030-v1"\nurl = "https://example.org/bafu.zip"\nstatus = "implemented"\n',
        encoding="utf-8",
    )
    raw = tmp_path / "source.zip"
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("process_sample.xml", '<dataset><referenceFunction name="Sample"/></dataset>')
    pipeline.sourceledger.record(source, raw, retrieved_at="2020-01-01T12:00:00Z")

    cache = tmp_path / "data/raw/.bafu-cache/bafu-2030-v1"
    assert pipeline.main(["build", "--dry-run"]) == 0
    assert not cache.exists()
    assert pipeline.main(["build"]) == 0
    assert cache.is_file()
    output_path = tmp_path / "data/processed/bafu-2030-v1.csv"
    output = output_path.read_bytes()

    reader = pipeline.NAME_LISTS["bafu"]

    def unexpected_read(_payload: bytes) -> Never:
        pytest.fail("an unchanged BAFU source was parsed again")

    monkeypatch.setitem(pipeline.NAME_LISTS, "bafu", pipeline.NameList(unexpected_read, reader.live))
    assert pipeline.main(["build"]) == 0
    assert output_path.read_bytes() == output

    retrieved_at = "2020-01-02T12:00:00Z"
    pipeline.sourceledger.record(source, raw, retrieved_at=retrieved_at)
    assert pipeline.main(["build"]) == 0
    (row,) = pipeline.sourceledger.read_output(output_path)
    assert row["retrieved_at"] == retrieved_at
    package = json.loads(output_path.with_name("datapackage.json").read_text(encoding="utf-8"))
    assert package["resources"][0]["sourceledger"]["retrieved_at"] == retrieved_at
    refreshed_output = output_path.read_bytes()

    (tmp_path / "data/raw/bafu-2030-v1.zip").write_bytes(b"changed behind the fetch record")
    assert pipeline.main(["build"]) == 3
    assert output_path.read_bytes() == refreshed_output


def test_build_preserves_brightway_blob_cells_without_caching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    manifest = tmp_path / "sources.toml"
    manifest.write_text(
        'output_format = "parquet"\n[[source]]\nid = "bafu-2030-v1"\n'
        'url = "https://example.org/bafu.tar.gz"\nstatus = "implemented"\n',
        encoding="utf-8",
    )
    (source,) = pipeline.sourceledger.load_manifest(manifest)
    pipeline.sourceledger.record(source, brightway_archive(tmp_path, b"Sample"))

    assert pipeline.main(["build"]) == 0
    (row,) = pipeline.sourceledger.read_output(tmp_path / "data/processed/bafu-2030-v1.parquet")
    assert row["name"] == "b'Sample'"
    assert not (tmp_path / "data/raw/.bafu-cache/bafu-2030-v1").exists()


def test_bafu_cache_misses_after_input_changes_or_corruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(_bafu_cache, "DIRECTORY", tmp_path / "cache")
    reader_file = tmp_path / "reader.py"
    reader_file.write_text("# first revision", encoding="utf-8")
    calls = 0

    def reader(payload: bytes) -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [{"code": payload.decode(), "name": "Café", "location": ""}]

    def read(payload: bytes) -> list[dict[str, str]]:
        return _bafu_cache.read_names(
            "bafu-2030-v1",
            payload,
            reader=reader,
            version=_bafu_cache.reader_version(reader_file),
        )

    original = read(b"example")
    assert read(b"example") == original
    assert calls == 1
    assert read(b"changed")[0]["code"] == "changed"
    assert calls == 2
    reader_file.write_text("# second revision", encoding="utf-8")
    assert read(b"changed")[0]["code"] == "changed"
    assert calls == 3
    entry = tmp_path / "cache/bafu-2030-v1"
    entry.write_bytes(entry.read_bytes().replace(b'"changed"', b'"corrupt"'))
    assert read(b"changed")[0]["code"] == "changed"
    assert calls == 4
    entry.write_text("incomplete", encoding="utf-8")
    assert read(b"changed")[0]["code"] == "changed"
    assert calls == 5


def test_bafu_cache_failure_keeps_the_reader_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cache = tmp_path / "cache"
    cache.touch()
    monkeypatch.setattr(_bafu_cache, "DIRECTORY", cache)
    calls = 0

    def reader(_payload: bytes) -> Never:
        nonlocal calls
        calls += 1
        msg = "archive could not be read"
        raise OSError(msg)

    with pytest.raises(OSError, match="archive could not be read"):
        _bafu_cache.read_names("bafu-2030-v1", b"example", reader=reader, version="1")
    assert calls == 1


def test_wikidata_fails_on_a_missing_or_redirected_item(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stub_sources: Callable[..., None]
):
    stub_sources(concepts="t01: {label: a, mappings: {exact: [wd:Q1]}, definition: d, example: e, note: n}\n"
                 "  t02: {label: b, mappings: {exact: [wd:Q2]}, definition: d, example: e, note: n}\n"
                 "  t03: {label: c, mappings: {close: [wd:Q3]}, definition: d, example: e, note: n}")  # fmt: skip
    entities = {
        "Q1": {"id": "Q1", "labels": {"en": {"value": "universe"}}},
        "Q2": {"id": "Q2", "missing": ""},
        "Q3": {"id": "Q30", "labels": {"en": {"value": "United States"}}},  # Q3 now redirects to Q30
    }
    requests = []

    def urlopen(req: urllib.request.Request, timeout: float) -> io.BytesIO:
        requests.append((req.full_url, req.get_header("User-agent"), timeout))
        return io.BytesIO(json.dumps({"entities": entities}).encode())

    monkeypatch.setattr(pipeline.urllib.request, "urlopen", urlopen)
    assert pipeline.main(["wikidata"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "t/t01\ta\texact\tQ1\tuniverse",
        "t/t02\tb\texact\tQ2\tMISSING OR REDIRECTED",
        "t/t03\tc\tclose\tQ3\tMISSING OR REDIRECTED",
    ]
    [(url, agent, _)] = requests
    assert "ids=Q1%7CQ2%7CQ3" in url
    assert agent == pipeline.USER_AGENT


def test_help_names_the_projects_own_commands(capsys: pytest.CaptureFixture[str]):
    assert pipeline.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "  r9lab-vocabulary fetch " in out  # sourceledger's own help comes first
    for command in ("rdf", "names", "wikidata", "diff REF"):
        assert f"\n  r9lab-vocabulary {command} " in out, command
    assert "`just` lists every recipe" in out
