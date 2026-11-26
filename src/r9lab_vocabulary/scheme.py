"""Load the YAML vocabulary, check it, and write it as SKOS.

Each file in `vocabulary/` is one concept scheme. Concept ids are opaque and never
reused: a concept that goes away is marked `deprecated`, never deleted. A mapping is a
CURIE whose prefix names either an outside scheme (`PREFIXES`) or another scheme of
this vocabulary (its `slug`).

Every scheme, and the vocabulary as a whole (`BASE`, a `dcat:Dataset`), says who made and
publishes it (the ORCID iDs in CITATION.cff), when it was created (the scheme's `created`)
and modified, and which release it is: `owl:versionIRI` is `BASE<version>/<path>`, so one
redirect rule per release can send every versioned IRI to that release's files.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import yaml
from rdflib import DCAT, DCTERMS, OWL, RDF, SDO, SKOS, XSD, Graph, Literal, Namespace, URIRef
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
    "unu2": f"{BASE}external/unu-key-v2/",
    "r9lab-cpv": f"{BASE}external/r9lab-cpv/",
    # The six categories of Annex III to the WEEE Directive 2012/19/EU. They have no IRIs of
    # their own, so each is a fragment on the directive's ELI, after its Annex III anchor.
    "weee6": "http://data.europa.eu/eli/dir/2012/19/oj#anx_III-",
}
# Outside schemes whose whole code list is fixed by their source text, so it is pinned here
# rather than in sources.toml.
# UNU-KEYs, codes only, from the E-waste Statistics Guidelines, 3rd ed., 2026: v1 is the left
# column of Table 19 (Annex 2), v2 is Table 2. v1 0406 merged into 0401; 0310, 0409, 0704 and
# 0705 are new in v2.
# fmt: off
FIXED_CODES = {
    "weee6": {"1", "2", "3", "4", "5", "6"},
    "unu1": {
        "0001", "0002", "0101", "0102", "0103", "0104", "0105", "0106", "0108", "0109", "0111", "0112",
        "0113", "0114", "0201", "0202", "0203", "0204", "0205", "0301", "0302", "0303", "0304", "0305",
        "0306", "0307", "0308", "0309", "0401", "0402", "0403", "0404", "0405", "0406", "0407", "0408",
        "0501", "0502", "0503", "0504", "0505", "0506", "0507", "0601", "0602", "0701", "0702", "0703",
        "0801", "0802", "0901", "0902", "1001", "1002",
    },
    "unu2": {
        "0001", "0002", "0101", "0102", "0103", "0104", "0105", "0106", "0108", "0109", "0111", "0112",
        "0113", "0114", "0201", "0202", "0203", "0204", "0205", "0301", "0302", "0303", "0304", "0305",
        "0306", "0307", "0308", "0309", "0310", "0401", "0402", "0403", "0404", "0405", "0407", "0408",
        "0409", "0501", "0502", "0503", "0504", "0505", "0506", "0507", "0601", "0602", "0701", "0702",
        "0703", "0704", "0705", "0801", "0802", "0901", "0902", "1001", "1002",
    },
}
# fmt: on
CODE_ONLY = {
    "unu1": "UNU-KEY v1 codes (codes only; names under CC BY-NC-SA 3.0 IGO are not copied)",
    "unu2": "UNU-KEY v2 codes (codes only; names under CC BY-NC-SA 4.0 are not copied)",
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
# A version path segment (`0.1.0`) starts with a digit, so it never collides with a scheme slug.
SLUG = re.compile(r"^[a-z]")
# A match: (scheme slug, concept id, family, version, pattern, matched names).
Match = tuple[str, str, str, str, str, list[str]]
LANG = "en"
LANGUAGE = URIRef("http://id.loc.gov/vocabulary/iso639-1/en")
CC0 = URIRef("https://creativecommons.org/publicdomain/zero/1.0/")
TITLE = "R9lab reference vocabulary"
BIBO = Namespace("http://purl.org/ontology/bibo/")
# PyST accepts only draft, accepted and rejected; deprecation is owl:deprecated, so a deprecated concept stays accepted.
ACCEPTED = URIRef("http://purl.org/ontology/bibo/status/accepted")


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


def validate(schemes: dict[str, Scheme], versions: dict[str, set[str]]) -> list[str]:
    """Every rule the vocabulary breaks, as `scheme/id: message`; empty when it is sound.

    `versions` maps each name-list family (`bafu`) to its pinned versions (`2026-v1`): a
    `names` entry for another family, or scoped to another version, is an error.
    """
    errors: list[str] = []
    for scheme in schemes.values():
        errors += _validate_scheme(scheme, schemes, versions)
    return errors


def _validate_scheme(scheme: Scheme, schemes: dict[str, Scheme], versions: dict[str, set[str]]) -> list[str]:
    errors = []
    if not SLUG.match(scheme.slug):
        errors.append(f"{scheme.slug}: slug must start with a lower-case letter")
    created = scheme.meta.get("created")
    if created is not None and (not isinstance(created, date) or isinstance(created, datetime)):
        errors.append(f"{scheme.slug}: created must be a date (YYYY-MM-DD, unquoted), not {created!r}")
    letter = scheme.meta.get("id_letter")
    for cid, c in scheme.concepts.items():
        where = f"{scheme.slug}/{cid}"
        if not ID.match(cid) or (letter and not cid.startswith(letter)):
            errors.append(f"{where}: id must be {letter or 'a letter'} plus 2-4 digits")
        if not c.get("label"):
            errors.append(f"{where}: no label")
        errors += _validate_links(where, c, scheme)
        errors += _validate_mappings(where, c, schemes)
        errors += _validate_names(where, c, versions)
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


def name_patterns(c: dict[str, Any]) -> list[tuple[str, str, list[str] | None]]:
    """(family, pattern, versions) for each `names` entry; versions is None for one that applies to every version.

    `names` maps a family to its patterns. An entry is a pattern string, or
    `{pattern: ..., versions: [2026-v1, ...]}` for a name that only some versions use.
    """
    out: list[tuple[str, str, list[str] | None]] = []
    for family, entries in (c.get("names") or {}).items():
        for entry in entries:
            if isinstance(entry, dict):
                out.append((family, str(entry["pattern"]), [str(v) for v in entry["versions"]]))
            else:
                out.append((family, str(entry), None))
    return out


def _bad_name_entry(entry: object) -> bool:
    if isinstance(entry, dict):
        scoped = entry.get("versions")
        return (
            set(entry) != {"pattern", "versions"}
            or _bad_name_entry(entry["pattern"])
            or not isinstance(scoped, list)
            or not scoped
            or not all(isinstance(v, str) for v in scoped)
        )
    return not isinstance(entry, str) or not entry.strip()


def _validate_names(where: str, c: dict[str, Any], versions: dict[str, set[str]]) -> list[str]:
    families = c.get("names") or {}
    if not isinstance(families, dict) or not all(isinstance(v, list) for v in families.values()):
        return [f"{where}: names must map each family to a list of patterns"]
    errors = [
        f"{where}: names family {f!r} has no pinned source in sources.toml" for f in families if f not in versions
    ]
    errors += [
        f"{where}: names entry {entry!r} must be a non-empty pattern or exactly a pattern and a non-empty versions list"
        for entries in families.values()
        for entry in entries
        if _bad_name_entry(entry)
    ]
    if errors:
        return errors
    for family, pattern, scoped in name_patterns(c):
        try:
            re.compile(pattern)
        except re.error as e:
            errors.append(f"{where}: {family} pattern {pattern!r}: {e}")
        errors.extend(
            f"{where}: {family} pattern {pattern!r} names unknown version {v!r}"
            for v in scoped or []
            if v not in versions[family]
        )
    return errors


def name_matches(schemes: dict[str, Scheme], lists: dict[str, dict[str, list[str]]]) -> list[Match]:
    """Each pattern against each version of its family it applies to, with the names it matches.

    `lists` maps family -> version -> names, already stripped of entries the family marks
    obsolete. A pattern matches a name by case-insensitive search. Deprecated concepts are
    skipped. Call it on a vocabulary `validate` passed.
    """
    out: list[Match] = []
    for scheme in schemes.values():
        for cid, c in scheme.concepts.items():
            if c.get("deprecated"):
                continue
            for family, pattern, scoped in name_patterns(c):
                rx = re.compile(pattern, re.IGNORECASE)
                for version in sorted(lists.get(family, {})):
                    if scoped is None or version in scoped:
                        hits = [n for n in lists[family][version] if rx.search(n)]
                        out.append((scheme.slug, cid, family, version, pattern, hits))
    return out


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
        elif local not in FIXED_CODES.get(prefix, {local}):
            errors.append(f"{where}: {curie} is not a {prefix} code")
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


def diff(old: dict[str, Scheme], new: dict[str, Scheme]) -> tuple[list[str], bool]:
    """The concepts added, deprecated, removed, remapped and relabelled from `old` to `new`, as Markdown lines.

    The flag is False when a concept id in `old` is missing from `new`: an id that leaves use stays, deprecated.
    """
    before, after = ({f"{s.slug}/{cid}": c for s in v.values() for cid, c in s.concepts.items()} for v in (old, new))
    sections: dict[str, list[str]] = {t: [] for t in ("Added", "Deprecated", "Removed", "Mappings", "Labels")}
    for key in sorted(before.keys() | after.keys()):
        a, b = before.get(key), after.get(key)
        if b is None:
            sections["Removed"].append(
                f"- `{key}` {a and a.get('label')}: deprecate it with `replaced_by` instead of deleting it"
            )
            continue
        if a is None:
            sections["Added"].append(f"- `{key}` {b['label']}")
            continue
        if b.get("deprecated") and not a.get("deprecated"):
            slug = key.partition("/")[0]
            by = ", ".join(f"`{slug}/{ref}`" for ref in b.get("replaced_by") or [])
            how = f"replaced by {by}" if by else "with no `replaced_by`"
            sections["Deprecated"].append(f"- `{key}` {b['label']}, {how}")
        if a.get("deprecated") and not b.get("deprecated"):
            sections["Deprecated"].append(f"- `{key}` {b['label']}: no longer deprecated")
        maps_a, maps_b = ({f"{rel} {prefix}:{local}" for rel, prefix, local in mappings(c)} for c in (a, b))
        if maps_a != maps_b:
            changes = [f"added {m}" for m in sorted(maps_b - maps_a)]
            changes += [f"dropped {m}" for m in sorted(maps_a - maps_b)]
            sections["Mappings"].append(f"- `{key}` {b['label']}: {'; '.join(changes)}")
        if a.get("label") != b.get("label"):
            sections["Labels"].append(f"- `{key}`: {a.get('label')} -> {b['label']}")
    lines = []
    for title, items in sections.items():
        if items:
            lines += [f"### {title}", "", *items, ""]
    return lines, not sections["Removed"]


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


@dataclass(frozen=True)
class About:
    """What every scheme says about its release: version, CITATION.cff, and the date the build stands for."""

    version: str
    citation: dict[str, Any]
    modified: date | None

    def describe(self, g: Graph, node: URIRef, title: str, created: date | None) -> None:
        """Type `node` as a schema.org term set and add its title, version, dates, creators and landing page."""
        g.add((node, RDF.type, SDO.DefinedTermSet))
        g.add((node, SDO.name, Literal(title, lang=LANG)))
        g.add((node, DCTERMS.title, Literal(title, lang=LANG)))
        g.add((node, OWL.versionInfo, Literal(self.version)))
        g.add((node, OWL.versionIRI, URIRef(f"{BASE}{self.version}/{str(node).removeprefix(BASE)}")))
        g.add((node, DCTERMS.license, CC0))
        g.add((node, DCTERMS.language, LANGUAGE))
        for prop, value in ((DCTERMS.created, created), (DCTERMS.modified, self.modified)):
            if value is not None:
                g.add((node, prop, Literal(value)))
        orcids = [URIRef(a["orcid"]) for a in self.citation.get("authors") or [] if a.get("orcid")]
        for orcid in orcids:
            g.add((node, DCTERMS.creator, orcid))
        if orcids:
            g.add((node, DCTERMS.publisher, orcids[0]))
        if repo := self.citation.get("repository-code"):
            g.add((node, DCAT.landingPage, URIRef(repo)))


def to_graph(
    schemes: dict[str, Scheme], version: str, *, citation: dict[str, Any] | None = None, modified: date | None = None
) -> Graph:
    """The whole vocabulary as one SKOS graph, its schemes the parts of one `dcat:Dataset`.

    `citation` is CITATION.cff, read for the authors' ORCID iDs and `repository-code`; `modified` is
    `dct:modified`. Without them those triples are left out.
    """
    g = Graph()
    namespaces = (("skos", SKOS), ("dcterms", DCTERMS), ("dcat", DCAT), ("schema", SDO), ("owl", OWL), ("bibo", BIBO))
    for prefix, ns in namespaces:
        g.bind(prefix, ns)
    for slug, scheme in schemes.items():
        g.bind(f"r9-{slug}", Namespace(scheme.iri))
    about = About(version, citation or {}, modified)
    # The code-only schemes and the whole are as old as the oldest scheme written here.
    created = min(filter(None, (s.meta.get("created") for s in schemes.values())), default=None)
    vocab = URIRef(BASE)
    g.add((vocab, RDF.type, DCAT.Dataset))
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


def write(
    schemes: dict[str, Scheme],
    version: str,
    out: Path,
    matches: list[Match],
    *,
    citation: dict[str, Any] | None = None,
    modified: date | None = None,
) -> list[Path]:
    """Write `r9lab-vocabulary.ttl`, `.jsonld` and `name-matches.csv` into `out`.

    `matches` is `name_matches`: the CSV has one row per pattern and source (`bafu-2026-v1`), with its match count.
    `citation` and `modified` are as in `to_graph`.
    """
    out.mkdir(parents=True, exist_ok=True)
    g = to_graph(schemes, version, citation=citation, modified=modified)
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
