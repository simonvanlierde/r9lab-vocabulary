"""Load the YAML vocabulary, check it, and write it as SKOS.

Each file in `vocabulary/` is one concept scheme. Concept ids are opaque and never
reused: a concept that goes away is marked `deprecated`, never deleted. A mapping is a
CURIE whose prefix names either an outside scheme (`PREFIXES`) or another scheme of
this vocabulary (its `slug`).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import yaml
from rdflib import DCTERMS, OWL, RDF, SKOS, XSD, Graph, Literal, Namespace, URIRef
from yaml.constructor import ConstructorError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

# NOTE: w3id.org/r9lab is not registered yet; the redirect is a PR to perma-id/w3id.org.
BASE = "https://w3id.org/r9lab/vocabulary/"

PREFIXES = {
    "cpc": "https://vocab.sentier.dev/products/cpc/2.1/CPCv2.1/",
    "wd": "http://www.wikidata.org/entity/",
    "pmdco": "https://w3id.org/pmd/co/",
    # Code-only schemes minted here: the UNU-KEY names are CC BY-NC-SA, so only codes are kept.
    "unu1": f"{BASE}external/unu-key-v1/",
    "r9lab-cpv": f"{BASE}external/r9lab-cpv/",
}
CODE_ONLY = {
    "unu1": "UNU-KEY v1 codes (codes only; names under CC BY-NC-SA 3.0 IGO are not copied)",
    "r9lab-cpv": "CPV codes as stored by R9lab (codes only, truncated as in the app)",
}
RELATIONS = {
    "exact": SKOS.exactMatch,
    "close": SKOS.closeMatch,
    "broad": SKOS.broadMatch,
    "narrow": SKOS.narrowMatch,
    "related": SKOS.relatedMatch,
}
ID = re.compile(r"^[a-z][0-9]{2,4}$")
# BAFU marks a withdrawn dataset by prefixing its name with "xx" or "xxx"; patterns skip them.
OBSOLETE = re.compile(r"^xx", re.IGNORECASE)
LANG = "en"


@dataclass(frozen=True)
class Scheme:
    """One YAML file: the scheme's metadata and its concepts keyed by id."""

    slug: str
    meta: dict[str, Any]
    concepts: dict[str, dict[str, Any]]

    @property
    def iri(self) -> str:
        """The scheme's IRI; each concept's IRI is this plus its id."""
        return f"{BASE}{self.slug}/"


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses a repeated mapping key, which PyYAML would let overwrite the first."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:  # noqa: FBT001, FBT002
        keys = [self.construct_object(k, deep=deep) for k, _ in node.value]
        if dupes := sorted({str(k) for k in keys if keys.count(k) > 1}):
            raise ConstructorError(None, None, f"repeated key {', '.join(dupes)}", node.start_mark)
        return super().construct_mapping(node, deep=deep)


def load(directory: Path) -> dict[str, Scheme]:
    """Every `*.yaml` scheme in `directory`, keyed by slug. A repeated key in a file is an error."""
    schemes = {}
    for path in sorted(directory.glob("*.yaml")):
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
        slug = doc["scheme"]["slug"]
        if slug in schemes or slug in PREFIXES:
            msg = f"{path.name}: scheme slug {slug!r} is already taken"
            raise ValueError(msg)
        schemes[slug] = Scheme(slug, doc["scheme"], doc.get("concepts") or {})
    return schemes


