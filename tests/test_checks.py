"""The vocabulary's rules (`checks`), on the real files and on small broken copies."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from conftest import VERSIONS, Schemes, one

from r9lab_vocabulary import checks

if TYPE_CHECKING:
    from pathlib import Path


def test_check_tag_mappings_catches(schemes: Schemes, tmp_path: Path):
    path = tmp_path / "t.sssom.tsv"
    j = "semapv:AgentBasedMatching"
    schemes = schemes | one({"t01": {"label": "old", "deprecated": True}})
    path.write_text(
        "#curie_map:\n#  materials: https://example.org/m/\n#  r9lab-tag: https://example.org/t/\n"
        "#  semapv: https://w3id.org/semapv/vocab/\n#  skos: http://www.w3.org/2004/02/skos/core#\n"
        "#  sssom: https://w3id.org/sssom/\n#  t: https://example.org/old/\n#  orcid: https://orcid.org/\n"
        "subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\treviewer_id\n"
        f"r9lab-tag:material/steel\tsteel\tskos:broadMatch\tmaterials:m0002\tferrous metal\t{j}"
        "\torcid:0000-0002-1825-0097\n"
        f"r9lab-tag:material/steel\tsteel\tskos:exactMatch\tmaterials:m0003\tcarbon and low-alloy steel\t{j}\n"
        f"r9lab-tag:material/Glass\tGlass\tskos:sameAs\tmaterials:m9999\t\t{j}\n"
        "r9lab-tag:material/pe\tpe\texact\tmaterials:m0022\tpolyethylene\tby hand\n"
        f"r9lab-tag:pc%20abs\tpc abs\tskos:exactMatch\tcomponents:c0001\tbattery\t{j}\n"
        f"r9lab-tag:material/pp\tpp\tskos:exactMatch\tmaterials:m0023\tPP\t{j}\n"
        f"r9lab-tag:material/fan%20blades\tfan blades\tskos:exactMatch\tsssom:NoTermFound\t\t{j}\n"
        f"r9lab-tag:material/tin\ttin\tskos:exactMatch\tt:t01\told\t{j}\n"
        f"r9lab-tag:material/wood\twood\tskos:exactMatch\tsssom:NoTermFound\twood\t{j}\n"
        f"r9lab-tag:material/zinc\tzinc\tskos:exactMatch\tmaterials:m0002\tferrous metal\t{j}\tmyid:simon\n"
        f"r9lab-tag:material/brass\tbrass\tskos:exactMatch\tmaterials:m0011\tbrass\t{j}\n"
        f"r9lab-tag:keyword/brass\tbrass\tskos:exactMatch\tmaterials:m0011\tbrass\t{j}\n"
    )
    assert checks.check_tag_mappings(schemes, path) == [
        "t.sssom.tsv: 'steel' is not lower case or appears twice",
        "t.sssom.tsv: 'Glass' is not lower case or appears twice",
        "t.sssom.tsv: 'Glass': unknown predicate skos:sameAs",
        "t.sssom.tsv: 'Glass': materials:m9999 is not a live concept",
        "t.sssom.tsv: 'pe': unknown predicate exact",
        "t.sssom.tsv: 'pe': justification 'by hand' is not a semapv term",
        "t.sssom.tsv: 'pe': prefix of exact is not in the curie_map",
        "t.sssom.tsv: 'pe': prefix of by hand is not in the curie_map",
        "t.sssom.tsv: 'pc abs': subject_id r9lab-tag:pc%20abs is not r9lab-tag: plus a field and the tag",
        "t.sssom.tsv: 'pc abs': prefix of components:c0001 is not in the curie_map",
        "t.sssom.tsv: 'pp': object_label 'PP' is not materials:m0023's label",
        "t.sssom.tsv: 'tin': t:t01 is not a live concept",
        "t.sssom.tsv: 'wood': object_label 'wood' is not sssom:NoTermFound's label",
        "t.sssom.tsv: 'zinc': prefix of myid:simon is not in the curie_map",
    ]


def test_check_tag_mappings_needs_its_columns(schemes: Schemes, tmp_path: Path):
    path = tmp_path / "t.sssom.tsv"
    path.write_text("subject_label\tobject_id\nsteel\tmaterials:m0002\n")
    assert checks.check_tag_mappings(schemes, path) == [
        "t.sssom.tsv: no subject_id, predicate_id, object_label, mapping_justification column"
    ]


def test_check_tag_mappings_reports_a_short_row(schemes: Schemes, tmp_path: Path):
    path = tmp_path / "t.sssom.tsv"
    path.write_text("\t".join(checks.TAG_COLUMNS) + "\nr9lab-tag:steel\tsteel\n")
    assert "t.sssom.tsv: 'steel': justification '' is not a semapv term" in checks.check_tag_mappings(schemes, path)


def test_check_codes_names_a_code_missing_from_the_pinned_source(schemes: Schemes):
    errors = checks.check_codes(schemes, {"cpc": {"411"}})
    assert "materials/m0002: cpc:411 is not in the pinned cpc source" not in errors
    assert "materials/m0003: cpc:41121 is not in the pinned cpc source" in errors


def test_check_codes_names_a_pmdco_id_missing_from_the_pinned_source():
    schemes = one({"t01": {"label": "a", "mappings": {"close": ["pmdco:PMD_0000001", "pmdco:PMD_0000852"]}}})
    errors = checks.check_codes(schemes, {"pmdco": {"PMD_0000852"}})
    assert errors == ["t/t01: pmdco:PMD_0000001 is not in the pinned pmdco source"]


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
        ({"t01": {"label": "a", "mappings": {"related": ["unu1:0303"]}}}, "unu1:0303 must be a broad mapping"),
        ({"t01": {"label": "a", "mappings": {"close": ["cpv:302131"]}}}, "cpv:302131 is not an 8-digit CPV code"),
        ({"t01": {"label": "a", "mappings": {"broad": ["weee6:0"]}}}, "weee6:0 is not a weee6 code"),
        ({"t01": {"label": "a", "mappings": {"broad": ["weee6:06"]}}}, "weee6:06 is not a weee6 code"),
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
        ({"t01": {"label": "a", "definition": " "}}, "definition must be non-empty text"),
        ({"t01": {"label": "a", "note": ["x"]}}, "note must be non-empty text"),
        ({"t01": {"label": "a", "example": []}}, "example must be non-empty text"),
        ({"t01": {"label": "a", "example": ["x", 3]}}, "example must be non-empty text"),
        ({"t01": {"label": "a", "source": "Ashby 2017", "definition": None}}, "source needs a definition"),
        ({"t01": {"label": "a", "examples": ["x"]}}, "unknown field 'examples'"),
        ({"t01": {}}, "t/t01: no label"),
        ({"t01": {"label": "a", "note": None}}, "t/t01: missing note"),
        ({"t01": {"label": "a", "related": ["t09"]}}, "related t09 does not exist"),
        ({"t01": {"label": "a", "deprecated": True, "replaced_by": ["t09"]}}, "replaced_by t09 does not exist"),
        ({"t01": {"label": "a", "mappings": {"close": ["t:t09"]}}}, "t:t09 does not exist"),
        ({"t01": {"label": "a", "related": ["t01"]}}, "related t01 is itself or above or below it"),
        (
            {"t01": {"label": "a"}, "t02": {"label": "b", "broader": ["t01"], "related": ["t01"]}},
            "t/t02: related t01 is itself or above or below it",
        ),
        (
            {"t01": {"label": "a", "related": ["t02"]}, "t02": {"label": "b", "broader": ["t01"]}},
            "t/t01: related t02 is itself or above or below it",
        ),
        ({101: {"label": "a"}}, "t/101: id must be"),
        (
            {
                "t01": {"label": "a", "mappings": {"narrow": ["t:t02"]}},
                "t02": {"label": "b", "deprecated": True, "replaced_by": ["t03"]},
                "t03": {"label": "c"},
            },
            "t:t02 is deprecated (replaced by t03)",
        ),
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
        ({"t01": {"label": True}}, "t/t01: label must be non-empty text"),  # YAML `label: on`
        ({"t01": {"label": 5}}, "t/t01: label must be non-empty text"),
        ({"t01": {"label": " "}}, "t/t01: label must be non-empty text"),
        ({"t01": {"label": "a", "broader": 5}}, "t/t01: broader must be a list of ids"),
        ({"t01": {"label": "a", "broader": "t02"}, "t02": {"label": "b"}}, "t/t01: broader must be a list of ids"),
        ({"t01": {"label": "a", "related": ["t02", 3]}, "t02": {"label": "b"}}, "t/t01: related must be a list of ids"),
        (
            {"t01": {"label": "a", "deprecated": True, "replaced_by": "t02"}, "t02": {"label": "b"}},
            "t/t01: replaced_by must be a list of ids",
        ),
        ({"t01": {"label": "a", "deprecated": "false"}}, "t/t01: deprecated must be true or false"),
        ({"scheme": {"title": None}}, "t: title must be non-empty text"),
        ({"scheme": {"title": 3}}, "t: title must be non-empty text"),
        ({"scheme": {"description": ""}}, "t: description must be non-empty text"),
        ({"scheme": {"slug": "tags"}}, "tags: slug 'tags' is reserved"),
        ({"scheme": {"slug": "terms"}}, "terms: slug 'terms' is reserved"),
    ],
)
def test_validate_catches(concepts: dict, message: str):
    # A row's "scheme" entry, never a concept id, sets the scheme's own fields.
    meta = concepts.get("scheme")
    errors = checks.validate(one({k: v for k, v in concepts.items() if k != "scheme"}, meta), VERSIONS)
    assert any(message in e for e in errors), errors


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
    assert checks.name_matches(schemes, lists) == [
        ("t", "t01", "bafu", "2025-v2", "^steel sheet", ["Steel sheet, uncoated, at plant"]),
        ("t", "t01", "bafu", "2026-v1", "^steel sheet", ["STEEL SHEET, zinc-coated"]),
        ("t", "t01", "bafu", "2026-v1", "^tin\\b", ["Tin, at regional storage"]),
    ]


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
    assert checks.validate(one(concepts), VERSIONS) == []


def test_an_id_in_a_scheme_without_a_letter_needs_any_letter():
    errors = checks.validate(one({"01": {"label": "a"}}, {"id_letter": None}), VERSIONS)
    assert any("id must be a letter plus 2-4 digits" in e for e in errors), errors
