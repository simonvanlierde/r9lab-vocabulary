"""The vocabulary's own content and how it loads, on the real files and on small broken copies."""

from typing import TYPE_CHECKING

import pytest
from conftest import ROOT, VERSIONS, Schemes
from rdflib import SKOS, URIRef
from yaml.constructor import ConstructorError

from r9lab_vocabulary import checks, export, scheme

if TYPE_CHECKING:
    from pathlib import Path


# The pilot's L1 keys: the ten frozen at registration (5 November 2026), plus motor_transformer.
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
    "motor_transformer",
}


def test_the_vocabulary_breaks_no_rule(schemes: Schemes):
    assert checks.validate(schemes, VERSIONS) == []


def test_the_pilot_collection_keeps_the_frozen_keys(schemes: Schemes):
    g = export.to_graph(schemes, export.About("test"))
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


def test_the_tag_mappings_break_no_rule(schemes: Schemes):
    assert checks.check_tag_mappings(schemes, ROOT / "mappings" / "r9lab-tags.sssom.tsv") == []


def test_a_repeated_concept_id_is_an_error_not_an_overwrite(tmp_path: Path):
    (tmp_path / "t.yaml").write_text("scheme: {slug: t, title: t}\nconcepts:\n  t01: {label: a}\n  t01: {label: b}\n")
    with pytest.raises(ConstructorError, match="repeated key t01"):
        scheme.load(tmp_path)


@pytest.mark.parametrize("slug", ["t", "wd"])
def test_a_scheme_slug_taken_by_another_scheme_or_prefix_is_an_error(tmp_path: Path, slug: str):
    (tmp_path / "a.yaml").write_text("scheme: {slug: t, title: a}\n")
    (tmp_path / "b.yaml").write_text(f"scheme: {{slug: {slug}, title: b}}\n")
    with pytest.raises(ValueError, match=rf"b\.yaml: scheme slug '{slug}' is already taken"):
        scheme.load(tmp_path)
