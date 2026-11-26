"""The vocabulary's own rules, on the real files and on small broken copies."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from rdflib import DCTERMS, OWL, RDF, SKOS, XSD, Literal, URIRef
from yaml.constructor import ConstructorError

from r9lab_vocabulary import scheme

Schemes = dict[str, scheme.Scheme]
VERSIONS = {"bafu": {"2025-v2", "2026-v1"}}
ROOT = Path(__file__).resolve().parent.parent
# The ORCID iD ORCID itself publishes for tests.
TEST_ORCID = "https://orcid.org/0000-0002-1825-0097"
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
    meta = {"title": "t", "id_letter": "t", **(meta or {})}
    return {meta.get("slug", "t"): scheme.Scheme(meta.get("slug", "t"), meta, concepts)}


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


def test_every_concept_is_in_its_scheme(schemes: Schemes):
    g = scheme.to_graph(schemes, "test")
    for s in schemes.values():
        for cid in s.concepts:
            assert (URIRef(s.iri + cid), SKOS.inScheme, URIRef(s.iri)) in g


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
        ({"t1": {"label": "a"}}, "id must be t"),
        ({"t00001": {"label": "a"}}, "id must be t"),
        ({"t01": {"label": "a", "broader": ["t01"]}}, "loops back"),
        ({"t01": {"label": "a", "mappings": {"exact": ["wd:Q1"], "broad": ["wd:Q1"]}}}, "both exact and broad"),
        ({"t01": {"label": "a", "mappings": {"exact": ["zz:1"]}}}, "unknown prefix"),
        ({"t01": {"label": "a", "mappings": {"same": ["wd:Q1"]}}}, "unknown mapping relation"),
        ({"t01": {"label": "a", "mappings": {"broad": ["weee6:7"]}}}, "weee6:7 is not a weee6 code"),
        ({"t01": {"label": "a", "mappings": {"broad": ["unu1:0310"]}}}, "unu1:0310 is not a unu1 code"),
        ({"t01": {"label": "a", "mappings": {"broad": ["unu2:0406"]}}}, "unu2:0406 is not a unu2 code"),
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
        ({"scheme": {"slug": "0-1"}}, "slug must start with a lower-case letter"),
        ({"scheme": {"created": "2026-11-17"}}, "created must be a date"),
        ({"scheme": {"created": datetime(2026, 11, 17, tzinfo=UTC)}}, "created must be a date"),
        ({"t01": {}}, "t/t01: no label"),
        ({"t01": {"label": "a", "related": ["t09"]}}, "related t09 does not exist"),
        ({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t09"]}}, "replaced_by t09 does not exist"),
        ({"t01": {"label": "a", "mappings": {"close": ["t:t09"]}}}, "t:t09 does not exist"),
        (
            {"t01": {"label": "a", "notation": "x"}, "t02": {"label": "b", "notation": "x"}},
            "notation 'x' is also t01's",
        ),
        ({"t01": {"label": "a", "notation": 1}, "t02": {"label": "b", "notation": "1"}}, "notation '1' is also t01's"),
        ({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t01"]}}, "replaced_by t01 is itself"),
        (
            {
                "t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]},
                "t02": {"label": "b", "deprecated": True},
            },
            "replaced_by t02 is deprecated",
        ),
        ({"t01": None}, "t01: no label"),
    ],
)
def test_validate_catches(concepts: dict, message: str):
    # A row's "scheme" entry, never a concept id, sets the scheme's own fields.
    meta = concepts.get("scheme")
    errors = scheme.validate(one({k: v for k, v in concepts.items() if k != "scheme"}, meta), VERSIONS)
    assert any(message in e for e in errors), errors


def test_a_weee_category_link_points_into_annex_iii_of_the_directive():
    schemes = one({"t01": {"label": "a", "mappings": {"broad": ["weee6:6"]}}})
    assert scheme.validate(schemes, VERSIONS) == []
    g = scheme.to_graph(schemes, "test")
    target = URIRef("http://data.europa.eu/eli/dir/2012/19/oj#anx_III-6")
    assert (URIRef(schemes["t"].iri + "t01"), SKOS.broadMatch, target) in g


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


def test_the_first_author_alone_publishes():
    orcids = [TEST_ORCID, "https://orcid.org/0000-0001-5109-3700"]
    g = scheme.to_graph(one({"t01": {"label": "a"}}), "1.2.3", orcids=orcids)
    s = URIRef(scheme.BASE + "t/")
    assert set(g.objects(s, DCTERMS.publisher)) == {URIRef(TEST_ORCID)}
    assert len(set(g.objects(s, DCTERMS.creator))) == 2
    assert g.value(s, OWL.versionIRI) == URIRef(f"{scheme.BASE}1.2.3/t/")


ORCID = "https://orcid.org/0009-0006-6953-909X"


def read_sssom(path: Path) -> tuple[dict, list[dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = [line[1:] for line in lines if line.startswith("#")]
    rows = csv.DictReader((line for line in lines if not line.startswith("#")), delimiter="\t")
    return yaml.safe_load("\n".join(header)), list(rows)


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


def test_labels_list_every_live_concept_once_in_id_order(schemes: Schemes, tmp_path: Path):
    json_path, md_path = scheme.write_labels(schemes, "0.1.0", tmp_path)
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["version"] == "0.1.0"
    assert [s["slug"] for s in doc["schemes"]] == list(schemes)
    for s in doc["schemes"]:
        ids = [c["id"] for c in s["concepts"]]
        assert ids == sorted(cid for cid, c in schemes[s["slug"]].concepts.items() if not c.get("deprecated"))
    concepts = {c["id"]: c for s in doc["schemes"] for c in s["concepts"]}
    assert concepts["m0003"] == {
        "id": "m0003",
        "iri": f"{schemes['materials'].iri}m0003",
        "label": "carbon and low-alloy steel",
        "path": ["metal", "ferrous metal", "carbon and low-alloy steel"],
        "definition": "Steel without the chromium content of stainless steel, including galvanised sheet.",
        "pilot": ["ferrous"],
    }
    assert concepts["s01"]["pilot"] == ["ferrous"]
    assert concepts["c0006"]["pilot"] == ["electronics"]
    md = md_path.read_text(encoding="utf-8")
    assert "## R9lab material classes" in md
    assert "| m0003 | carbon and low-alloy steel | metal > ferrous metal > carbon and low-alloy steel |" in md


def test_labels_leave_out_a_deprecated_concept(tmp_path: Path):
    schemes = one({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]}, "t02": {"label": "b"}})
    json_path, md_path = scheme.write_labels(schemes, "test", tmp_path)
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["schemes"][0]["concepts"] == [
        {"id": "t02", "iri": f"{schemes['t'].iri}t02", "label": "b", "path": ["b"], "definition": None, "pilot": []}
    ]
    assert "t01" not in md_path.read_text(encoding="utf-8")


def test_a_close_pilot_mapping_marks_its_target_but_not_the_targets_descendants(schemes: Schemes):
    concepts = {c["id"]: c for s in scheme.labels(schemes) for c in s["concepts"]}
    assert "non_ferrous" in concepts["m0006"]["pilot"]
    assert "non_ferrous" not in concepts["m0017"]["pilot"]
    assert "non_ferrous" not in concepts["m0012"]["pilot"]


def pilot_fixture(materials: dict, pilot_mappings: dict) -> Schemes:
    return {
        "m": scheme.Scheme("m", {"title": "m", "id_letter": "m"}, materials),
        "p": scheme.Scheme(
            "p",
            {"title": "p", "id_letter": "p", "collection": "p"},
            {"p01": {"label": "x", "notation": "x", "mappings": pilot_mappings}},
        ),
    }


def test_broad_and_related_pilot_mappings_give_no_pilot_key():
    schemes = pilot_fixture({"m01": {"label": "a"}}, {"broad": ["m:m01"], "related": ["m:m01"]})
    assert scheme.labels(schemes)[0]["concepts"][0]["pilot"] == []


def test_pilot_keys_come_from_every_broader_parent():
    schemes = pilot_fixture(
        {"m01": {"label": "a"}, "m02": {"label": "b"}, "m03": {"label": "c", "broader": ["m01", "m02"]}},
        {"exact": ["m:m01"], "narrow": ["m:m02"]},
    )
    schemes["q"] = scheme.Scheme(
        "q",
        {"title": "q", "id_letter": "q", "collection": "q"},
        {"q01": {"label": "y", "notation": "y", "mappings": {"exact": ["m:m02"]}}},
    )
    m03 = {c["id"]: c for c in scheme.labels(schemes)[0]["concepts"]}["m03"]
    assert m03["pilot"] == ["x", "y"]
    assert m03["path"] == ["a", "c"]


def test_labels_md_escapes_a_pipe_in_any_cell(tmp_path: Path):
    schemes = one({"t01": {"label": "a|b", "definition": "c | d"}})
    _, md_path = scheme.write_labels(schemes, "test", tmp_path)
    assert "| t01 | a\\|b | a\\|b | c \\| d |  |" in md_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("slug", ["t", "wd"])
def test_a_scheme_slug_taken_by_another_scheme_or_prefix_is_an_error(tmp_path: Path, slug: str):
    (tmp_path / "a.yaml").write_text("scheme: {slug: t, title: a}\n")
    (tmp_path / "b.yaml").write_text(f"scheme: {{slug: {slug}, title: b}}\n")
    with pytest.raises(ValueError, match=rf"b\.yaml: scheme slug '{slug}' is already taken"):
        scheme.load(tmp_path)


@pytest.mark.parametrize(
    "concepts",
    [
        {"t01": {"label": "a", "deprecated": True}, "t02": {"label": "b", "deprecated": True, "broader": ["t01"]}},
        {"t01": {"label": "a", "deprecated": True}, "t02": {"label": "a"}},
        {"t01": {"label": "a", "notation": ""}, "t02": {"label": "b", "notation": ""}},
    ],
    ids=["deprecated-under-deprecated", "deprecated-label-reused", "empty-notations"],
)
def test_validate_accepts(concepts: dict):
    assert scheme.validate(one(concepts), VERSIONS) == []


def test_an_id_in_a_scheme_without_a_letter_needs_any_letter():
    errors = scheme.validate(one({"01": {"label": "a"}}, {"id_letter": None}), VERSIONS)
    assert any("id must be a letter plus 2-4 digits" in e for e in errors), errors
