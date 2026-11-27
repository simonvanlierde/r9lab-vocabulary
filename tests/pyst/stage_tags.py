"""Stage a verified vocabulary release in a disposable loopback PyST.

Use stage to build and verify a snapshot. Use activate to switch a local manifest,
or to restore one saved earlier. No public endpoints are changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import quote, urlencode, urlsplit

import yaml
from rdflib import OWL, RDF, SKOS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.compare import to_isomorphic
from rdflib.exceptions import ParserError
from rdflib.namespace import DCTERMS
from round_trip import PySTRefusedError, call, compare, load, node_docs, read_back

from r9lab_vocabulary.checks import NO_TERM, TAG_COLUMNS, TAG_FIELDS, TAG_PREFIX
from r9lab_vocabulary.curate import ORCID
from r9lab_vocabulary.export import ACCEPTED, BIBO
from r9lab_vocabulary.scheme import BASE, RELATIONS

if TYPE_CHECKING:
    from collections.abc import Iterator

XKOS = Namespace("http://rdf-vocabulary.ddialliance.org/xkos#")
VIEW = Namespace(f"{BASE}pyst/")
TAG_ASSET_NAME = "r9lab-tags.sssom.tsv"
VERSION = re.compile(r"\d+\.\d+\.\d+")
SHA256 = re.compile(r"[0-9a-f]{64}")
PREDICATES = {f"skos:{iri.fragment}" for iri in RELATIONS.values()}


class StageError(Exception):
    """Assets or the staged graph failed verification."""


def fail(message: str) -> NoReturn:
    raise StageError(message)


@dataclass(frozen=True)
class Release:
    version: str
    graph_sha256: str
    tags_sha256: str
    tags_url: str

    @classmethod
    def parse(cls, manifest: object) -> Release:
        if not isinstance(manifest, dict):
            fail("release manifest must be a JSON object")
        for field in cls.__dataclass_fields__:
            if not isinstance(manifest.get(field), str):
                fail(f"release manifest requires a string {field}")
        release = cls(
            manifest["version"],
            manifest["graph_sha256"],
            manifest["tags_sha256"],
            manifest["tags_url"],
        )
        if not VERSION.fullmatch(release.version):
            fail("manifest version must be X.Y.Z")
        if not SHA256.fullmatch(release.graph_sha256) or not SHA256.fullmatch(release.tags_sha256):
            fail("both manifest checksums must be lowercase SHA-256 hex digests")
        url = urlsplit(release.tags_url)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
            or not url.path.endswith(f"/v{release.version}/{TAG_ASSET_NAME}")
        ):
            fail(f"tags_url must be an HTTPS asset URL for v{release.version}")
        return release


def checked_bytes(path: Path, digest: str) -> bytes:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        fail(f"SHA-256 mismatch for {path.name}")
    return data


def tag_iri(label: str) -> URIRef:
    digest = hashlib.sha256(label.strip().lower().encode()).hexdigest()
    return VIEW[f"strings/{digest}"]


def field_iri(field: str) -> URIRef:
    return VIEW[f"fields/{field}"]


def read_rows(tags: bytes, version: str) -> tuple[dict, csv.DictReader]:
    metadata, tsv = [], []
    for line in tags.decode("utf-8").splitlines(keepends=True):
        if line.startswith("#"):
            metadata.append(line[1:])
        else:
            tsv.append(line)
    meta = yaml.safe_load("".join(metadata))
    if not isinstance(meta, dict) or meta.get("mapping_set_version") != version:
        fail("SSSOM mapping_set_version disagrees with the manifest")
    prefixes = meta.get("curie_map")
    if not isinstance(prefixes, dict) or prefixes.get(TAG_PREFIX) != f"{BASE}tags/":
        fail("SSSOM curie_map requires the canonical r9lab-tag prefix")
    rows = csv.DictReader(StringIO("".join(tsv)), delimiter="\t", restval="", strict=True)
    required = (*TAG_COLUMNS, "reviewer_id")
    columns = rows.fieldnames or []
    if not set(required) <= set(columns) or len(set(columns)) != len(columns):
        fail("SSSOM tag mapping columns are missing or duplicated")
    return prefixes, rows


def release_schemes(graph: Graph, version: str) -> set[URIRef]:
    schemes = set()
    for scheme in graph.subjects(RDF.type, SKOS.ConceptScheme):
        if not isinstance(scheme, URIRef) or not str(scheme).startswith(BASE):
            fail("vocabulary graph contains a non-R9lab scheme")
        if set(graph.objects(scheme, OWL.versionInfo)) != {Literal(version)}:
            fail(f"vocabulary scheme version disagrees with the manifest: {scheme}")
        schemes.add(scheme)
    if not schemes:
        fail("vocabulary graph has no concept schemes")
    return schemes


def target_iris(graph: Graph, schemes: set[URIRef], prefixes: dict, row: dict, line: int) -> tuple[URIRef, URIRef]:
    prefix, _, code = row["object_id"].partition(":")
    scheme = URIRef(f"{BASE}{prefix}/")
    if not code or prefixes.get(prefix) != str(scheme) or scheme not in schemes:
        fail(f"SSSOM line {line} references an unknown target scheme")
    target = URIRef(f"{scheme}{code}")
    if (
        (target, RDF.type, SKOS.Concept) not in graph
        or set(graph.objects(target, SKOS.inScheme)) != {scheme}
        or (target, OWL.deprecated, Literal("true", datatype=XSD.boolean)) in graph
    ):
        fail(f"SSSOM line {line} target is missing or deprecated")
    if row["object_label"] not in {str(label) for label in graph.objects(target, SKOS.prefLabel)}:
        fail(f"SSSOM line {line} target label disagrees with the vocabulary")
    return scheme, target


def eligible_rows(
    graph: Graph, schemes: set[URIRef], tags: bytes, version: str
) -> Iterator[tuple[str, str, str, URIRef, URIRef]]:
    prefixes, rows = read_rows(tags, version)
    seen = set()
    for row in rows:
        subject = row["subject_id"]
        label = row["subject_label"]
        field, _, _ = subject.removeprefix(f"{TAG_PREFIX}:").partition("/")
        valid_id = f"{TAG_PREFIX}:{field}/{quote(label, safe='')}"
        if (
            not label
            or label != label.strip().lower()
            or field not in TAG_FIELDS
            or subject != valid_id
            or subject in seen
        ):
            fail(f"SSSOM line {rows.line_num} has a malformed or duplicate tag subject")
        seen.add(subject)
        if row["predicate_id"] not in PREDICATES or not row["mapping_justification"].startswith("semapv:"):
            fail(f"SSSOM line {rows.line_num} has an invalid mapping predicate or justification")
        reviewers = row["reviewer_id"]
        if reviewers and (
            prefixes.get("orcid") != "https://orcid.org/"
            or any(not ORCID.fullmatch(reviewer) for reviewer in reviewers.split("|"))
        ):
            fail(f"SSSOM line {rows.line_num} has an invalid reviewer_id")
        if row["object_id"] == NO_TERM:
            continue
        scheme, target = target_iris(graph, schemes, prefixes, row, rows.line_num)
        if reviewers:
            yield subject, label, field, scheme, target


def prepare(graph: Graph, tags: bytes, release: Release) -> Graph:
    """Validate the released rows and build their conditional association view."""
    schemes = release_schemes(graph, release.version)
    view = Graph()
    for subject, label, field, target_scheme, target in eligible_rows(graph, schemes, tags, release.version):
        tag = tag_iri(label)
        field_id = field_iri(field)
        slug = str(target_scheme).removeprefix(BASE).removesuffix("/")
        correspondence = VIEW[f"correspondences/{slug}"]
        subject_iri = f"{BASE}tags/{subject.split(':', 1)[1]}"
        association = URIRef(f"{correspondence}/{hashlib.sha256(subject_iri.encode()).hexdigest()}")
        view.add((tag, RDF.type, SKOS.Concept))
        view.add((tag, SKOS.prefLabel, Literal(label, lang="en")))
        view.add((tag, SKOS.inScheme, VIEW["strings/"]))
        view.add((tag, BIBO.status, ACCEPTED))
        view.add((correspondence, RDF.type, XKOS.Correspondence))
        for compared in (VIEW["strings/"], VIEW["fields/"], target_scheme):
            view.add((correspondence, XKOS.compares, compared))
        view.add((correspondence, DCTERMS.references, URIRef(release.tags_url)))
        view.add((correspondence, XKOS.madeOf, association))
        view.add((association, RDF.type, XKOS.ConceptAssociation))
        view.add((association, XKOS.sourceConcept, tag))
        view.add((association, XKOS.sourceConcept, field_id))
        view.add((association, XKOS.targetConcept, target))

    release_scheme = min(schemes)
    for node, label in [(VIEW["strings/"], "Tag strings"), (VIEW["fields/"], "Tag fields")]:
        view.add((node, RDF.type, SKOS.ConceptScheme))
        view.add((node, SKOS.prefLabel, Literal(label, lang="en")))
        view.add((node, SKOS.definition, Literal(f"R9lab {label.lower()}", lang="en")))
    for correspondence in view.subjects(RDF.type, XKOS.Correspondence):
        slug = str(correspondence).rsplit("/", 1)[1]
        view.add((correspondence, SKOS.prefLabel, Literal(f"Tag mappings to {slug}", lang="en")))
    for node in (VIEW["strings/"], VIEW["fields/"], *view.subjects(RDF.type, XKOS.Correspondence)):
        view.add((node, BIBO.status, ACCEPTED))
        view.add((node, OWL.versionInfo, Literal(release.version)))
        for predicate in (DCTERMS.creator, DCTERMS.created):
            for value in graph.objects(release_scheme, predicate):
                view.add((node, predicate, value))
    for field in TAG_FIELDS:
        node = field_iri(field)
        view.add((node, RDF.type, SKOS.Concept))
        view.add((node, SKOS.inScheme, VIEW["fields/"]))
        view.add((node, SKOS.prefLabel, Literal(field, lang="en")))
        view.add((node, BIBO.status, ACCEPTED))
    return view


def load_associations(view: Graph, base: str) -> None:
    docs = node_docs(view)
    for correspondence in view.subjects(RDF.type, XKOS.Correspondence):
        doc = docs[str(correspondence)].copy()
        members = doc.pop(str(XKOS.madeOf))
        call(base, "POST", "/api/v1/correspondences/", doc)
        for member in members:
            call(base, "POST", "/api/v1/associations/", docs[member["@id"]])
        call(base, "POST", "/api/v1/made_ofs/", {"@id": str(correspondence), str(XKOS.madeOf): members})


def lookup(base: str, tag: URIRef, field: URIRef, correspondences: list[str]) -> URIRef | None:
    """Resolve a full field-qualified tag, even if the API returns several fields."""
    matches = []
    for correspondence in correspondences:
        query = urlencode({"correspondence_iri": correspondence, "source_concept_iri": tag, "kind": "conditional"})
        records = call(base, "GET", f"/api/v1/associations/?{query}")
        if not isinstance(records, list):
            fail("PyST associations response must be a list")
        for record in records:
            sources = [node["@id"] for node in record[str(XKOS.sourceConcept)]]
            if sorted(sources) == sorted((str(tag), str(field))):
                targets = record[str(XKOS.targetConcept)]
                if len(targets) != 1:
                    fail("PyST conditional association must have one target")
                matches.append(URIRef(targets[0]["@id"]))
    if len(matches) > 1:
        fail("PyST returned multiple targets for one field-qualified tag")
    return matches[0] if matches else None


def read_associations(base: str) -> tuple[Graph, list[dict], list[dict]]:
    correspondences = call(base, "GET", "/api/v1/correspondences/")
    associations = call(base, "GET", "/api/v1/associations/")
    if not isinstance(correspondences, list) or not isinstance(associations, list):
        fail("PyST correspondence and association responses must be lists")
    graph = Graph().parse(data=json.dumps([*correspondences, *associations]), format="json-ld")
    return graph, correspondences, associations


def fingerprint(vocabulary: Graph, associations: Graph, release: Release, endpoint: str) -> str:
    record = {
        "graph_digest": f"{to_isomorphic(vocabulary + associations).graph_digest():x}",
        "release": asdict(release),
        "endpoint": endpoint,
    }
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def stage(graph: Graph, view: Graph, release: Release, base: str) -> dict[str, object]:
    for resource in ("concept_schemes", "concepts", "correspondences", "associations"):
        if call(base, "GET", f"/api/v1/{resource}/") != []:
            fail("staging requires an empty PyST snapshot")
    combined = graph + view
    load(combined, base)
    load_associations(view, base)
    vocabulary = read_back(base)
    if any(compare(combined, vocabulary)):
        fail("staged PyST vocabulary differs from the release")
    actual, correspondences, associations = read_associations(base)
    expected = {
        triple
        for cls in (XKOS.Correspondence, XKOS.ConceptAssociation)
        for iri in view.subjects(RDF.type, cls)
        for triple in view.triples((iri, None, None))
    }
    # PyST can add bookkeeping statements such as dcterms:modified.
    predicates = {predicate for _, predicate, _ in expected}
    if expected != {triple for triple in actual if triple[1] in predicates} or (
        len(associations) != len(set(view.subjects(RDF.type, XKOS.ConceptAssociation)))
        or len(correspondences) != len(set(view.subjects(RDF.type, XKOS.Correspondence)))
    ):
        fail("staged PyST associations or membership differ from the release")

    correspondence_ids = sorted(record["@id"] for record in correspondences)
    for tag in view.subjects(SKOS.inScheme, VIEW["strings/"]):
        for field in TAG_FIELDS:
            field_id = field_iri(field)
            expected_targets = [
                view.value(association, XKOS.targetConcept)
                for association in view.subjects(XKOS.sourceConcept, tag)
                if (association, XKOS.sourceConcept, field_id) in view
            ]
            expected_target = expected_targets[0] if expected_targets else None
            if not isinstance(tag, URIRef) or lookup(base, tag, field_id, correspondence_ids) != expected_target:
                fail("staged PyST field-qualified lookup differs from the release")
    return {
        "association_count": len(associations),
        "correspondences": correspondence_ids,
        "snapshot_fingerprint": fingerprint(vocabulary, actual, release, base),
    }


def loopback(value: str) -> str:
    url = urlsplit(value)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.port is None or url.netloc != f"127.0.0.1:{url.port}":
        msg = "use an HTTP endpoint on 127.0.0.1 with an explicit port"
        raise argparse.ArgumentTypeError(msg)
    if url.path not in {"", "/"} or url.query or url.fragment:
        msg = "use the PyST base URL"
        raise argparse.ArgumentTypeError(msg)
    return value.rstrip("/")


def write_manifest(path: Path, data: dict, *, replace: bool) -> None:
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if replace:
            temporary.replace(path)
        else:
            path.hardlink_to(temporary)
    finally:
        temporary.unlink(missing_ok=True)


def activate_snapshot(staged_manifest: Path, active_manifest: Path) -> None:
    data = json.loads(staged_manifest.read_text(encoding="utf-8"))
    release = Release.parse(data)
    if not isinstance(data.get("endpoint"), str) or not isinstance(data.get("snapshot_fingerprint"), str):
        fail("activation requires a manifest from a successful stage")
    endpoint = loopback(data["endpoint"])
    associations, correspondences, records = read_associations(endpoint)
    if (
        fingerprint(read_back(endpoint), associations, release, endpoint) != data["snapshot_fingerprint"]
        or sorted(record["@id"] for record in correspondences) != data.get("correspondences")
        or len(records) != data.get("association_count")
    ):
        fail("snapshot endpoint no longer matches the staged manifest")
    write_manifest(active_manifest, data, replace=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Exit 1 on failed verification, 2 for invalid arguments, 3 on an I/O or PyST error.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stage_parser = commands.add_parser("stage", help="verify release files and stage a snapshot")
    stage_parser.add_argument("graph", type=Path, help="release vocabulary Turtle")
    stage_parser.add_argument("tags", type=Path, help="release tag SSSOM TSV")
    stage_parser.add_argument(
        "release_manifest", type=Path, help="JSON with version, graph_sha256, tags_sha256 and tags_url"
    )
    stage_parser.add_argument("staged_manifest", type=Path, help="new output snapshot manifest")
    stage_parser.add_argument("--url", required=True, type=loopback, help="empty local PyST endpoint")
    activate = commands.add_parser("activate", help="atomically switch or restore the local snapshot manifest")
    activate.add_argument("staged_manifest", type=Path)
    activate.add_argument("active_manifest", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "stage":
            if args.staged_manifest.exists():
                fail("staged manifest already exists")
            release = Release.parse(json.loads(args.release_manifest.read_text(encoding="utf-8")))
            graph = Graph().parse(data=checked_bytes(args.graph, release.graph_sha256), format="turtle")
            view = prepare(graph, checked_bytes(args.tags, release.tags_sha256), release)
            result = stage(graph, view, release, args.url)
            write_manifest(
                args.staged_manifest,
                asdict(release) | result | {"endpoint": args.url},
                replace=False,
            )
        else:
            activate_snapshot(args.staged_manifest, args.active_manifest)
    except (
        StageError,
        ValueError,
        SyntaxError,
        argparse.ArgumentTypeError,
        csv.Error,
        ParserError,
        yaml.YAMLError,
    ) as error:
        sys.stderr.write(f"error: {str(error)!r}\n")
        return 1
    except (OSError, PySTRefusedError) as error:
        sys.stderr.write(f"error: {str(error)!r}\n")
        return 3
    sys.stdout.write(f"{args.staged_manifest if args.command == 'stage' else args.active_manifest}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
