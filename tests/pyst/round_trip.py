"""Load the built SKOS graph into a running PyST and check that every statement comes back.

Usage: `python tests/pyst/round_trip.py dist/r9lab-vocabulary.ttl [--url http://127.0.0.1:8741]`.
`just pyst-round-trip` starts the PyST in `compose.yaml`, runs this and stops it. Exits 1 on a
round-trip mismatch, 2 when PyST refuses a write.

PyST takes no file: a scheme, each concept and the relationships are separate API calls,
in that order. Two PyST rules need a reshape on the way in, which the read back undoes:

- A scheme may not list `skos:hasTopConcept`; each top concept's `skos:topConceptOf` says it.
- An editorial note must be a resource with `rdf:value`, `dcterms:creator` and
  `dcterms:issued`. The YAML has no date or author per note, so the loader takes the scheme's
  creators and `dcterms:modified`. These two are PyST's, not the vocabulary's.

`skos:narrower` goes in as the `skos:broader` it mirrors, which PyST requires, and comes back
from the `skos:broader` read back. Only the schemes and concepts are compared: PyST has no
place for the `dcat:Dataset` node or the `skos:Collection`. A separate probe checks
conditional XKOS associations and their correspondence links.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from rdflib import RDF, SKOS, BNode, Graph, Literal, Namespace
from rdflib.namespace import DCTERMS

TOKEN = "round-trip"  # noqa: S105 -- PyST_auth_token of the throwaway PyST in compose.yaml
RELATIONS = [SKOS[p] for p in ("broader", "exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch")]


class PySTRefusedError(Exception):
    pass


def call(base: str, method: str, path: str, body: object = None) -> object:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "X-PyST-Auth-Token": TOKEN}
    req = urllib.request.Request(base + path, data, headers, method=method)  # noqa: S310 -- base is --url
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.load(resp)
    except urllib.error.HTTPError as err:
        msg = f"{method} {path}: {err.code} {err.read().decode()[:2000]}"
        raise PySTRefusedError(msg) from err


def node_docs(g: Graph) -> dict[str, dict]:
    """Each node as PyST reads it: expanded JSON-LD, one object per subject."""
    return {d["@id"]: d for d in json.loads(g.serialize(format="json-ld"))}


def load(g: Graph, base: str) -> None:
    docs = node_docs(g)
    schemes = sorted(g.subjects(RDF.type, SKOS.ConceptScheme), key=str)
    for scheme in schemes:
        doc = docs[str(scheme)]
        doc.pop(str(SKOS.hasTopConcept), None)
        call(base, "POST", "/api/v1/concept_schemes/", doc)

    skip = {str(SKOS.narrower), *map(str, RELATIONS)}
    for concept in sorted(g.subjects(RDF.type, SKOS.Concept), key=str):
        doc = {k: v for k, v in docs[str(concept)].items() if k not in skip}
        scheme = docs[str(g.value(concept, SKOS.inScheme))]
        # PyST refuses a notation equal to a prefLabel. It is left out, so the check reports it lost.
        labels = {label["@value"] for label in doc[str(SKOS.prefLabel)]}
        notations = [n for n in doc.pop(str(SKOS.notation), []) if n["@value"] not in labels]
        if notations:
            doc[str(SKOS.notation)] = notations
        if notes := doc.get(str(SKOS.editorialNote)):
            doc[str(SKOS.editorialNote)] = [
                {
                    str(RDF.value): [note],
                    str(DCTERMS.creator): scheme[str(DCTERMS.creator)],
                    str(DCTERMS.issued): scheme[str(DCTERMS.modified)],
                }
                for note in notes
            ]
        call(base, "POST", "/api/v1/concepts/", doc)

    # One relationship per object: PyST refuses an object holding two.
    rels = {(s, p, o) for p in RELATIONS for s, o in g.subject_objects(p)}
    rels |= {(o, SKOS.broader, s) for s, o in g.subject_objects(SKOS.narrower)}
    body = [{"@id": str(s), str(p): [{"@id": str(o)}]} for s, p, o in sorted(rels)]
    if body:
        call(base, "POST", "/api/v1/relationships/", body)


def read_back(base: str) -> Graph:
    docs = call(base, "GET", "/api/v1/concept_schemes/")
    assert isinstance(docs, list)
    for scheme in [d["@id"] for d in docs]:
        q = urllib.parse.urlencode({"concept_scheme_iri": scheme})
        concepts = call(base, "GET", f"/api/v1/concepts/?{q}")
        assert isinstance(concepts, list)
        docs += concepts
        for concept in concepts:
            q = urllib.parse.urlencode({"iri": concept["@id"]})
            rels = call(base, "GET", f"/api/v1/relationships/?{q}")
            assert isinstance(rels, list)
            docs += rels
    back = Graph().parse(data=json.dumps(docs), format="json-ld")

    for s, note in list(back.subject_objects(SKOS.editorialNote)):
        if isinstance(note, BNode):
            back.remove((s, SKOS.editorialNote, note))
            for value in back.objects(note, RDF.value):
                back.add((s, SKOS.editorialNote, value))
            back.remove((note, None, None))
    for s, o in list(back.subject_objects(SKOS.broader)):
        back.add((o, SKOS.narrower, s))
    for s, o in list(back.subject_objects(SKOS.topConceptOf)):
        back.add((o, SKOS.hasTopConcept, s))
    return back


def check_conditional_associations(base: str) -> bool:
    xkos = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")
    fixture = Graph().parse(
        format="turtle",
        data="""
        @prefix : <https://example.org/r9lab-pyst-test/> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix xkos: <http://rdf-vocabulary.ddialliance.org/xkos#> .
        @prefix dct: <http://purl.org/dc/terms/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix bibo: <http://purl.org/ontology/bibo/> .
        @prefix status: <http://purl.org/ontology/bibo/status/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        :tags a skos:ConceptScheme ; skos:prefLabel "Tags"@en ; skos:definition "Tag strings"@en ;
            bibo:status status:accepted ; dct:creator :creator ;
            dct:created "2026-11-28T00:00:00Z"^^xsd:dateTime ; owl:versionInfo "0.1.0" .
        :fields a skos:ConceptScheme ; skos:prefLabel "Fields"@en ; skos:definition "Tag fields"@en ;
            bibo:status status:accepted ; dct:creator :creator ;
            dct:created "2026-11-28T00:00:00Z"^^xsd:dateTime ; owl:versionInfo "0.1.0" .
        :targets a skos:ConceptScheme ; skos:prefLabel "Targets"@en ; skos:definition "Tag targets"@en ;
            bibo:status status:accepted ; dct:creator :creator ;
            dct:created "2026-11-28T00:00:00Z"^^xsd:dateTime ; owl:versionInfo "0.1.0" .
        :pc a skos:Concept ; skos:inScheme :tags ; skos:prefLabel "pc"@en ;
            bibo:status status:accepted .
        :material a skos:Concept ; skos:inScheme :fields ; skos:prefLabel "material"@en ;
            bibo:status status:accepted .
        :keyword a skos:Concept ; skos:inScheme :fields ; skos:prefLabel "keyword"@en ;
            bibo:status status:accepted .
        :polycarbonate a skos:Concept ; skos:inScheme :targets ; skos:prefLabel "polycarbonate"@en ;
            bibo:status status:accepted .
        :computer a skos:Concept ; skos:inScheme :targets ; skos:prefLabel "personal computer"@en ;
            bibo:status status:accepted .

        :correspondence a xkos:Correspondence ; skos:prefLabel "Tag mappings"@en ;
            xkos:compares :tags, :fields, :targets ; dct:references :r9lab-tags.sssom.tsv ;
            bibo:status status:accepted ; dct:creator :creator ;
            dct:created "2026-11-28T00:00:00Z"^^xsd:dateTime ; owl:versionInfo "0.1.0" .
        :material-pc a xkos:ConceptAssociation ; xkos:sourceConcept :pc, :material ;
            xkos:targetConcept :polycarbonate .
        :keyword-pc a xkos:ConceptAssociation ; xkos:sourceConcept :pc, :keyword ;
            xkos:targetConcept :computer .
        """,
    )
    load(fixture, base)
    docs = node_docs(fixture)
    correspondence = next(fixture.subjects(RDF.type, xkos.Correspondence))
    call(base, "POST", "/api/v1/correspondences/", docs[str(correspondence)])
    associations = list(fixture.subjects(RDF.type, xkos.ConceptAssociation))
    for association in associations:
        call(base, "POST", "/api/v1/associations/", docs[str(association)])

    members = [{"@id": str(association)} for association in associations]
    call(base, "POST", "/api/v1/made_ofs/", {"@id": str(correspondence), str(xkos.madeOf): members})
    query = urllib.parse.urlencode(
        {
            "correspondence_iri": str(correspondence),
            "source_concept_iri": "https://example.org/r9lab-pyst-test/pc",
            "kind": "conditional",
        }
    )
    results = call(base, "GET", f"/api/v1/associations/?{query}")
    assert isinstance(results, list)
    linked = call(base, "GET", f"/api/v1/correspondences/{correspondence}")
    back = Graph().parse(format="json-ld", data=json.dumps([linked, *results]))
    predicates = (xkos.compares, xkos.madeOf, xkos.sourceConcept, xkos.targetConcept, DCTERMS.references)
    wanted = {row for row in fixture if row[1] in predicates}
    wanted.update((correspondence, xkos.madeOf, association) for association in associations)
    received = {row for row in back if row[1] in predicates}
    if wanted != received or len(results) != len(associations):
        for label, rows in (("lost", wanted - received), ("added", received - wanted)):
            for subject, predicate, target in sorted(rows):
                sys.stderr.write(f"{label}: <{subject}> <{predicate}> {target}\n")
        sys.stderr.write("Conditional tag associations did not round-trip\n")
        return False
    return True


def compare(g: Graph, back: Graph) -> tuple[set, set]:
    """The statements about schemes and concepts lost and added on the way through PyST."""
    subjects = set(g.subjects(RDF.type, SKOS.ConceptScheme)) | set(g.subjects(RDF.type, SKOS.Concept))

    def about(graph: Graph) -> set:
        return {(s, p, norm(o)) for s, p, o in graph if s in subjects}

    sent, got = about(g), about(back)
    return sent - got, got - sent


def norm(o: object) -> object:
    """A literal by its value, so a re-serialized date or a default text direction is no loss."""
    if isinstance(o, Literal):
        return (str(o.toPython()), o.language, o.datatype)
    return o


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("graph", help="the built Turtle or JSON-LD, such as dist/r9lab-vocabulary.ttl")
    parser.add_argument("--url", default="http://127.0.0.1:8741", help="PyST's base URL")
    args = parser.parse_args()

    g = Graph().parse(args.graph)
    for _ in range(60):  # PyST takes a few seconds to start once its container is up
        try:
            call(args.url, "GET", "/api/v1/status/")
            break
        except OSError:
            time.sleep(1)
    try:
        load(g, args.url)
        back = read_back(args.url)
    except PySTRefusedError as err:
        sys.stderr.write(f"PyST refused: {err}\n")
        return 2

    lost, added = compare(g, back)
    for label, rows in (("lost", lost), ("added", added)):
        for s, p, o in sorted(rows, key=str):
            sys.stderr.write(f"{label}: <{s}> <{p}> {o}\n")
    schemes = len(set(back.subjects(RDF.type, SKOS.ConceptScheme)))
    concepts = len(set(back.subjects(RDF.type, SKOS.Concept)))
    kept = len(compare(g, Graph())[0]) - len(lost)
    sys.stdout.write(
        f"{schemes} schemes, {concepts} concepts, {kept} statements back; {len(lost)} lost, {len(added)} added\n"
    )
    if lost or added:
        return 1
    try:
        if not check_conditional_associations(args.url):
            return 1
    except PySTRefusedError as err:
        sys.stderr.write(f"PyST refused: {err}\n")
        return 2
    sys.stdout.write("2 conditional tag associations and their correspondence back\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