def mappings(concept: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    """(relation, prefix, local) for each mapping of a concept."""
    for relation, curies in (concept.get("mappings") or {}).items():
        for curie in curies:
            prefix, _, local = str(curie).partition(":")
            yield relation, prefix, local


def validate(schemes: dict[str, Scheme], releases: set[str]) -> list[str]:
    """Every rule the vocabulary breaks, as `scheme/id: message`; empty when it is sound.

    `releases` are the BAFU releases a scoped `bafu` pattern may name.
    """
    errors: list[str] = []
    for scheme in schemes.values():
        errors += _validate_scheme(scheme, schemes, releases)
    return errors


def _validate_scheme(scheme: Scheme, schemes: dict[str, Scheme], releases: set[str]) -> list[str]:
    errors = []
    letter = scheme.meta.get("id_letter")
    for cid, c in scheme.concepts.items():
        where = f"{scheme.slug}/{cid}"
        if not ID.match(cid) or (letter and not cid.startswith(letter)):
            errors.append(f"{where}: id must be {letter or 'a letter'} plus 2-4 digits")
        if not c.get("label"):
            errors.append(f"{where}: no label")
        errors += _validate_links(where, c, scheme)
        errors += _validate_mappings(where, c, schemes)
        errors += _validate_patterns(where, c, releases)
    errors += _duplicates(
        scheme, "label", lambda c: None if c.get("deprecated") else str(c.get("label", "")).casefold()
    )
    errors += _duplicates(scheme, "notation", lambda c: c.get("notation"))
    errors += _cycles(scheme)
    return errors


def _duplicates(scheme: Scheme, field: str, key: Callable[[dict[str, Any]], Any]) -> list[str]:
    errors, seen = [], {}
    for cid, c in scheme.concepts.items():
        k = key(c)
        if k is None or k == "":
            continue
        if k in seen:
            errors.append(f"{scheme.slug}/{cid}: {field} {c[field]!r} is also {seen[k]}'s")
        seen[k] = cid
    return errors


def _validate_links(where: str, c: dict[str, Any], scheme: Scheme) -> list[str]:
    errors = []
    for field in ("broader", "related"):
        for ref in c.get(field) or []:
            target = scheme.concepts.get(ref)
            if target is None:
                errors.append(f"{where}: {field} {ref} does not exist")
            elif target.get("deprecated") and not c.get("deprecated"):
                errors.append(f"{where}: {field} {ref} is deprecated")
    if not c.get("deprecated") and c.get("replaced_by"):
        errors.append(f"{where}: replaced_by needs deprecated: true")
    errors.extend(
        f"{where}: replaced_by {ref} does not exist" for ref in c.get("replaced_by") or [] if ref not in scheme.concepts
    )
    return errors


def bafu_patterns(c: dict[str, Any]) -> list[tuple[str, list[str] | None]]:
    """(pattern, releases) for each `bafu` entry; releases is None for one that applies to every release.

    An entry is a pattern string, or `{pattern: ..., releases: [2026-v1, ...]}` for a name
    that only some releases use.
    """
    out: list[tuple[str, list[str] | None]] = []
    for entry in c.get("bafu") or []:
        if isinstance(entry, dict):
            out.append((str(entry.get("pattern", "")), [str(r) for r in entry.get("releases") or []]))
        else:
            out.append((str(entry), None))
    return out


def _bad_bafu_entry(entry: object) -> bool:
    if isinstance(entry, dict):
        scoped = entry.get("releases")
        return (
            set(entry) != {"pattern", "releases"}
            or _bad_bafu_entry(entry["pattern"])
            or not isinstance(scoped, list)
            or not scoped
            or not all(isinstance(r, str) for r in scoped)
        )
    return not isinstance(entry, str) or not entry.strip()


def _validate_patterns(where: str, c: dict[str, Any], releases: set[str]) -> list[str]:
    entries = c.get("bafu") or []
    if not isinstance(entries, list):
        return [f"{where}: bafu must be a list of patterns"]
    errors = [
        f"{where}: bafu entry {entry!r} must be a non-empty pattern or exactly a pattern and a non-empty releases list"
        for entry in entries
        if _bad_bafu_entry(entry)
    ]
    if errors:
        return errors
    for pattern, scoped in bafu_patterns(c):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"{where}: bafu pattern {pattern!r}: {e}")
        errors.extend(
            f"{where}: bafu pattern {pattern!r} names unknown release {r!r}" for r in scoped or [] if r not in releases
        )
    return errors


def bafu_matches(schemes: dict[str, Scheme], names: dict[str, list[str]]) -> list[tuple[str, str, str, str, list[str]]]:
    """(scheme, id, release, pattern, matched names) for each pattern and each release in `names` it applies to.

    A pattern matches a name by case-insensitive search, over live activities only.
    Deprecated concepts are skipped. Call it on a vocabulary `validate` passed.
    """
    live = {release: [n for n in names[release] if not OBSOLETE.match(n)] for release in sorted(names)}
    return [
        (scheme.slug, cid, release, pattern, [n for n in ns if re.search(pattern, n, re.IGNORECASE)])
        for scheme in schemes.values()
        for cid, c in scheme.concepts.items()
        if not c.get("deprecated")
        for pattern, scoped in bafu_patterns(c)
        for release, ns in live.items()
        if scoped is None or release in scoped
    ]


def _validate_mappings(where: str, c: dict[str, Any], schemes: dict[str, Scheme]) -> list[str]:
    raw = c.get("mappings") or {}
    if not isinstance(raw, dict) or not all(isinstance(v, list) for v in raw.values()):
        return [f"{where}: mappings must map each relation to a list of CURIEs"]
    errors = []
    relation_of: dict[str, str] = {}
    for relation, prefix, local in mappings(c):
        curie = f"{prefix}:{local}"
        if relation not in RELATIONS:
            errors.append(f"{where}: unknown mapping relation {relation!r}")
        if prefix in schemes:
            if local not in schemes[prefix].concepts:
                errors.append(f"{where}: {curie} does not exist")
        elif prefix not in PREFIXES:
            errors.append(f"{where}: unknown prefix in {curie}")
        # SKOS integrity: exactMatch is disjoint with the hierarchical and associative matches.
        if curie in relation_of and relation_of[curie] != relation:
            errors.append(f"{where}: {curie} is both {relation_of[curie]} and {relation}")
        relation_of[curie] = relation
    return errors


