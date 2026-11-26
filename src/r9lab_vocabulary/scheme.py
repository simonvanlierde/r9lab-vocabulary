"""The vocabulary's data model: its IRIs and prefixes, the `Scheme` each YAML file loads into, and `load`.

Each file in `vocabulary/` is one concept scheme. Concept ids are opaque and never
reused: a concept that goes away is marked `deprecated`, never deleted. A mapping is a
CURIE whose prefix names either an outside scheme (`PREFIXES`) or another scheme of
this vocabulary (its `slug`).

`checks` holds the rules the vocabulary must keep, `export` writes it as SKOS and its side files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import yaml
from rdflib import SKOS, URIRef
from yaml.constructor import ConstructorError

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
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
# A match: (scheme slug, concept id, family, version, pattern, matched names).
Match = tuple[str, str, str, str, str, list[str]]
CC0 = URIRef("https://creativecommons.org/publicdomain/zero/1.0/")


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
    """Every `*.yaml` scheme in `directory`, keyed by slug.

    ValueError when there is none, or a file is not a `scheme` mapping with a `slug` and a
    `concepts` mapping; a repeated key in a file is a YAML error.
    """
    schemes = {}
    paths = sorted(directory.glob("*.yaml"))
    if not paths:
        msg = f"{directory}: no *.yaml scheme files"
        raise ValueError(msg)
    for path in paths:
        doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506
        meta = doc.get("scheme") if isinstance(doc, dict) else None
        if not isinstance(meta, dict) or not isinstance(meta.get("slug"), str):
            msg = f"{path.name}: needs a `scheme` mapping with a `slug`"
            raise ValueError(msg)  # noqa: TRY004 - bad input, not a caller's bug
        concepts = doc.get("concepts") or {}
        if not isinstance(concepts, dict):
            msg = f"{path.name}: `concepts` must map each id to a concept"
            raise ValueError(msg)  # noqa: TRY004 - bad input, not a caller's bug
        slug = meta["slug"]
        if slug in schemes or slug in PREFIXES:
            msg = f"{path.name}: scheme slug {slug!r} is already taken"
            raise ValueError(msg)
        schemes[slug] = Scheme(slug, meta, concepts)
    return schemes


def mappings(concept: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    """(relation, prefix, local) for each mapping of a concept."""
    for relation, curies in (concept.get("mappings") or {}).items():
        for curie in curies:
            prefix, _, local = str(curie).partition(":")
            yield relation, prefix, local


def iri(schemes: dict[str, Scheme], prefix: str, local: str) -> URIRef:
    """The IRI a CURIE stands for."""
    base = schemes[prefix].iri if prefix in schemes else PREFIXES[prefix]
    return URIRef(base + local)


def texts(c: dict[str, Any], field: str) -> list[Any]:
    """A text field's values: `example` may be one string or a list, every other field is one string."""
    value = c.get(field)
    if value is None:
        return []
    return value if field in MANY_TEXTS and isinstance(value, list) else [value]


def ancestors(s: Scheme, cid: str) -> Iterator[str]:
    """Each concept up the `broader` links from `cid`, once, and `cid` if a chain loops back. Skips unknown ids."""
    seen, todo = set(), list(s.concepts[cid].get("broader") or [])
    while todo:
        node = todo.pop()
        if node in seen or node not in s.concepts:
            continue
        seen.add(node)
        yield node
        todo += s.concepts[node].get("broader") or []
