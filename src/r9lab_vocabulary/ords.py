"""Validate the proposed ORDS v0.3 EEE crosswalk without adding links to the vocabulary build."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

from r9lab_vocabulary import scheme

TABLE = Path("mappings/ords-v0.3-eee.csv")
COLUMNS = ("product_category_id", "r9lab_product_id", "relation", "review_note")
SOURCE_BASE = "https://media.githubusercontent.com/media/openrepair/data/2af16342c751f56e28e2f62d018f051e7f22aed0/"
SOURCE_CSV = "OpenRepairData_v0.3_Product_Categories_eee.csv"
SOURCE_SHA256 = "c9309e6146bd64f2bc635bc296926413ead8fe8bb9dee14479b4d8e978ab4ba1"
RELATIONS = {"broad", "close", "exact"}
NO_MATCH = "no_match"


class ReviewRow(NamedTuple):
    """A category disposition and the evidence for review."""

    category: str
    product: str
    relation: str
    note: str


def category_codes(codelist: Path | None = None) -> set[str]:
    """Read and verify the publisher's CSV, or use the codes transcribed from that pin."""
    if codelist is None:
        return {str(code) for code in range(1, 41)}
    payload = codelist.read_bytes()
    if (digest := hashlib.sha256(payload).hexdigest()) != SOURCE_SHA256:
        msg = f"{codelist}: SHA-256 {digest} differs from the ORDS v0.3 EEE pin {SOURCE_SHA256}"
        raise ValueError(msg)
    rows = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
    return {row["product_category_id"] for row in rows}


def product_ids(vocabulary: Path) -> set[str]:
    """Live product types in the vocabulary, excluding navigation parents."""
    products = scheme.load(vocabulary).get("products")
    if products is None:
        msg = f"{vocabulary}: no products scheme"
        raise ValueError(msg)
    parents = {parent for concept in products.concepts.values() for parent in concept.get("broader", [])}
    return {cid for cid, concept in products.concepts.items() if cid not in parents and not concept.get("deprecated")}


def _row_errors(where: str, product: str, relation: str, note: str, products: set[str]) -> list[str]:
    errors = []
    if not note.strip():
        errors.append(f"{where}: needs a review note")
    if relation == NO_MATCH:
        if product:
            errors.append(f"{where}: no_match requires an empty product ID")
    elif relation not in RELATIONS:
        errors.append(f"{where}: unknown relation {relation!r}")
    elif product not in products:
        errors.append(f"{where}: product {product!r} is not a live leaf type")
    return errors


def read_review(table: Path, products: set[str], codes: set[str]) -> tuple[list[ReviewRow], list[str]]:
    """Read each disposition, with any errors in the endpoints, relation or coverage."""
    review = []
    errors = []
    dispositions: dict[str, set[str]] = {}
    rollups: dict[str, str] = {}
    with table.open(encoding="utf-8", newline="") as stream:
        rows = csv.reader(stream, strict=True)
        if tuple(next(rows, [])) != COLUMNS:
            return [], [f"{table}: expected columns {', '.join(COLUMNS)}"]
        for row in rows:
            where = f"{table}:{rows.line_num}"
            if len(row) != len(COLUMNS):
                errors.append(f"{where}: expected {len(COLUMNS)} fields")
                continue
            category, product, relation, note = entry = ReviewRow(*row)
            if category not in codes:
                errors.append(f"{where}: unknown ORDS code {category!r}")
                continue
            errors.extend(_row_errors(where, product, relation, note, products))
            targets = dispositions.setdefault(category, set())
            if product in targets:
                errors.append(f"{where}: duplicate disposition for ORDS code {category} and product {product!r}")
            targets.add(product)
            if (
                product in products
                and relation in {"exact", "broad"}
                and rollups.setdefault(product, category) != category
            ):
                errors.append(f"{where}: {product} would roll up to ORDS codes {rollups[product]} and {category}")
            review.append(entry)
    for code, targets in dispositions.items():
        if "" in targets and len(targets) > 1:
            errors.append(f"{table}: ORDS code {code} has both candidates and no_match")
    if missing := codes - dispositions.keys():
        errors.append(f"{table}: missing dispositions for ORDS codes {', '.join(sorted(missing, key=int))}")
    return review, errors


def draft_sssom(review: list[ReviewRow]) -> str:
    """Write the positive proposals as SSSOM TSV, using literal category codes."""
    out = io.StringIO(newline="")
    metadata = {
        "curie_map": {
            "ords-source": SOURCE_BASE,
            "products": f"{scheme.BASE}products/",
            "semapv": "https://w3id.org/semapv/vocab/",
            "skos": str(scheme.SKOS),
        },
        "mapping_set_id": f"{scheme.BASE}ords-v0.3-eee.csv",
        "mapping_set_title": "Draft R9lab to ORDS v0.3 EEE proposals",
        "license": str(scheme.CC0),
    }
    out.writelines(f"#{line}\n" for line in yaml.safe_dump(metadata, sort_keys=False).splitlines())
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(
        (
            "subject_id",
            "predicate_id",
            "object_id",
            "object_label",
            "object_type",
            "object_source",
            "object_source_version",
            "mapping_justification",
            "comment",
        )
    )
    for category, product, relation, note in review:
        if relation != NO_MATCH:
            writer.writerow(
                (
                    f"products:{product}",
                    f"skos:{relation}Match",
                    "",
                    category,
                    "rdfs literal",
                    f"ords-source:{SOURCE_CSV}",
                    "0.3",
                    "semapv:UnspecifiedMatching",
                    note,
                )
            )
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    """Run the proposal check. Exit 1 for findings, 2 for usage, or 3 for I/O errors."""
    parser = argparse.ArgumentParser(
        prog="python -m r9lab_vocabulary.ords",
        description="Check the draft ORDS v0.3 EEE crosswalk.",
        epilog="Example: uv run python -m r9lab_vocabulary.ords",
        allow_abbrev=False,
    )
    parser.add_argument("--codelist", type=Path, help="verify the publisher CSV at PATH against the pinned SHA-256")
    parser.add_argument("--sssom", action="store_true", help="write the checked draft links as SSSOM TSV")
    args = parser.parse_args(argv)
    try:
        codes = category_codes(args.codelist)
        review, errors = read_review(TABLE, product_ids(Path("vocabulary")), codes)
    except OSError as error:
        sys.stderr.write(f"error: {error}\n")
        return 3
    except (ValueError, csv.Error, yaml.YAMLError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    if errors:
        sys.stderr.writelines(f"error: {error}\n" for error in errors)
        return 1
    if args.sssom:
        sys.stdout.write(draft_sssom(review))
    else:
        sys.stdout.write(f"Checked {len(codes)} ORDS v0.3 EEE category dispositions in {TABLE}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
