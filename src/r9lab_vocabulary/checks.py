"""The rules the vocabulary keeps, and what changed between two releases of it.

`validate` checks it on its own, `check_codes` against the pinned sources,
`check_tag_mappings` checks the R9lab tag file, and `diff` compares two releases.

`name_matches` runs each concept's `names` patterns against the pinned name lists.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import yaml

from r9lab_vocabulary.scheme import (
    FIXED_CODES,
    PREFIXES,
    RELATIONS,
    SOURCE,
    TEXT_FIELDS,
    Match,
    ancestors,
    mappings,
    texts,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping
    from pathlib import Path

    from r9lab_vocabulary.scheme import Scheme

# Every field a concept may carry; validate rejects any other, so a misspelt one is not lost.
FIELDS = {"label", "notation", *TEXT_FIELDS, SOURCE, "broader", "related", "mappings", "names"}
# A concept in use carries all three, so a model prompt never gets a bare label.
REQUIRED_TEXTS = ("definition", "example", "note")
FIELDS |= {"deprecated", "replaced_by"}
ID = re.compile(r"^[a-z][0-9]{2,4}$")
# A version path segment (`0.1.0`) starts with a digit, so it never collides with a scheme slug.
SLUG = re.compile(r"^[a-z]")


def validate(schemes: dict[str, Scheme], versions: Mapping[str, Collection[str]]) -> list[str]:
    """Every rule the vocabulary breaks, as `scheme/id: message`; empty when it is sound.

    `versions` maps each name-list family (`bafu`) to its pinned versions (`2026-v1`), such as
    the version -> names lists `name_matches` takes: a `names` entry for another family, or
    scoped to another version, is an error.
    """
    errors: list[str] = []
    for scheme in schemes.values():
        errors += _validate_scheme(scheme, schemes, versions)
    return errors


def _validate_scheme(scheme: Scheme, schemes: dict[str, Scheme], versions: Mapping[str, Collection[str]]) -> list[str]:
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
        errors += [f"{where}: unknown field {k!r}" for k in sorted(set(c) - FIELDS)]
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


def _validate_text(where: str, c: dict[str, Any]) -> list[str]:
    errors = [
        f"{where}: {field} must be non-empty text"
        for field in (*TEXT_FIELDS, SOURCE)
        if field in c and not ((values := texts(c, field)) and all(isinstance(t, str) and t.strip() for t in values))
    ]
    if SOURCE in c and not c.get("definition"):
        errors.append(f"{where}: {SOURCE} needs a definition to cite")
    if not c.get("deprecated") and (missing := [f for f in REQUIRED_TEXTS if not c.get(f)]):
        errors.append(f"{where}: missing {', '.join(missing)}")
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


def _validate_names(where: str, c: dict[str, Any], versions: Mapping[str, Collection[str]]) -> list[str]:
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
    loops = [cid for cid in scheme.concepts if cid in ancestors(scheme, cid)]
    return [f"{scheme.slug}/{cid}: broader chain loops back to itself" for cid in loops]


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
                f"- `{key}` {before[key].get('label')}: deprecate it with `replaced_by` instead of deleting it"
            )
            continue
        if a is None:
            sections["Added"].append(f"- `{key}` {b.get('label')}")
            continue
        if b.get("deprecated") and not a.get("deprecated"):
            slug = key.partition("/")[0]
            by = ", ".join(f"`{slug}/{ref}`" for ref in b.get("replaced_by") or [])
            how = f"replaced by {by}" if by else "with no `replaced_by`"
            sections["Deprecated"].append(f"- `{key}` {b.get('label')}, {how}")
        if a.get("deprecated") and not b.get("deprecated"):
            sections["Deprecated"].append(f"- `{key}` {b.get('label')}: no longer deprecated")
        maps_a, maps_b = ({f"{rel} {prefix}:{local}" for rel, prefix, local in mappings(c)} for c in (a, b))
        if maps_a != maps_b:
            changes = [f"added {m}" for m in sorted(maps_b - maps_a)]
            changes += [f"dropped {m}" for m in sorted(maps_a - maps_b)]
            sections["Mappings"].append(f"- `{key}` {b.get('label')}: {'; '.join(changes)}")
        if a.get("label") != b.get("label"):
            sections["Labels"].append(f"- `{key}`: {a.get('label')} -> {b.get('label')}")
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


NO_TERM = "sssom:NoTermFound"
TAG_PREFIX = "r9lab-tag"
TAG_COLUMNS = ("subject_id", "subject_label", "predicate_id", "object_id", "object_label", "mapping_justification")


def read_sssom(path: Path) -> tuple[dict[str, Any], csv.DictReader[str]]:
    """An SSSOM TSV file's `#` metadata block and its rows; a short row's missing fields are empty."""
    lines = path.read_text(encoding="utf-8").splitlines()
    meta = yaml.safe_load("\n".join(line[1:] for line in lines if line.startswith("#"))) or {}
    return meta, csv.DictReader((line for line in lines if not line.startswith("#")), delimiter="\t", restval="")


def check_tag_mappings(schemes: dict[str, Scheme], path: Path) -> list[str]:
    """Rows of the SSSOM file that maps R9lab tags to concepts that break a rule.

    A tag (`subject_label`) is lower case, as tags are matched, and appears once; its
    `subject_id` is `r9lab-tag:` plus the URL-encoded tag. Its predicate is a SKOS match
    property (`skos:exactMatch`, as `export.write_sssom` writes it), its justification a semapv
    term, and its object a live concept here, under its current label, or
    `sssom:NoTermFound`. Every CURIE's prefix is in the file's `curie_map`. A missing file is one error.
    """
    try:
        meta, reader = read_sssom(path)
    except FileNotFoundError:
        return [f"{path}: missing"]
    prefixes = set(meta.get("curie_map") or {})
    if missing := [c for c in TAG_COLUMNS if c not in (reader.fieldnames or [])]:
        return [f"{path.name}: no {', '.join(missing)} column"]
    predicates = {f"skos:{p.fragment}" for p in RELATIONS.values()}
    errors, seen = [], set()
    for row in reader:
        label, obj = row["subject_label"], row["object_id"]
        where = f"{path.name}: {label!r}"
        if label != label.strip().lower() or label in seen:
            errors.append(f"{where} is not lower case or appears twice")
        seen.add(label)
        if row["subject_id"] != f"{TAG_PREFIX}:{quote(label, safe='')}":
            errors.append(f"{where}: subject_id {row['subject_id']} is not {TAG_PREFIX}: plus the encoded tag")
        if row["predicate_id"] not in predicates:
            errors.append(f"{where}: unknown predicate {row['predicate_id']}")
        if not row["mapping_justification"].startswith("semapv:"):
            errors.append(f"{where}: justification {row['mapping_justification']!r} is not a semapv term")
        curies = [row[c] for c in ("subject_id", "predicate_id", "object_id", "mapping_justification")]
        curies += [r for r in [row.get("reviewer_id")] if r]
        errors += [f"{where}: prefix of {c} is not in the curie_map" for c in curies if c.split(":")[0] not in prefixes]
        slug, _, cid = obj.partition(":")
        concept = schemes[slug].concepts.get(cid) if slug in schemes else None
        if obj != NO_TERM and (concept is None or concept.get("deprecated")):
            errors.append(f"{where}: {obj} is not a live concept")
        elif row["object_label"] != (concept["label"] if concept else ""):
            errors.append(f"{where}: object_label {row['object_label']!r} is not {obj}'s label")
    return errors
