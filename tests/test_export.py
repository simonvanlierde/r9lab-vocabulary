"""What `export` writes: the SKOS graph, the name-match CSV, the SSSOM mapping set and the label tables."""

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
from conftest import ROOT, VERSIONS, Schemes, one
from rdflib import DCTERMS, OWL, SKOS, XSD, Literal, URIRef

from r9lab_vocabulary import checks, export, scheme

if TYPE_CHECKING:
    from pathlib import Path


# The ORCID iD ORCID itself publishes for tests.
TEST_ORCID = "https://orcid.org/0000-0002-1825-0097"


@pytest.mark.parametrize("prefix", sorted(scheme.CODE_LISTS))
def test_unu_keys_are_typed_codes_not_iris(schemes: Schemes, prefix: str):
    g = export.to_graph(schemes, export.About("test"))
    datatype = URIRef(scheme.TERMS + scheme.CODE_LISTS[prefix][0])
    values = g.objects(None, URIRef(scheme.TERMS + "unuKey"))
    codes = [o for o in values if isinstance(o, Literal) and o.datatype == datatype]
    assert codes
    # A bare code, never a licensed key name.
    assert {str(o) for o in codes} <= scheme.FIXED_CODES[prefix]
    assert not [n for n in g.all_nodes() if str(n).startswith(f"{scheme.BASE}external/")]


def test_cc0_covers_the_vocabulary_and_its_own_schemes_only(schemes: Schemes):
    g = export.to_graph(schemes, export.About("test"))
    licensed = {str(s) for s in g.subjects(DCTERMS.license, scheme.CC0)}
    assert licensed == {scheme.BASE} | {s.iri for s in schemes.values()}


def test_text_fields_are_written_as_skos_notes():
    concept = {
        "label": "a",
        "definition": "An a.",
        "example": ["x", "y"],
        "note": "Not a b.",
        "editorial_note": "No BAFU dataset.",
        "hidden": ["aa"],
        "source": "https://www.wikidata.org/wiki/Q1",
    }
    schemes = one(
        {
            "t01": concept,
            "t02": {"label": "b", "definition": "A b.", "source": "Ashby 2017, sec. 2.2"},
            "t03": {"label": "c", "definition": "A c.", "source": "http://example.org/c"},
        }
    )
    assert checks.validate(schemes, VERSIONS) == []
    g = export.to_graph(schemes, export.About("test"))
    a, b = URIRef(schemes["t"].iri + "t01"), URIRef(schemes["t"].iri + "t02")
    assert set(g.objects(a, SKOS.example)) == {Literal("x", lang="en"), Literal("y", lang="en")}
    assert g.value(a, SKOS.scopeNote) == Literal("Not a b.", lang="en")
    assert g.value(a, SKOS.editorialNote) == Literal("No BAFU dataset.", lang="en")
    assert g.value(a, SKOS.hiddenLabel) == Literal("aa", lang="en")
    assert g.value(a, DCTERMS.source) == URIRef("https://www.wikidata.org/wiki/Q1")
    assert g.value(b, DCTERMS.source) == Literal("Ashby 2017, sec. 2.2")
    assert g.value(URIRef(schemes["t"].iri + "t03"), DCTERMS.source) == URIRef("http://example.org/c")


def test_a_weee_category_link_points_into_annex_iii_of_the_directive():
    schemes = one({"t01": {"label": "a", "mappings": {"broad": ["weee6:6"]}}})
    assert checks.validate(schemes, VERSIONS) == []
    g = export.to_graph(schemes, export.About("test"))
    target = URIRef("http://data.europa.eu/eli/dir/2012/19/oj#anx_III-6")
    assert (URIRef(schemes["t"].iri + "t01"), SKOS.broadMatch, target) in g


def test_a_deprecated_concept_is_marked_and_not_a_top_concept():
    schemes = one({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]}, "t02": {"label": "b"}})
    assert checks.validate(schemes, VERSIONS) == []
    g = export.to_graph(schemes, export.About("test"))
    old = URIRef(schemes["t"].iri + "t01")
    assert (old, OWL.deprecated, Literal("true", datatype=XSD.boolean)) in g
    assert (old, SKOS.topConceptOf, URIRef(schemes["t"].iri)) not in g


def test_name_matches_has_one_row_per_pattern_and_source(tmp_path: Path):
    schemes = one({"t01": {"label": "a", "names": {"bafu": ["^x"]}}})
    match = ("t", "t01", "bafu", "2026-v1", "^x", ["X, at plant", "x2"])
    export.write(schemes, export.About("test"), tmp_path, [match])
    assert (tmp_path / "name-matches.csv").read_text(encoding="utf-8").splitlines() == [
        "concept,label,source,pattern,matches",
        f"{schemes['t'].iri}t01,a,bafu-2026-v1,^x,2",
    ]


