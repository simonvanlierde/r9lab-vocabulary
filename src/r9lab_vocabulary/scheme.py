"""Load the YAML vocabulary, check it, and write it as SKOS.

Each file in `vocabulary/` is one concept scheme. Concept ids are opaque and never
reused: a concept that goes away is marked `deprecated`, never deleted. A mapping is a
CURIE whose prefix names either an outside scheme (`PREFIXES`) or another scheme of
this vocabulary (its `slug`).
"""

from __future__ import annotations

import csv
import json
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
# A concept's text fields; README "Write a concept's text" says what each holds.
TEXT_FIELDS = {
    "definition": SKOS.definition,
    "example": SKOS.example,
    "note": SKOS.scopeNote,
    "editorial_note": SKOS.editorialNote,
}
MANY_TEXTS = {"example"}
# Where the definition comes from: a URL, written as an IRI, or a citation.
SOURCE = "source"
ID = re.compile(r"^[a-z][0-9]{2,4}$")
# A match: (scheme slug, concept id, family, version, pattern, matched names).
Match = tuple[str, str, str, str, str, list[str]]
LANG = "en"


@dataclass(frozen=True)
class Scheme:
    """One YAML file: the scheme's metadata and its concepts keyed by id."""

    slug: str
    meta: dict[str, Any]
    concepts: dict[str, dict[str, Any]]

    def __post_init__(self) -> None:
        # A concept with nothing after its id in YAML loads as None; validate reports it as "no label".
        for cid, c in self.concepts.items():
            if c is None:
                self.concepts[cid] = {}

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
    letter = scheme.meta.get("id_letter")
    for cid, c in scheme.concepts.items():
        where = f"{scheme.slug}/{cid}"
        if not ID.match(cid) or (letter and not cid.startswith(letter)):
            errors.append(f"{where}: id must be {letter or 'a letter'} plus 2-4 digits")
        if not c.get("label"):
            errors.append(f"{where}: no label")
        errors += _validate_text(where, c)
        errors += _validate_links(where, c, scheme)
        errors += _validate_mappings(where, c, schemes)
        errors += _validate_names(where, c, versions)
    errors += _duplicates(
        scheme, "label", lambda c: None if c.get("deprecated") else str(c.get("label", "")).casefold()
    )
    errors += _duplicates(scheme, "notation", lambda c: None if c.get("notation") is None else str(c["notation"]))
    errors += _cycles(scheme)
    return errors


def _texts(c: dict[str, Any], field: str) -> list[Any]:
    """A text field's values: `example` may be one string or a list, every other field is one string."""
    value = c.get(field)
    if value is None:
        return []
    return value if field in MANY_TEXTS and isinstance(value, list) else [value]


def _validate_text(where: str, c: dict[str, Any]) -> list[str]:
    errors = [
        f"{where}: {field} must be non-empty text"
        for field in (*TEXT_FIELDS, SOURCE)
        if field in c and not ((values := _texts(c, field)) and all(isinstance(t, str) and t.strip() for t in values))
    ]
    if SOURCE in c and not c.get("definition"):
        errors.append(f"{where}: {SOURCE} needs a definition to cite")
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
    for ref in c.get("replaced_by") or []:
        target = scheme.concepts.get(ref)
        if target is None:
            errors.append(f"{where}: replaced_by {ref} does not exist")
        elif target is c:
            errors.append(f"{where}: replaced_by {ref} is itself")
        elif target.get("deprecated"):
            errors.append(f"{where}: replaced_by {ref} is deprecated")
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
    for field, prop in TEXT_FIELDS.items():
        for text in _texts(c, field):
            g.add((node, prop, Literal(text.strip(), lang=LANG)))
    if source := c.get(SOURCE):
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


def write(schemes: dict[str, Scheme], version: str, out: Path, matches: list[Match]) -> list[Path]:
    """Write `r9lab-vocabulary.ttl`, `.jsonld` and `name-matches.csv` into `out`.

    `matches` is `name_matches`: the CSV has one row per pattern and source (`bafu-2026-v1`), with its match count.
    """
    out.mkdir(parents=True, exist_ok=True)
    g = to_graph(schemes, version)
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


def write_sssom(schemes: dict[str, Scheme], version: str, out: Path, author: str) -> Path:
    """Write `r9lab-vocabulary.sssom.tsv` into `out`: one SSSOM row per `mappings` entry.

    Every row is a person's curation, so its justification is `semapv:ManualMappingCuration`
    and `author` (an ORCID IRI) is its author. Mappings from or to a deprecated concept are
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
        "mapping_set_version": version,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
    }
    author_id = f"orcid:{author.removeprefix(orcid)}"
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
            key = str(c.get("notation", cid))
            inherited.setdefault((slug, cid), set()).add(key)
            for relation, prefix, local in mappings(c):
                target = {"exact": inherited, "narrow": inherited, "close": own}.get(relation)
                if target is not None and prefix in schemes:
                    target.setdefault((prefix, local), set()).add(key)
    return inherited, own


def _ancestors(s: Scheme, cid: str) -> set[str]:
    """`cid` and every concept above it, through all its `broader` parents."""
    seen, todo = set(), [cid]
    while todo:
        node = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(s.concepts[node].get("broader") or [])
    return seen


def labels(schemes: dict[str, Scheme]) -> list[dict[str, Any]]:
    """Per scheme, each non-deprecated concept by id: IRI, label, label path from its root, definition, pilot keys.

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
            definition = s.concepts[cid].get("definition")
            pilot = own.get((slug, cid), set()).union(*(inherited.get((slug, a), set()) for a in _ancestors(s, cid)))
            concepts.append(
                {
                    "id": cid,
                    "iri": s.iri + cid,
                    "label": s.concepts[cid]["label"],
                    "path": [s.concepts[a]["label"] for a in chain],
                    "definition": definition.strip() if definition else None,
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
