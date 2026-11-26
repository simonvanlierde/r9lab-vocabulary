"""The review log for the R9lab tag mappings, and the published file built from it.

Machines propose: `mappings/r9lab-tags/predictions.sssom.tsv` holds their rows, with no reviewer.
People review: `mappings/r9lab-tags/reviews.sssom.tsv` gets one row per rater per verdict, appended,
with `reviewer_agreement` 1 (agree), -1 (disagree) or 0 (unsure). The rater's latest row for a mapping
counts. `mappings/r9lab-tags.sssom.tsv` is built from both and is the file others read: every
proposal no rater rejected, with the raters who agreed in `reviewer_id`. `docs/decisions/0005` says why.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import sys
from pathlib import Path

import yaml

from r9lab_vocabulary.scheme import read_sssom

PREDICTIONS = Path("mappings/r9lab-tags/predictions.sssom.tsv")
REVIEWS = Path("mappings/r9lab-tags/reviews.sssom.tsv")
PUBLISHED = Path("mappings/r9lab-tags.sssom.tsv")

KEY = ("subject_id", "predicate_id", "object_id")
MACHINE = {"semapv:AgentBasedMatching", "semapv:LLMBasedMatching", "semapv:LexicalMatching"}
# The last column is never empty: the trailing-whitespace hook would strip an empty one's tab.
PREDICTION_COLUMNS = (
    "subject_id", "subject_label", "predicate_id", "object_id", "object_label",
    "mapping_tool", "comment", "mapping_justification",
)  # fmt: skip
REVIEW_COLUMNS = (
    "subject_id", "predicate_id", "object_id", "mapping_justification",
    "reviewer_id", "reviewer_agreement", "review_seconds", "comment", "review_date",
)  # fmt: skip
PUBLISHED_COLUMNS = (
    "subject_id", "subject_label", "predicate_id", "object_id", "object_label",
    "reviewer_id", "comment", "mapping_justification",
)  # fmt: skip
PUBLISHED_META = {
    "mapping_set_id": "https://w3id.org/r9lab/vocabulary/r9lab-tags.sssom.tsv",
    "mapping_set_title": "R9lab material and keyword tags to R9lab vocabulary concepts",
    "license": "https://creativecommons.org/publicdomain/zero/1.0/",
}
ORCID = re.compile(r"orcid:\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def key(row: dict[str, str]) -> tuple[str, str, str]:
    """What a review row and a proposal share: subject, predicate and object."""
    return row["subject_id"], row["predicate_id"], row["object_id"]


def latest_verdicts(reviews: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, int]]:
    """Each mapping's verdict per rater, the rater's last row winning."""
    verdicts: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in reviews:
        verdicts.setdefault(key(row), {})[row["reviewer_id"]] = int(row["reviewer_agreement"])
    return verdicts


def build(meta: dict, predictions: list[dict[str, str]], reviews: list[dict[str, str]]) -> str:
    """The published file: each proposal no rater rejected, with the raters who agreed as `reviewer_id`.

    A proposal one rater agrees with and another rejects stays, with no reviewer, until the rater who
    rejected it changes their verdict; one that only drew rejections is left out.
    """
    verdicts = latest_verdicts(reviews)
    out = io.StringIO()
    header = {"curie_map": meta["curie_map"], **PUBLISHED_META}
    out.writelines(f"#{line}\n" for line in yaml.safe_dump(header, sort_keys=False).splitlines())
    w = csv.writer(out, delimiter="\t", lineterminator="\n")
    w.writerow(PUBLISHED_COLUMNS)
    for row in predictions:
        votes = verdicts.get(key(row), {})
        agree = sorted(r for r, v in votes.items() if v == 1)
        reject = any(v == -1 for v in votes.values())
        if reject and not agree:
            continue
        reviewers = "" if reject else "|".join(agree)
        out_row = row | {"reviewer_id": reviewers}
        w.writerow([out_row.get(c, "") for c in PUBLISHED_COLUMNS])
    return out.getvalue()


def read(path: Path) -> tuple[dict, list[str], list[dict[str, str]]]:
    """An SSSOM file's metadata, column names and rows."""
    meta, reader = read_sssom(path)
    rows = list(reader)
    return meta, list(reader.fieldnames or []), rows


