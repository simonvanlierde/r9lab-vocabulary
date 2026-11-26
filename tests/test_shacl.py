"""The SHACL shapes: skohub-shapes' SKOS rules and this vocabulary's own, on the real build and a broken graph."""

from datetime import date
from pathlib import Path

import pytest
import yaml
from pyshacl import validate
from rdflib import SH, Graph

from r9lab_vocabulary import scheme

ROOT = Path(__file__).resolve().parent.parent
OWN, SKOHUB = ROOT / "shapes" / "r9lab.shacl.ttl", ROOT / "shapes" / "skohub-skos.shacl.ttl"


@pytest.fixture(scope="module")
def shapes() -> Graph:
    return Graph().parse(OWN).parse(SKOHUB)


def _violations(data: Graph, shapes: Graph) -> set[str]:
    conforms, report, _ = validate(data, shacl_graph=shapes)
    assert isinstance(report, Graph)
    messages = {str(m) for m in report.objects(None, SH.resultMessage)}
    assert conforms == (not messages)
    return messages


@pytest.mark.parametrize("root", [ROOT, ROOT / "tests" / "fixtures" / "golden"])
def test_the_build_conforms(root: Path, shapes: Graph):
    citation = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
    g = scheme.to_graph(scheme.load(root / "vocabulary"), "1.0.0", citation=citation, modified=date(2026, 2, 1))
    assert _violations(g, shapes) == set()


def test_each_own_rule_catches_its_break(shapes: Graph):
    messages = _violations(Graph().parse(ROOT / "tests" / "fixtures" / "shacl-broken.ttl"), shapes)
    for expected in (
        "A concept has an English prefLabel.",
        "A concept is in a concept scheme.",
        "A mapping points at an IRI.",
        "A deprecated concept is replaced by a concept in use.",
        "A scheme names its creator by IRI.",
        "A scheme names its publisher by IRI.",
        "A scheme has a dct:created date.",
        "A scheme has a dct:modified date.",
        "A scheme has an English dct:title.",
        "A scheme has an owl:versionIRI.",
        "A scheme names its language by IRI.",
        "A scheme has a dcat:landingPage.",
    ):
        assert expected in messages, messages