def _cycles(scheme: Scheme) -> list[str]:
    errors = []
    for start in scheme.concepts:
        stack, seen = list(scheme.concepts[start].get("broader") or []), set()
        while stack:
            node = stack.pop()
            if node == start:
                errors.append(f"{scheme.slug}/{start}: broader chain loops back to itself")
                break
            if node in seen or node not in scheme.concepts:
                continue
            seen.add(node)
            stack += scheme.concepts[node].get("broader") or []
    return errors


def check_codes(schemes: dict[str, Scheme], known: dict[str, set[str]]) -> list[str]:
    """Mappings to an outside scheme whose code is not in that scheme's pinned source.

    `known` maps a prefix to its valid local codes; prefixes without an entry are not checked.
    """
    return [
        f"{scheme.slug}/{cid}: {prefix}:{local} is not in the pinned {prefix} source"
        for scheme in schemes.values()
        for cid, c in scheme.concepts.items()
        for _, prefix, local in mappings(c)
        if prefix in known and local not in known[prefix]
    ]


def iri(schemes: dict[str, Scheme], prefix: str, local: str) -> URIRef:
    """The IRI a CURIE stands for."""
    base = schemes[prefix].iri if prefix in schemes else PREFIXES[prefix]
    return URIRef(base + local)


def to_graph(schemes: dict[str, Scheme], version: str) -> Graph:
    """The whole vocabulary as one SKOS graph."""
    g = Graph()
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    for slug, scheme in schemes.items():
        g.bind(f"r9-{slug}", Namespace(scheme.iri))
    used_external: dict[str, set[str]] = {}
    for scheme in schemes.values():
        _add_scheme(g, scheme, schemes, version, used_external)
    for prefix, codes in used_external.items():
        _add_code_only_scheme(g, prefix, codes, version)
    return g


def _add_scheme(
    g: Graph, scheme: Scheme, schemes: dict[str, Scheme], version: str, used_external: dict[str, set[str]]
) -> None:
    s = URIRef(scheme.iri)
    g.add((s, RDF.type, SKOS.ConceptScheme))
    g.add((s, SKOS.prefLabel, Literal(scheme.meta["title"], lang=LANG)))
    if desc := scheme.meta.get("description"):
        g.add((s, DCTERMS.description, Literal(desc.strip(), lang=LANG)))
    g.add((s, OWL.versionInfo, Literal(version)))
    g.add((s, DCTERMS.license, URIRef("https://creativecommons.org/publicdomain/zero/1.0/")))
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
    g.add((node, SKOS.inScheme, s))
    g.add((node, SKOS.prefLabel, Literal(c["label"], lang=LANG)))
    for field, prop in (("definition", SKOS.definition), ("note", SKOS.scopeNote)):
        if text := c.get(field):
            g.add((node, prop, Literal(text.strip(), lang=LANG)))
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


def _add_code_only_scheme(g: Graph, prefix: str, codes: set[str], version: str) -> None:
    s = URIRef(PREFIXES[prefix])
    g.add((s, RDF.type, SKOS.ConceptScheme))
    g.add((s, SKOS.prefLabel, Literal(CODE_ONLY[prefix], lang=LANG)))
    g.add((s, OWL.versionInfo, Literal(version)))
    for code in sorted(codes):
        node = URIRef(PREFIXES[prefix] + code)
        g.add((node, RDF.type, SKOS.Concept))
        g.add((node, SKOS.inScheme, s))
        g.add((node, SKOS.notation, Literal(code)))
        g.add((node, SKOS.prefLabel, Literal(code, lang=LANG)))


def write(
    schemes: dict[str, Scheme], version: str, out: Path, matches: list[tuple[str, str, str, str, list[str]]]
) -> list[Path]:
    """Write `r9lab-vocabulary.ttl`, `.jsonld` and `bafu-candidates.csv` into `out`.

    `matches` is `bafu_matches`: the CSV has one row per pattern and release, with its match count.
    """
    out.mkdir(parents=True, exist_ok=True)
    g = to_graph(schemes, version)
    ttl, jsonld, bafu = out / "r9lab-vocabulary.ttl", out / "r9lab-vocabulary.jsonld", out / "bafu-candidates.csv"
    g.serialize(ttl, format="turtle")
    g.serialize(jsonld, format="json-ld", auto_compact=True)
    with bafu.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["concept", "label", "release", "pattern", "matches"])
        for slug, cid, release, pattern, hits in matches:
            w.writerow([schemes[slug].iri + cid, schemes[slug].concepts[cid]["label"], release, pattern, len(hits)])
    return [ttl, jsonld, bafu]
