"""The SHACL shapes: skohub-shapes' SKOS rules and this vocabulary's own, on the real build and a broken graph."""

from datetime import date
from typing import TYPE_CHECKING

import pytest
from conftest import ROOT
from pyshacl import validate
from rdflib import DCTERMS, RDF, RDFS, SDO, SH, SKOS, Graph, URIRef

from r9lab_vocabulary import export, pipeline, scheme

if TYPE_CHECKING:
    from pathlib import Path

OWN, SKOHUB = ROOT / "shapes" / "r9lab.shacl.ttl", ROOT / "tests" / "fixtures" / "skohub-skos.shacl.ttl"


@pytest.fixture(scope="module")
def own() -> Graph:
    return Graph().parse(OWN)


@pytest.fixture(scope="module")
def skohub() -> Graph:
    graph = Graph().parse(SKOHUB)
    # SKOS S4 constrains the object of inScheme. The subject can be a collection.
    # https://www.w3.org/TR/skos-reference/#sec-inscheme
    shape = URIRef("http://skohub.io/skohub-shaclDisjointConceptSchemeAndCollection")
    graph.remove((shape, SH.targetSubjectsOf, SKOS.inScheme))
    return graph


@pytest.fixture(scope="module")
def shapes(own: Graph, skohub: Graph) -> Graph:
    return own + skohub


def _violations(data: Graph, shapes: Graph) -> set[str]:
    conforms, report, _ = validate(data, shacl_graph=shapes)
    assert isinstance(report, Graph)
    messages = {str(m) for m in report.objects(None, SH.resultMessage)}
    assert conforms == (not messages)
    return messages


@pytest.mark.parametrize("root", [ROOT, ROOT / "tests" / "fixtures" / "golden"])
def test_the_build_conforms(root: Path, own: Graph, skohub: Graph):
    authors, landing = pipeline.citation(root / "CITATION.cff")
    schemes = scheme.load(root / "vocabulary")
    g = export.to_graph(schemes, export.About("1.0.0", list(authors), landing, date(2026, 2, 1), authors))
    # skohub's S19/S20 rule wants every relatedMatch target typed in the graph. SKOS entails it
    # (relatedMatch is a sub-property of related, whose range is skos:Concept), and a target in an
    # outside scheme, such as a CPV code, is typed only in that scheme's own data. Add the entailed
    # type for the skohub run; the vocabulary's own shapes run on the graph as built.
    entailed = Graph() + g
    for target in set(g.objects(None, SKOS.relatedMatch)):
        entailed.add((target, RDF.type, SKOS.Concept))
    assert _violations(g, own) == set()
    assert _violations(entailed, skohub) == set()


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
        "A concept has one bibo:status PyST accepts.",
        "A concept scheme has one bibo:status PyST accepts.",
        "A concept scheme has a skos:definition.",
        "A concept scheme has exactly one owl:versionInfo.",
    ):
        assert expected in messages, messages


def test_the_build_describes_vocabulary_resources():
    authors, landing = pipeline.citation(ROOT / "CITATION.cff")
    g = export.to_graph(
        scheme.load(ROOT / "vocabulary"), export.About("test", list(authors), landing, author_names=authors)
    )
    for s in g.subjects(RDF.type, SKOS.ConceptScheme):
        assert g.value(s, SDO.codeRepository)
        assert g.value(s, SKOS.historyNote)
        for creator in g.objects(s, DCTERMS.creator):
            assert (creator, RDF.type, SDO.Person) in g
            assert g.value(creator, SDO.name)
    for node, source in g.subject_objects(DCTERMS.source):
        if isinstance(source, URIRef):
            assert str(g.value(node, SDO.citation)) == str(source)
    for kind in (SKOS.Concept, SKOS.Collection):
        for node in g.subjects(RDF.type, kind):
            parent = g.value(node, SKOS.inScheme)
            assert (node, RDFS.isDefinedBy, parent) in g
            assert g.value(node, SKOS.definition)