def read_log(root: Path) -> tuple[dict, list[dict[str, str]], list[dict[str, str]], list[str]]:
    """The log's metadata, proposals and reviews, and what breaks its rules."""
    try:
        meta, pcols, predictions = read(root / PREDICTIONS)
        _, rcols, reviews = read(root / REVIEWS)
    except FileNotFoundError as e:
        return {}, [], [], [f"{e.filename}: missing"]
    errors = [f"{PREDICTIONS.name}: no {c} column" for c in PREDICTION_COLUMNS if c not in pcols]
    errors += [f"{REVIEWS.name}: no {c} column" for c in REVIEW_COLUMNS if c not in rcols]
    if not errors:
        errors = check_predictions(predictions) + check_reviews(reviews, {key(r) for r in predictions})
    return meta, predictions, reviews, errors


def check(root: Path = Path()) -> list[str]:
    """What breaks the review log's rules, and whether the published file is out of date."""
    meta, predictions, reviews, errors = read_log(root)
    if errors:
        return errors
    published = root / PUBLISHED
    if not published.exists() or published.read_text(encoding="utf-8") != build(meta, predictions, reviews):
        return [f"{PUBLISHED} is out of date: run `just curate`"]
    return []


def check_predictions(predictions: list[dict[str, str]]) -> list[str]:
    """A tag has one proposal, and it carries a machine justification.

    One per tag, because the published file may hold a tag once (`scheme.check_tag_mappings`).
    """
    errors, proposed, tags = [], set(), set()
    for row in predictions:
        where = f"{PREDICTIONS.name}: {row['subject_label']!r} -> {row['object_id']}"
        if key(row) in proposed:
            errors.append(f"{where} is proposed twice")
        elif row["subject_id"] in tags:
            errors.append(f"{where}: the tag already has a proposal")
        proposed.add(key(row))
        tags.add(row["subject_id"])
        if row["mapping_justification"] not in MACHINE:
            errors.append(f"{where}: {row['mapping_justification']!r} is not a machine justification")
    return errors


def check_reviews(reviews: list[dict[str, str]], proposed: set[tuple[str, str, str]]) -> list[str]:
    """A review names a proposal, an ORCID, an agreement of 1, -1 or 0, a date, and seconds if any."""
    errors = []
    for n, row in enumerate(reviews, start=1):
        where = f"{REVIEWS.name} row {n}"
        if key(row) not in proposed:
            errors.append(f"{where}: {row['subject_id']} -> {row['object_id']} is not a proposal")
        if not ORCID.fullmatch(row["reviewer_id"]):
            errors.append(f"{where}: reviewer_id {row['reviewer_id']!r} is not an ORCID CURIE")
        if row["reviewer_agreement"] not in ("1", "-1", "0"):
            errors.append(f"{where}: reviewer_agreement {row['reviewer_agreement']!r} is not 1, -1 or 0")
        if not is_date(row["review_date"]):
            errors.append(f"{where}: review_date {row['review_date']!r} is not YYYY-MM-DD")
        if row["review_seconds"] and not re.fullmatch(r"\d+(\.\d+)?", row["review_seconds"]):
            errors.append(f"{where}: review_seconds {row['review_seconds']!r} is not a number")
    return errors


def is_date(text: str) -> bool:
    """A real calendar date written YYYY-MM-DD."""
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return bool(DATE.fullmatch(text))


def write_published(root: Path = Path()) -> int:
    """Rewrite the published file from the log; leave it alone and print why if the log breaks a rule."""
    meta, predictions, reviews, errors = read_log(root)
    if errors:
        return fail(errors)
    (root / PUBLISHED).write_text(build(meta, predictions, reviews), encoding="utf-8")
    return 0


def report(root: Path = Path()) -> int:
    """Print what breaks a rule; 1 if anything does."""
    return fail(check(root))


def fail(errors: list[str]) -> int:
    """Print each error; 1 if there are any."""
    sys.stderr.writelines(f"error: {e}\n" for e in errors)
    return 1 if errors else 0


COMMANDS = {"build": write_published, "check": report}


def main(argv: list[str] | None = None) -> int:
    """`build` rewrites the published file from the log; `check` reports what breaks a rule."""
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "check"
    if command in COMMANDS:
        return COMMANDS[command]()
    sys.stderr.write(f"error: unknown command {command!r}; use build or check\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
