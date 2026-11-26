"""The vocabulary's own rules, on the real files and on small broken copies."""

from pathlib import Path

import pytest
import yaml
from rdflib import OWL, RDF, SKOS, XSD, Graph, Literal, URIRef
from yaml.constructor import ConstructorError

from r9lab_vocabulary import scheme

Schemes = dict[str, scheme.Scheme]
VERSIONS = {"bafu": {"2025-v2", "2026-v1"}}
ROOT = Path(__file__).resolve().parent.parent
# The pilot's frozen L1 keys (photo-study pilot registration, 5 November 2026).
PILOT_KEYS = {
    "ferrous",
    "non_ferrous",
    "plastic",
    "electronics",
    "battery",
    "display_glass",
    "rubber",
    "cable",
    "magnet",
    "other",
}


@pytest.fixture(scope="module")
def schemes() -> dict[str, scheme.Scheme]:
    return scheme.load(ROOT / "vocabulary")


def one(concepts: dict, meta: dict | None = None) -> dict[str, scheme.Scheme]:
    return {"t": scheme.Scheme("t", meta or {"title": "t", "id_letter": "t"}, concepts)}


def test_the_vocabulary_breaks_no_rule(schemes: Schemes):
    assert scheme.validate(schemes, VERSIONS) == []


def test_the_pilot_collection_keeps_the_frozen_keys(schemes: Schemes):
    g = scheme.to_graph(schemes, "test")
    coll = URIRef(schemes["pilot-classes"].iri + "collection")
    members = set(g.objects(coll, SKOS.member))
    assert {str(g.value(m, SKOS.notation)) for m in members} == PILOT_KEYS


def test_every_pilot_class_maps_into_the_material_or_component_axis(schemes: Schemes):
    for cid, c in schemes["pilot-classes"].concepts.items():
        targets = {prefix for _, prefix, _ in scheme.mappings(c)}
        assert targets, cid
        assert targets <= {"materials", "components"}, cid


def test_the_material_axis_is_topped_by_ashbys_six_families(schemes: Schemes):
    tops = {c["label"] for c in schemes["materials"].concepts.values() if not c.get("broader")}
    assert tops == {"metal", "polymer", "elastomer", "glass", "ceramic", "hybrid material"}


# rdflib's JSON-LD parser builds a ConjunctiveGraph internally whatever the caller passes.
@pytest.mark.filterwarnings("ignore:ConjunctiveGraph is deprecated:DeprecationWarning")
def test_every_concept_is_in_its_scheme_and_round_trips_through_turtle(schemes: Schemes, tmp_path: Path):
    scheme.write(schemes, "test", tmp_path, [])
    g = Graph().parse(tmp_path / "r9lab-vocabulary.ttl")
    for s in schemes.values():
        for cid in s.concepts:
            assert (URIRef(s.iri + cid), SKOS.inScheme, URIRef(s.iri)) in g
    assert len(g) == len(scheme.to_graph(schemes, "test"))
    assert len(Graph().parse(tmp_path / "r9lab-vocabulary.jsonld")) == len(g)


def test_licensed_schemes_keep_codes_only(schemes: Schemes):
    g = scheme.to_graph(schemes, "test")
    base = scheme.PREFIXES["unu1"]
    nodes = {s for s in g.subjects(RDF.type, SKOS.Concept) if str(s).startswith(base)}
    assert nodes
    for node in nodes:
        assert str(g.value(node, SKOS.prefLabel)) == str(node).removeprefix(base)


def test_check_codes_names_a_code_missing_from_the_pinned_source(schemes: Schemes):
    errors = scheme.check_codes(schemes, {"cpc": {"411"}})
    assert "materials/m0002: cpc:411 is not in the pinned cpc source" not in errors
    assert "materials/m0003: cpc:41121 is not in the pinned cpc source" in errors


@pytest.mark.parametrize(
    ("concepts", "message"),
    [
        ({"t01": {"label": "a", "broader": ["t02"]}, "t02": {"label": "b", "broader": ["t01"]}}, "loops back"),
        ({"t01": {"label": "a", "broader": ["t09"]}}, "broader t09 does not exist"),
        ({"t01": {"label": "a"}, "t02": {"label": "A"}}, "label 'A' is also t01's"),
        ({"x01": {"label": "a"}}, "id must be t"),
        ({"t01": {"label": "a", "mappings": {"exact": ["wd:Q1"], "broad": ["wd:Q1"]}}}, "both exact and broad"),
        ({"t01": {"label": "a", "mappings": {"exact": ["zz:1"]}}}, "unknown prefix"),
        ({"t01": {"label": "a", "mappings": {"same": ["wd:Q1"]}}}, "unknown mapping relation"),
        ({"t01": {"label": "a", "replaced_by": ["t02"]}, "t02": {"label": "b"}}, "needs deprecated"),
        (
            {"t01": {"label": "a", "deprecated": True}, "t02": {"label": "b", "broader": ["t01"]}},
            "broader t01 is deprecated",
        ),
        ({"t01": {"label": "a", "names": {"bafu": ["("]}}}, "bafu pattern '('"),
        ({"t01": {"label": "a", "names": {"bafu": [{"pattern": "^x"}]}}}, "non-empty versions list"),
        (
            {"t01": {"label": "a", "names": {"bafu": [{"pattern": "^x", "versions": ["2026-v1"], "since": 1}]}}},
            "exactly a pattern",
        ),
        (
            {"t01": {"label": "a", "names": {"bafu": [{"pattern": "^x", "versions": ["2031-v1"]}]}}},
            "unknown version '2031-v1'",
        ),
        ({"t01": {"label": "a", "names": {"ecoinvent": ["^x"]}}}, "family 'ecoinvent' has no pinned source"),
        ({"t01": {"label": "a", "names": ["^ab"]}}, "names must map each family to a list"),
        ({"t01": {"label": "a", "names": {"bafu": "^ab"}}}, "names must map each family to a list"),
        ({"t01": {"label": "a", "names": {"bafu": [""]}}}, "must be a non-empty pattern"),
        ({"t01": {"label": "a", "names": {"bafu": [None]}}}, "must be a non-empty pattern"),
        (
            {"t01": {"label": "a", "names": {"bafu": [{"pattern": "^x", "versions": "2026-v1"}]}}},
            "must be a non-empty pattern",
        ),
        ({"t01": {"label": "a", "mappings": {"exact": "wd:Q1"}}}, "mappings must map each relation to a list"),
    ],
)
def test_validate_catches(concepts: dict, message: str):
    errors = scheme.validate(one(concepts), VERSIONS)
    assert any(message in e for e in errors), errors


