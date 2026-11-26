"""Write the vocabulary out as SKOS, SSSOM and label tables.

`to_graph` and `write` build the SKOS graph, `write_sssom` its SSSOM mapping set, and
`labels` and `write_labels` the label tables.

Every scheme, and the vocabulary as a whole (`BASE`, a `dcat:Dataset`), carries release
metadata (`About`): docs/decisions/0004-versioned-iris-and-scheme-dates.md says which, and why.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import yaml
from rdflib import DCAT, DCTERMS, OWL, RDF, SDO, SKOS, XSD, Graph, Literal, Namespace, URIRef

from r9lab_vocabulary.scheme import (
    BASE,
    CC0,
    CODE_ONLY,
    PREFIXES,
    RELATIONS,
    SOURCE,
    TEXT_FIELDS,
    Match,
    Scheme,
    ancestors,
    iri,
    mappings,
    texts,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date
    from pathlib import Path

LANG = "en"
LANGUAGE = URIRef("http://id.loc.gov/vocabulary/iso639-1/en")
TITLE = "R9lab reference vocabulary"
BIBO = Namespace("http://purl.org/ontology/bibo/")
# PyST accepts only draft, accepted and rejected; deprecation is owl:deprecated, so a deprecated concept stays accepted.
ACCEPTED = URIRef("http://purl.org/ontology/bibo/status/accepted")


@dataclass(frozen=True)
class About:
    """What every scheme says about its release: version, the authors' ORCID iDs, landing page, and build date.

    `orcids` and `landing` are what `pipeline.citation` reads from CITATION.cff, the first iD the
    publisher; `modified` is `dct:modified`. Without them those triples are left out.
    """

    version: str
    orcids: Sequence[str] = ()
    landing: str | None = None
    modified: date | None = None

    def describe(self, g: Graph, node: URIRef, title: str, created: date | None) -> None:
        """Type `node` as a schema.org term set and add its title, version, dates, creators and landing page."""
        g.add((node, RDF.type, SDO.DefinedTermSet))
        g.add((node, SDO.name, Literal(title, lang=LANG)))
        g.add((node, DCTERMS.title, Literal(title, lang=LANG)))
        g.add((node, OWL.versionInfo, Literal(self.version)))
        g.add((node, OWL.versionIRI, URIRef(f"{BASE}{self.version}/{str(node).removeprefix(BASE)}")))
        g.add((node, DCTERMS.language, LANGUAGE))
        for prop, value in ((DCTERMS.created, created), (DCTERMS.modified, self.modified)):
            if value is not None:
                g.add((node, prop, Literal(value)))
        for orcid in self.orcids:
            g.add((node, DCTERMS.creator, URIRef(orcid)))
        if self.orcids:
            g.add((node, DCTERMS.publisher, URIRef(self.orcids[0])))
        if self.landing:
            g.add((node, DCAT.landingPage, URIRef(self.landing)))


def to_graph(schemes: dict[str, Scheme], about: About) -> Graph:
    """The whole vocabulary as one SKOS graph, its schemes the parts of one `dcat:Dataset`, all described by `about`."""
    g = Graph()
    namespaces = (("skos", SKOS), ("dcterms", DCTERMS), ("dcat", DCAT), ("schema", SDO), ("owl", OWL), ("bibo", BIBO))
    for prefix, ns in namespaces:
        g.bind(prefix, ns)
    for slug, scheme in schemes.items():
        g.bind(f"r9-{slug}", Namespace(scheme.iri))
    # The code-only schemes and the whole are as old as the oldest scheme written here.
    created = min(filter(None, (s.meta.get("created") for s in schemes.values())), default=None)
    vocab = URIRef(BASE)
    g.add((vocab, RDF.type, DCAT.Dataset))
    g.add((vocab, DCTERMS.license, CC0))
    about.describe(g, vocab, TITLE, created)
    used_external: dict[str, set[str]] = {}
    for scheme in schemes.values():
        _add_scheme(g, scheme, schemes, about, used_external)
        g.add((vocab, DCTERMS.hasPart, URIRef(scheme.iri)))
    for prefix, codes in used_external.items():
        _add_code_only_scheme(g, prefix, codes, about, created)
        g.add((vocab, DCTERMS.hasPart, URIRef(PREFIXES[prefix])))
    return g


def _add_scheme(
    g: Graph, scheme: Scheme, schemes: dict[str, Scheme], about: About, used_external: dict[str, set[str]]
) -> None:
    s = URIRef(scheme.iri)
    g.add((s, RDF.type, SKOS.ConceptScheme))
    g.add((s, SKOS.prefLabel, Literal(scheme.meta["title"], lang=LANG)))
    g.add((s, BIBO.status, ACCEPTED))
    g.add((s, DCTERMS.license, CC0))
    if desc := scheme.meta.get("description"):
        g.add((s, DCTERMS.description, Literal(desc.strip(), lang=LANG)))
        g.add((s, SKOS.definition, Literal(desc.strip(), lang=LANG)))
    about.describe(g, s, scheme.meta["title"], scheme.meta.get("created"))
    collection = scheme.meta.get("collection")
    if collection:
        coll = URIRef(f"{scheme.iri}collection")
        g.add((coll, RDF.type, SKOS.Collection))
        g.add((coll, SKOS.prefLabel, Literal(collection, lang=LANG)))
    for cid, c in scheme.concepts.items():
        node = URIRef(scheme.iri + cid)
        _add_concept(g, node, c, scheme)
        if collection:
            g.add((coll, SKOS.member, node))
        for relation, prefix, local in mappings(c):
            g.add((node, RELATIONS[relation], iri(schemes, prefix, local)))
            if prefix in CODE_ONLY:
                used_external.setdefault(prefix, set()).add(local)


def _add_concept(g: Graph, node: URIRef, c: dict[str, Any], scheme: Scheme) -> None:
    s = URIRef(scheme.iri)
    g.add((node, RDF.type, SKOS.Concept))
    g.add((node, RDF.type, SDO.DefinedTerm))
    g.add((node, SKOS.inScheme, s))
    g.add((node, BIBO.status, ACCEPTED))
    g.add((node, SKOS.prefLabel, Literal(c["label"], lang=LANG)))
    for field, prop in TEXT_FIELDS.items():
        for text in texts(c, field):
            g.add((node, prop, Literal(text.strip(), lang=LANG)))
    if source := c.get(SOURCE, "").strip():
        g.add((node, DCTERMS.source, URIRef(source) if source.startswith(("http://", "https://")) else Literal(source)))
    if (notation := c.get("notation")) is not None:
        g.add((node, SKOS.notation, Literal(str(notation))))
    broader = c.get("broader") or []
    if not broader and not c.get("deprecated"):
        g.add((node, SKOS.topConceptOf, s))
        g.add((s, SKOS.hasTopConcept, node))
    for ref in broader:
        g.add((node, SKOS.broader, URIRef(scheme.iri + ref)))
        g.add((URIRef(scheme.iri + ref), SKOS.narrower, node))
    for ref in c.get("related") or []:
        g.add((node, SKOS.related, URIRef(scheme.iri + ref)))
    if c.get("deprecated"):
        g.add((node, OWL.deprecated, Literal("true", datatype=XSD.boolean)))
        for ref in c.get("replaced_by") or []:
            g.add((node, DCTERMS.isReplacedBy, URIRef(scheme.iri + ref)))


def _add_code_only_scheme(g: Graph, prefix: str, codes: set[str], about: About, created: date | None) -> None:
    s = URIRef(PREFIXES[prefix])
    g.add((s, RDF.type, SKOS.ConceptScheme))
    g.add((s, SKOS.prefLabel, Literal(CODE_ONLY[prefix], lang=LANG)))
    g.add((s, SKOS.definition, Literal(CODE_ONLY[prefix], lang=LANG)))
    g.add((s, BIBO.status, ACCEPTED))
    about.describe(g, s, CODE_ONLY[prefix], created)
    for code in sorted(codes):
        node = URIRef(PREFIXES[prefix] + code)
        g.add((node, RDF.type, SKOS.Concept))
        g.add((node, RDF.type, SDO.DefinedTerm))
        g.add((node, SKOS.inScheme, s))
        g.add((node, BIBO.status, ACCEPTED))
        g.add((node, SKOS.notation, Literal(code)))
        g.add((node, SKOS.prefLabel, Literal(code, lang=LANG)))


def write(schemes: dict[str, Scheme], about: About, out: Path, matches: list[Match]) -> list[Path]:
    """Write `r9lab-vocabulary.ttl`, `.jsonld` and `name-matches.csv` into `out`.

    `matches` is `checks.name_matches`: the CSV has one row per pattern and source (`bafu-2026-v1`) and its match count.
    """
    out.mkdir(parents=True, exist_ok=True)
    g = to_graph(schemes, about)
    ttl, jsonld, names = out / "r9lab-vocabulary.ttl", out / "r9lab-vocabulary.jsonld", out / "name-matches.csv"
    g.serialize(ttl, format="turtle")
    g.serialize(jsonld, format="json-ld", auto_compact=True)
    with names.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["concept", "label", "source", "pattern", "matches"])
        for slug, cid, family, ver, pattern, hits in matches:
            label = schemes[slug].concepts[cid]["label"]
            w.writerow([schemes[slug].iri + cid, label, f"{family}-{ver}", pattern, len(hits)])
    return [ttl, jsonld, names]


def write_sssom(schemes: dict[str, Scheme], about: About, out: Path) -> Path:
    """Write `r9lab-vocabulary.sssom.tsv` into `out`: one SSSOM row per `mappings` entry.

    Every row is a person's curation, so its justification is `semapv:ManualMappingCuration`
    and the publisher, `about`'s first ORCID iD, is its author. Mappings from or to a deprecated concept are
    left out: SSSOM has no field for a deprecated subject, and the SKOS graph keeps them.
    The YAML records no date per mapping, so there is no `mapping_date` column.
    """
    orcid = "https://orcid.org/"
    curie_map = {
        **PREFIXES,
        **{slug: s.iri for slug, s in schemes.items()},
        "orcid": orcid,
        "semapv": "https://w3id.org/semapv/vocab/",
        "skos": str(SKOS),
    }
    meta = {
        "curie_map": curie_map,
        "mapping_set_id": f"{BASE}r9lab-vocabulary.sssom.tsv",
        "mapping_set_version": about.version,
        "license": str(CC0),
    }
    author_id = f"orcid:{about.orcids[0].removeprefix(orcid)}"
    rows = sorted(
        (f"{slug}:{cid}", c["label"], f"skos:{RELATIONS[relation].fragment}", f"{prefix}:{local}")
        for slug, s in schemes.items()
        for cid, c in s.concepts.items()
        if not c.get("deprecated")
        for relation, prefix, local in mappings(c)
        if not (prefix in schemes and schemes[prefix].concepts[local].get("deprecated"))
    )
    path = out / "r9lab-vocabulary.sssom.tsv"
    out.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.writelines(f"#{line}\n" for line in yaml.safe_dump(meta, sort_keys=False).splitlines())
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["subject_id", "subject_label", "predicate_id", "object_id", "mapping_justification", "author_id"])
        w.writerows((*row, "semapv:ManualMappingCuration", author_id) for row in rows)
    return path


def _pilot_keys(schemes: dict[str, Scheme]) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    """Two maps of (slug, id) -> the keys of the collection members that map onto that concept.

    The first holds `exact` and `narrow` targets, whose descendants inherit the key; the second
    `close` targets, which carry it alone (SKOS closeMatch says nothing about the narrower
    concepts). A member's key is its notation, and a member carries its own key.
    """
    inherited: dict[tuple[str, str], set[str]] = {}
    own: dict[tuple[str, str], set[str]] = {}
    for slug, s in schemes.items():
        if not s.meta.get("collection"):
            continue
        for cid, c in s.concepts.items():
            if c.get("deprecated"):
                continue
            key = str(cid if c.get("notation") is None else c["notation"])
            inherited.setdefault((slug, cid), set()).add(key)
            for relation, prefix, local in mappings(c):
                target = {"exact": inherited, "narrow": inherited, "close": own}.get(relation)
                if target is not None and prefix in schemes:
                    target.setdefault((prefix, local), set()).add(key)
    return inherited, own


def labels(schemes: dict[str, Scheme]) -> list[dict[str, Any]]:
    """Per scheme, each live concept by id: IRI, label, path, definition, scope note, examples, pilot keys.

    The editorial note stays out: it is for curators, not prompts.

    The path follows the first `broader` only. `pilot` holds the key of each pilot class that
    maps onto the concept, or as `exact` or `narrow` onto any of its ancestors through every
    `broader` parent; a `close` mapping marks its target alone.
    """
    inherited, own = _pilot_keys(schemes)
    out = []
    for slug, s in schemes.items():
        concepts = []
        for cid in sorted(cid for cid, c in s.concepts.items() if not c.get("deprecated")):
            chain, node = [cid], s.concepts[cid]
            while node.get("broader"):
                chain.insert(0, node["broader"][0])
                node = s.concepts[chain[0]]
            c = s.concepts[cid]
            above = {cid, *ancestors(s, cid)}
            pilot = own.get((slug, cid), set()).union(*(inherited.get((slug, a), set()) for a in above))
            concepts.append(
                {
                    "id": cid,
                    "iri": s.iri + cid,
                    "label": c["label"],
                    "path": [s.concepts[a]["label"] for a in chain],
                    "definition": c["definition"].strip() if c.get("definition") else None,
                    "note": c["note"].strip() if c.get("note") else None,
                    "example": [e.strip() for e in texts(c, "example")],
                    "pilot": sorted(pilot),
                }
            )
        out.append({"slug": slug, "title": s.meta["title"], "iri": s.iri, "concepts": concepts})
    return out


def write_labels(schemes: dict[str, Scheme], version: str, out: Path) -> list[Path]:
    """Write `labels.json` and `labels.md` into `out`: `labels`, as data and as a table per scheme."""
    out.mkdir(parents=True, exist_ok=True)
    data = labels(schemes)
    json_path, md_path = out / "labels.json", out / "labels.md"
    json_path.write_text(
        json.dumps({"version": version, "schemes": data}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [f"# R9lab vocabulary labels {version}"]
    for s in data:
        lines += ["", f"## {s['title']}", "", "| id | label | path | definition | pilot |", "|---|---|---|---|---|"]
        for c in s["concepts"]:
            cells = (c["id"], c["label"], " > ".join(c["path"]), c["definition"] or "", ", ".join(c["pilot"]))
            lines.append("| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in cells) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [json_path, md_path]
