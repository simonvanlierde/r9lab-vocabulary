"""Load the built SKOS graph into a running PyST and check that every statement comes back.

Usage: `python tests/pyst/round_trip.py dist/r9lab-vocabulary.ttl [--url http://127.0.0.1:8741]`.
`just pyst-round-trip` starts the PyST in `compose.yaml`, runs this and stops it. Exits 1 on a
statement lost or added, 2 when PyST refuses a write.

PyST takes no file: a scheme, each concept and the relationships are separate API calls,
in that order. Two PyST rules need a reshape on the way in, which the read back undoes:

- A scheme may not list `skos:hasTopConcept`; each top concept's `skos:topConceptOf` says it.
- An editorial note must be a resource with `rdf:value`, `dcterms:creator` and
  `dcterms:issued`. The YAML has no date or author per note, so the loader takes the scheme's
  creators and `dcterms:modified`. These two are PyST's, not the vocabulary's.

`skos:narrower` goes in as the `skos:broader` it mirrors, which PyST requires, and comes back
from the `skos:broader` read back. Only the schemes and concepts are compared: PyST has no
place for the `dcat:Dataset` node or the `skos:Collection`.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from rdflib import RDF, SKOS, BNode, Graph, Literal
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
    return 1 if lost or added else 0


if __name__ == "__main__":
    sys.exit(main())