def test_the_first_author_alone_publishes():
    orcids = [TEST_ORCID, "https://orcid.org/0000-0001-5109-3700"]
    g = export.to_graph(one({"t01": {"label": "a"}}), export.About("1.2.3", orcids))
    s = URIRef(scheme.BASE + "t/")
    assert set(g.objects(s, DCTERMS.publisher)) == {URIRef(TEST_ORCID)}
    assert len(set(g.objects(s, DCTERMS.creator))) == 2
    assert g.value(s, OWL.versionIRI) == URIRef(f"{scheme.BASE}1.2.3/t/")


ORCID = "https://orcid.org/0009-0006-6953-909X"


def read_sssom(path: Path) -> tuple[dict, list[dict[str, str]]]:
    meta, rows = checks.read_sssom(path)
    return meta, list(rows)


def test_sssom_has_a_metadata_block_and_one_row_per_mapping(schemes: Schemes, tmp_path: Path):
    meta, rows = read_sssom(export.write_sssom(schemes, export.About("0.1.0", [ORCID, TEST_ORCID]), tmp_path))
    assert meta["mapping_set_id"] == f"{scheme.BASE}r9lab-vocabulary.sssom.tsv"
    assert meta["mapping_set_title"] == "R9lab reference vocabulary mappings"
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
        "object_label": "",
        "object_type": "",
        "object_source": "",
        "mapping_justification": "semapv:ManualMappingCuration",
        "author_id": "orcid:0009-0006-6953-909X",  # the first author, the publisher
    } in rows
    # A UNU-KEY has no IRI: an SSSOM 1.0 literal mapping, the key version in object_source.
    assert {
        "subject_id": "products:p0007",
        "subject_label": "laptop",
        "predicate_id": "skos:broadMatch",
        "object_id": "",
        "object_label": "0303",
        "object_type": "rdfs literal",
        "object_source": "r9lab:UNUKEYv1",
        "mapping_justification": "semapv:ManualMappingCuration",
        "author_id": "orcid:0009-0006-6953-909X",
    } in rows
    assert meta["curie_map"]["r9lab"] == scheme.TERMS
    keys = [(r["subject_id"], r["predicate_id"], r["object_id"]) for r in rows]
    assert keys == sorted(keys)


def test_sssom_leaves_out_mappings_from_or_to_a_deprecated_concept(tmp_path: Path):
    schemes = one(
        {
            "t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"], "mappings": {"exact": ["wd:Q1"]}},
            "t02": {"label": "b", "mappings": {"exact": ["wd:Q2"], "related": ["t:t01"]}},
        }
    )
    _, rows = read_sssom(export.write_sssom(schemes, export.About("test", [ORCID]), tmp_path))
    assert [(r["subject_id"], r["object_id"]) for r in rows] == [("t:t02", "wd:Q2")]


def test_labels_list_every_live_concept_once_in_id_order(schemes: Schemes, tmp_path: Path):
    json_path, md_path = export.write_labels(schemes, "0.1.0", tmp_path)
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["version"] == "0.1.0"
    assert [s["slug"] for s in doc["schemes"]] == list(schemes)
    for s in doc["schemes"]:
        ids = [c["id"] for c in s["concepts"]]
        assert ids == sorted(cid for cid, c in schemes[s["slug"]].concepts.items() if not c.get("deprecated"))
    concepts = {c["id"]: c for s in doc["schemes"] for c in s["concepts"]}
    assert {k: v for k, v in concepts["m0003"].items() if k not in ("note", "example")} == {
        "id": "m0003",
        "iri": f"{schemes['materials'].iri}m0003",
        "label": "carbon and low-alloy steel",
        "path": ["metal", "ferrous metal", "carbon and low-alloy steel"],
        "definition": schemes["materials"].concepts["m0003"]["definition"],
        "pilot": ["ferrous"],
        "pilot_any": ["ferrous"],
    }
    assert concepts["s01"]["pilot"] == ["ferrous"]
    assert concepts["c0006"]["pilot"] == ["electronics"]
    md = md_path.read_text(encoding="utf-8")
    assert "## R9lab material classes" in md
    assert "| m0003 | carbon and low-alloy steel | metal > ferrous metal > carbon and low-alloy steel |" in md


def test_labels_carry_the_scope_note_and_examples_but_not_the_editorial_note():
    concepts = {"t01": {"label": "a", "note": " Not b. ", "example": ["x "], "editorial_note": "Ask Ann."}}
    (c,) = export.labels(one(concepts))[0]["concepts"]
    assert (c["note"], c["example"]) == ("Not b.", ["x"])
    assert "Ask Ann." not in json.dumps(c)


