"""The vocabulary's own rules, on the real files and on small broken copies."""

from pathlib import Path

import pytest
from rdflib import OWL, RDF, SKOS, XSD, Graph, Literal, URIRef
from yaml.constructor import ConstructorError

from r9lab_vocabulary import scheme

Schemes = dict[str, scheme.Scheme]
RELEASES = {"2025-v2", "2026-v1"}
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
    assert scheme.validate(schemes, RELEASES) == []


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
        ({"t01": {"label": "a", "bafu": ["("]}}, "bafu pattern"),
        ({"t01": {"label": "a", "bafu": [{"pattern": "^x"}]}}, "non-empty releases list"),
        (
            {"t01": {"label": "a", "bafu": [{"pattern": "^x", "releases": ["2026-v1"], "since": 1}]}},
            "exactly a pattern",
        ),
        ({"t01": {"label": "a", "bafu": [{"pattern": "^x", "releases": ["2031-v1"]}]}}, "unknown release '2031-v1'"),
        ({"t01": {"label": "a", "bafu": "^ab"}}, "bafu must be a list"),
        ({"t01": {"label": "a", "bafu": [""]}}, "must be a non-empty pattern"),
        ({"t01": {"label": "a", "bafu": [None]}}, "must be a non-empty pattern"),
        ({"t01": {"label": "a", "bafu": [{"pattern": "^x", "releases": "2026-v1"}]}}, "must be a non-empty pattern"),
        ({"t01": {"label": "a", "mappings": {"exact": "wd:Q1"}}}, "mappings must map each relation to a list"),
    ],
)
def test_validate_catches(concepts: dict, message: str):
    errors = scheme.validate(one(concepts), RELEASES)
    assert any(message in e for e in errors), errors


def test_a_deprecated_concept_is_marked_and_not_a_top_concept():
    schemes = one({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]}, "t02": {"label": "b"}})
    assert scheme.validate(schemes, RELEASES) == []
    g = scheme.to_graph(schemes, "test")
    old = URIRef(schemes["t"].iri + "t01")
    assert (old, OWL.deprecated, Literal("true", datatype=XSD.boolean)) in g
    assert (old, SKOS.topConceptOf, URIRef(schemes["t"].iri)) not in g


def test_bafu_patterns_search_live_names_of_the_releases_they_apply_to():
    schemes = one(
        {
            "t01": {"label": "a", "bafu": ["^steel sheet", {"pattern": "^tin\\b", "releases": ["2026-v1"]}]},
            "t02": {"label": "b", "deprecated": True, "bafu": ["^steel"]},
        }
    )
    names = {
        "2025-v2": ["Steel sheet, uncoated, at plant", "xx Steel sheet, old, at plant", "Tin, at plant"],
        "2026-v1": ["STEEL SHEET, zinc-coated", "Tin, at regional storage", "Tinplate"],
    }
    assert scheme.bafu_matches(schemes, names) == [
        ("t", "t01", "2025-v2", "^steel sheet", ["Steel sheet, uncoated, at plant"]),
        ("t", "t01", "2026-v1", "^steel sheet", ["STEEL SHEET, zinc-coated"]),
        ("t", "t01", "2026-v1", "^tin\\b", ["Tin, at regional storage"]),
    ]


def test_bafu_candidates_has_one_row_per_pattern_and_release(tmp_path: Path):
    schemes = one({"t01": {"label": "a", "bafu": ["^x"]}})
    scheme.write(schemes, "test", tmp_path, [("t", "t01", "2026-v1", "^x", ["X, at plant", "x2"])])
    assert (tmp_path / "bafu-candidates.csv").read_text(encoding="utf-8").splitlines() == [
        "concept,label,release,pattern,matches",
        f"{schemes['t'].iri}t01,a,2026-v1,^x,2",
    ]


def test_a_repeated_concept_id_is_an_error_not_an_overwrite(tmp_path: Path):
    (tmp_path / "t.yaml").write_text("scheme: {slug: t, title: t}\nconcepts:\n  t01: {label: a}\n  t01: {label: b}\n")
    with pytest.raises(ConstructorError, match="repeated key t01"):
        scheme.load(tmp_path)
