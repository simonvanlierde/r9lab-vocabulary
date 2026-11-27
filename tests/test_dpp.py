import csv
from typing import TYPE_CHECKING

import pytest
from conftest import ROOT
from pyshacl import validate
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from r9lab_vocabulary import dpp, scheme

if TYPE_CHECKING:
    from pathlib import Path

TABLE = ROOT / dpp.CROSSWALK
EUDPP = Namespace("https://w3id.org/eudpp#")
SCHEMA = Namespace("https://schema.org/")


def test_dpp_crosswalk_covers_current_vocabulary():
    assert not dpp.validate_crosswalk(scheme.load(ROOT / "vocabulary"), TABLE)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing", "missing coverage"),
        ("duplicate", "duplicate row"),
        ("unknown", "unknown concept"),
        ("target", "is not an OWL class"),
        ("none-with-target", "must have no target"),
        ("partial-row", "expected 6 columns"),
        ("unknown-disposition", "unknown disposition"),
    ],
)
def test_dpp_crosswalk_rejects_bad_rows(tmp_path: Path, mutation: str, error: str):
    index = TABLE.with_name(dpp.CLASS_INDEX)
    tmp_path.joinpath(index.name).write_bytes(index.read_bytes())
    rows = TABLE.read_text(encoding="utf-8").splitlines()
    index = next(i for i, row in enumerate(rows) if row.startswith("electronics-v1\tcomponents\tc0009\t"))
    row = rows[index].split("\t")
    match mutation:
        case "missing":
            rows.pop(index)
        case "duplicate":
            rows.append(rows[index])
        case "unknown":
            row[2] = "c9999"
        case "target":
            row[4] = "http://www.semanticweb.org/RePlanIT/hasComponent"
        case "none-with-target":
            row[3] = "no-match"
        case "partial-row":
            row.pop()
        case "unknown-disposition":
            row[3] = "maybe"
    if mutation not in {"missing", "duplicate"}:
        rows[index] = "\t".join(row)
    table = tmp_path / TABLE.name
    table.write_text("\n".join(rows) + "\n", encoding="utf-8")
    assert any(error in finding for finding in dpp.validate_crosswalk(scheme.load(ROOT / "vocabulary"), table))


def test_dpp_raw_pin_refuses_changed_bytes(tmp_path: Path):
    wrong = tmp_path / "wrong.ttl"
    wrong.write_text("# changed upstream\n", encoding="utf-8")
    errors = dpp.validate_crosswalk(scheme.load(ROOT / "vocabulary"), TABLE, electronics=wrong, mat=wrong)
    assert len(errors) == 2
    assert all("SHA-256" in error for error in errors)


def test_dpp_local_profile_accepts_sample_and_rejects_bad_code():
    sample = Graph().parse(TABLE.with_name("cirpass-2-example.ttl"))
    shapes = Graph().parse(ROOT / "shapes" / "dpp-exchange.shacl.ttl")
    conforms, _, report = validate(sample, shacl_graph=shapes)
    assert conforms, report
    component, concept_uri = next(sample.subject_objects(SCHEMA.additionalType))
    concept_id = str(concept_uri).rsplit("/", 1)[-1]
    with TABLE.open(encoding="utf-8", newline="") as stream:
        candidate = next(row for row in csv.DictReader(stream, delimiter="\t") if row["concept_id"] == concept_id)
    assert (component, RDF.type, URIRef(candidate["target_iri"])) in sample
    material_type = next(sample.subjects(EUDPP.materialTypeValue))
    schemes = scheme.load(ROOT / "vocabulary")
    assert str(sample.value(material_type, EUDPP.materialTypeValue)) in schemes["materials"].concepts
    sample.set((material_type, EUDPP.materialTypeValue, Literal("polycarbonate")))
    conforms, _, report = validate(sample, shacl_graph=shapes)
    assert not conforms
    assert "The material code must have R9lab concept ID syntax." in str(report)


def test_dpp_cli_checks_the_proposal_and_optional_source(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    monkeypatch.chdir(ROOT)
    assert dpp.main([]) == 0
    assert dpp.CROSSWALK.as_posix() in capsys.readouterr().out
    wrong = tmp_path / "wrong.ttl"
    wrong.write_text("# changed upstream\n", encoding="utf-8")
    assert dpp.main(["--electronics", str(wrong)]) == 1
    assert "SHA-256" in capsys.readouterr().err
    assert dpp.main(["--mat", str(tmp_path / "missing.ttl")]) == 3
    assert "missing.ttl" in capsys.readouterr().err