def test_labels_leave_out_a_deprecated_concept(tmp_path: Path):
    schemes = one({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t02"]}, "t02": {"label": "b"}})
    json_path, md_path = export.write_labels(schemes, "test", tmp_path)
    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert doc["schemes"][0]["concepts"] == [
        {
            "id": "t02",
            "iri": f"{schemes['t'].iri}t02",
            "label": "b",
            "path": ["b"],
            "definition": "d",
            "note": "n",
            "example": ["e"],
            "pilot": [],
            "pilot_any": [],
        }
    ]
    assert "t01" not in md_path.read_text(encoding="utf-8")


# Concepts that span several pilot classes, so they carry no fixed key.
KEYLESS = {
    "materials:m0001",
    "materials:m0049",
    "components:c0018",
    "components:c0026",  # Depends on whether the part is a wound assembly, magnet or loose material.
    "components:c0027",
    "components:c0030",  # Depends on the blade material.
    "components:c0031",  # Depends on whether the assembly is chiefly electronics, metal or plastic.
    "components:c0032",  # Glass bulbs and other bulb designs may sort differently.
}


def test_every_material_and_component_has_a_pilot_key_or_is_known_to_span_several(schemes: Schemes):
    keyless = {
        f"{s['slug']}:{c['id']}"
        for s in export.labels(schemes)
        if s["slug"] in ("materials", "components")
        for c in s["concepts"]
        if not c["pilot"]
    }
    assert keyless == KEYLESS


def test_pilot_any_collects_the_keys_below_a_concept():
    child = {"broader": ["m01"]}
    materials = {"m01": {"label": "a"}, "m02": {"label": "b", **child}, "m03": {"label": "c", **child}}
    schemes = pilot_fixture(materials, {"narrow": ["m:m02"]})
    concepts = {c["id"]: (c["pilot"], c["pilot_any"]) for c in export.labels(schemes)[0]["concepts"]}
    assert concepts == {"m01": ([], ["x"]), "m02": (["x"], ["x"]), "m03": ([], [])}


def test_a_close_pilot_mapping_marks_its_target_but_not_the_targets_descendants():
    schemes = pilot_fixture({"m01": {"label": "a"}, "m02": {"label": "b", "broader": ["m01"]}}, {"close": ["m:m01"]})
    concepts = {c["id"]: c["pilot"] for c in export.labels(schemes)[0]["concepts"]}
    assert concepts == {"m01": ["x"], "m02": []}


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
    assert export.labels(schemes)[0]["concepts"][0]["pilot"] == []


def test_a_pilot_class_with_a_null_notation_is_keyed_by_its_id():
    schemes = pilot_fixture({"m01": {"label": "a"}}, {"exact": ["m:m01"]})
    schemes["p"].concepts["p01"]["notation"] = None
    assert export.labels(schemes)[0]["concepts"][0]["pilot"] == ["p01"]


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
    m03 = {c["id"]: c for c in export.labels(schemes)[0]["concepts"]}["m03"]
    assert m03["pilot"] == ["x", "y"]
    assert m03["path"] == ["a", "c"]


def test_labels_md_escapes_a_pipe_in_any_cell(tmp_path: Path):
    schemes = one({"t01": {"label": "a|b", "definition": "c | d"}})
    _, md_path = export.write_labels(schemes, "test", tmp_path)
    assert "| t01 | a\\|b | a\\|b | c \\| d |  |" in md_path.read_text(encoding="utf-8")


def test_labels_md_has_a_column_for_the_pilot_keys(tmp_path: Path):
    schemes = pilot_fixture({"m01": {"label": "a", "definition": "An a."}}, {"exact": ["m:m01"]})
    _, md_path = export.write_labels(schemes, "test", tmp_path)
    lines = md_path.read_text(encoding="utf-8").splitlines()
    assert "| id | label | path | definition | pilot |" in lines
    assert "| m01 | a | a | An a. | x |" in lines


# Builds the real vocabulary in a fresh interpreter, so each run gets its own hash seed.
BUILD = """
import sys
from datetime import date
from pathlib import Path
from r9lab_vocabulary import export, scheme
about = export.About("test", ["https://orcid.org/0000-0002-1825-0097"], None, date(2026, 2, 1))
export.write(scheme.load(Path(sys.argv[1])), about, Path(sys.argv[2]), [])
"""


def test_two_builds_write_the_same_bytes_whatever_the_hash_seed(tmp_path: Path):
    for seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = tmp_path / seed
        subprocess.run([sys.executable, "-c", BUILD, ROOT / "vocabulary", out], env=env, check=True)  # noqa: S603
    for name in ("r9lab-vocabulary.ttl", "r9lab-vocabulary.jsonld"):
        assert (tmp_path / "1" / name).read_bytes() == (tmp_path / "2" / name).read_bytes(), name
