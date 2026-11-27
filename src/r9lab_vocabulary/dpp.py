"""Checks for the proposed CIRPASS-2 crosswalk and its pinned Hub releases."""

from __future__ import annotations

import argparse
import csv
import sys
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from rdflib import OWL, RDF, Graph, URIRef

from r9lab_vocabulary import scheme

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from r9lab_vocabulary.scheme import Scheme

CROSSWALK = Path("docs/crosswalks/cirpass-2-crosswalk-v1.tsv")
CLASS_INDEX = "cirpass-2-electronics-v1-classes.txt"
ELECTRONICS_SHA256 = "c2f01ff2c4575917feea4b6a505df3c519a17203b0a4f6994fa8e85d27e30697"
MAT_SHA256 = "67432b3479e5cfda839274f880862962225777624fe94bb84832e1c239fc96bc"
CLASS_INDEX_SHA256 = "a897aadae3528f8e34dc479e350516fa638f1882201c6394296bec6847ef88c4"

COLUMNS = ["module", "scheme", "concept_id", "disposition", "target_iri", "reason"]
ELECTRONICS = "electronics-v1"
NO_MATCH = "no-match"
MODULE_SCHEMES = {ELECTRONICS: ("components", "materials"), "mat-v1.1.0": ("materials",)}
DISPOSITIONS = {"close", "broad", "contextual", NO_MATCH}


def validate_crosswalk(
    schemes: Mapping[str, Scheme],
    table: Path = CROSSWALK,
    *,
    electronics: Path | None = None,
    mat: Path | None = None,
) -> list[str]:
    """Check every disposition against the vocabulary and the pinned Electronics class index.

    Supply the Hub Turtle files to verify their bytes and regenerate the class index in memory.
    Local builds can use the checked-in index without downloading the ontologies.
    """
    index = table.with_name(CLASS_INDEX)
    try:
        class_index = index.read_text(encoding="utf-8")
        if sha256(class_index.encode("utf-8")).hexdigest() != CLASS_INDEX_SHA256:
            return [f"{index}: SHA-256 differs from the pinned Electronics class index"]
        known = set(class_index.splitlines())
        with table.open(encoding="utf-8", newline="") as stream:
            rows = csv.reader(stream, delimiter="\t", strict=True)
            if next(rows, None) != COLUMNS:
                return [f"{table}: expected columns {', '.join(COLUMNS)}"]
            errors = _check_rows(schemes, table, rows, known)
    except (UnicodeError, csv.Error) as exc:
        return [f"{table}: {exc}"]
    for path, expected in ((electronics, ELECTRONICS_SHA256), (mat, MAT_SHA256)):
        if path is not None:
            errors.extend(_check_source(path, expected, known))
    return errors


def _check_rows(
    schemes: Mapping[str, Scheme],
    table: Path,
    rows: Iterable[list[str]],
    known: set[str],
) -> list[str]:
    expected = {
        (module, slug, cid)
        for module, slugs in MODULE_SCHEMES.items()
        for slug in slugs
        if slug in schemes
        for cid in schemes[slug].concepts
    }
    errors = [
        f"{table}: vocabulary is missing scheme {slug}" for slug in ("components", "materials") if slug not in schemes
    ]
    seen = set()
    for number, row in enumerate(rows, start=2):
        where = f"{table}: row {number}"
        if len(row) != len(COLUMNS):
            errors.append(f"{where}: expected {len(COLUMNS)} columns")
            continue
        module, slug, cid, disposition, target, reason = row
        key = (module, slug, cid)
        if key not in expected:
            errors.append(f"{where}: unknown concept or module assignment {module} {slug}/{cid}")
        if key in seen:
            errors.append(f"{where}: duplicate row for {module} {slug}/{cid}")
        seen.add(key)
        if not reason.strip():
            errors.append(f"{where}: expected a reason for the disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{where}: unknown disposition {disposition!r}")
        elif disposition == NO_MATCH:
            if target:
                errors.append(f"{where}: a no-match row must have no target")
        elif module != ELECTRONICS or target not in known:
            errors.append(f"{where}: target {target!r} is not an OWL class in the pinned module")
    errors.extend(
        f"{table}: missing coverage for {module} {slug}/{cid}" for module, slug, cid in sorted(expected - seen)
    )
    return errors


def _check_source(path: Path, expected: str, known: set[str]) -> list[str]:
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != expected:
        return [f"{path}: SHA-256 differs from pinned Hub release {expected}"]
    if expected == ELECTRONICS_SHA256:
        graph = Graph().parse(data=payload, format="turtle")
        classes = {str(iri) for iri in graph.subjects(RDF.type, OWL.Class) if isinstance(iri, URIRef)}
        if classes != known:
            return [f"{path}: declared OWL classes differ from the checked-in index"]
    return []


def main(argv: list[str] | None = None) -> int:
    """Run the proposal check. Exit 1 for findings, 2 for usage, or 3 for I/O errors."""
    parser = argparse.ArgumentParser(
        prog="python -m r9lab_vocabulary.dpp",
        description="Check the draft CIRPASS-2 crosswalk.",
        epilog="Example: uv run python -m r9lab_vocabulary.dpp",
        allow_abbrev=False,
    )
    parser.add_argument("--electronics", type=Path, help="verify the Hub Electronics Turtle file at PATH")
    parser.add_argument("--mat", type=Path, help="verify the Hub MAT Turtle file at PATH")
    args = parser.parse_args(argv)
    try:
        schemes = scheme.load(Path("vocabulary"))
        errors = validate_crosswalk(schemes, electronics=args.electronics, mat=args.mat)
    except OSError as error:
        sys.stderr.write(f"error: {error}\n")
        return 3
    except (ValueError, yaml.YAMLError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    if errors:
        sys.stderr.writelines(f"error: {error}\n" for error in errors)
        return 1
    sys.stdout.write(f"Checked CIRPASS-2 component and material dispositions in {CROSSWALK}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