def test_a_deprecated_concept_is_marked_and_not_a_top_concept():
    schemes = one({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]}, "t02": {"label": "b"}})
    assert scheme.validate(schemes, VERSIONS) == []
    g = scheme.to_graph(schemes, "test")
    old = URIRef(schemes["t"].iri + "t01")
    assert (old, OWL.deprecated, Literal("true", datatype=XSD.boolean)) in g
    assert (old, SKOS.topConceptOf, URIRef(schemes["t"].iri)) not in g


def test_name_patterns_search_the_versions_they_apply_to():
    schemes = one(
        {
            "t01": {
                "label": "a",
                "names": {"bafu": ["^steel sheet", {"pattern": "^tin\\b", "versions": ["2026-v1"]}]},
            },
            "t02": {"label": "b", "deprecated": True, "names": {"bafu": ["^steel"]}},
        }
    )
    lists = {
        "bafu": {
            "2025-v2": ["Steel sheet, uncoated, at plant", "Tin, at plant"],
            "2026-v1": ["STEEL SHEET, zinc-coated", "Tin, at regional storage", "Tinplate"],
        }
    }
    assert scheme.name_matches(schemes, lists) == [
        ("t", "t01", "bafu", "2025-v2", "^steel sheet", ["Steel sheet, uncoated, at plant"]),
        ("t", "t01", "bafu", "2026-v1", "^steel sheet", ["STEEL SHEET, zinc-coated"]),
        ("t", "t01", "bafu", "2026-v1", "^tin\\b", ["Tin, at regional storage"]),
    ]


def test_name_matches_has_one_row_per_pattern_and_source(tmp_path: Path):
    schemes = one({"t01": {"label": "a", "names": {"bafu": ["^x"]}}})
    scheme.write(schemes, "test", tmp_path, [("t", "t01", "bafu", "2026-v1", "^x", ["X, at plant", "x2"])])
    assert (tmp_path / "name-matches.csv").read_text(encoding="utf-8").splitlines() == [
        "concept,label,source,pattern,matches",
        f"{schemes['t'].iri}t01,a,bafu-2026-v1,^x,2",
    ]


def test_a_repeated_concept_id_is_an_error_not_an_overwrite(tmp_path: Path):
    (tmp_path / "t.yaml").write_text("scheme: {slug: t, title: t}\nconcepts:\n  t01: {label: a}\n  t01: {label: b}\n")
    with pytest.raises(ConstructorError, match="repeated key t01"):
        scheme.load(tmp_path)


ORCID = "https://orcid.org/0009-0006-6953-909X"


def read_sssom(path: Path) -> tuple[dict, list[dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = [line[1:] for line in lines if line.startswith("#")]
    rows = [line.split("\t") for line in lines if not line.startswith("#")]
    return yaml.safe_load("\n".join(header)), [dict(zip(rows[0], r, strict=True)) for r in rows[1:]]


def test_sssom_has_a_metadata_block_and_one_row_per_mapping(schemes: Schemes, tmp_path: Path):
    meta, rows = read_sssom(scheme.write_sssom(schemes, "0.1.0", tmp_path, ORCID))
    assert meta["mapping_set_id"] == f"{scheme.BASE}r9lab-vocabulary.sssom.tsv"
    assert meta["mapping_set_version"] == "0.1.0"
    assert meta["license"] == "https://creativecommons.org/publicdomain/zero/1.0/"
    assert meta["curie_map"]["materials"] == schemes["materials"].iri
    assert meta["curie_map"]["cpc"] == scheme.PREFIXES["cpc"]
    assert len(rows) == sum(1 for s in schemes.values() for c in s.concepts.values() for _ in scheme.mappings(c))
    assert {
        "subject_id": "materials:m0001",
        "subject_label": "metal",
        "predicate_id": "skos:exactMatch",
        "object_id": "wd:Q11426",
        "mapping_justification": "semapv:ManualMappingCuration",
        "author_id": "orcid:0009-0006-6953-909X",
    } in rows
    keys = [(r["subject_id"], r["predicate_id"], r["object_id"]) for r in rows]
    assert keys == sorted(keys)


def test_sssom_leaves_out_mappings_from_or_to_a_deprecated_concept(tmp_path: Path):
    schemes = one(
        {
            "t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"], "mappings": {"exact": ["wd:Q1"]}},
            "t02": {"label": "b", "mappings": {"exact": ["wd:Q2"], "related": ["t:t01"]}},
        }
    )
    _, rows = read_sssom(scheme.write_sssom(schemes, "test", tmp_path, ORCID))
    assert [(r["subject_id"], r["object_id"]) for r in rows] == [("t:t02", "wd:Q2")]
