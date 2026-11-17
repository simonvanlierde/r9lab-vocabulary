"""Fetch, build and validate the reference sources, then build the vocabulary from them.

The source stages come from sourceledger: each download gets a fetch record, and every
output row names the bytes it came from (see https://github.com/simonvanlierde/sourceledger).
What is this project's own is `parse`, which reads each raw file, and the `rdf` and
`wikidata` commands, which turn `vocabulary/*.yaml` into SKOS and check its Wikidata links.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.parse
import urllib.request
from importlib.metadata import version
from pathlib import Path
from typing import NoReturn

import rdflib
import sourceledger
from sourceledger import Source

from r9lab_vocabulary import scheme

VOCABULARY = Path("vocabulary")
DIST = Path("dist")
PROCESSED = Path("data/processed")
USER_AGENT = "r9lab-vocabulary (https://github.com/simonvanlierde/r9lab-vocabulary)"
CPC_SOURCE, PMDCO_SOURCE, WIKIDATA = "cpc21", "pmdco", "wd"


def parse(source: Source, payload: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """One raw file as its columns and rows."""
    if source["id"] == CPC_SOURCE:
        # The UNSD structure file is Latin-1 with CRLF line ends.
        rows = csv.DictReader(io.StringIO(payload.decode("latin-1"), newline=""))
        return ["code", "title"], [{"code": r["CPC21code"], "title": r["CPC21title"]} for r in rows]
    if source["id"] == PMDCO_SOURCE:
        g = rdflib.Graph().parse(data=payload, format="turtle")
        prefix = scheme.PREFIXES["pmdco"]
        labels = {
            str(s): str(o)
            for s, o in g.subject_objects(rdflib.RDFS.label)
            if str(s).startswith(prefix) and getattr(o, "language", None) in {"en", None}
        }
        return ["id", "label"], [{"id": s.removeprefix(prefix), "label": labels[s]} for s in sorted(labels)]
    return sourceledger.parse_source(source, payload)


def known_codes() -> dict[str, set[str]]:
    """The CPC codes and PMDco ids in the processed sources; error if they were not built."""
    paths = {"cpc": PROCESSED / "cpc21.parquet", "pmdco": PROCESSED / "pmdco.parquet"}
    if missing := [str(p) for p in paths.values() if not p.exists()]:
        msg = f"{', '.join(missing)} missing; run `just fetch build` first"
        raise FileNotFoundError(msg)
    return {
        "cpc": {r["code"] for r in sourceledger.read_output(paths["cpc"])},
        "pmdco": {r["id"] for r in sourceledger.read_output(paths["pmdco"])},
    }


def rdf(out: Path) -> int:
    """Check the vocabulary against itself and the pinned sources, then write it to `out`."""
    schemes = scheme.load(VOCABULARY)
    try:
        errors = scheme.validate(schemes) + scheme.check_codes(schemes, known_codes())
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        return 3
    if errors:
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    for path in scheme.write(schemes, version("r9lab-vocabulary"), out):
        sys.stdout.write(f"{path}\n")
    return 0


def wikidata_labels(qids: list[str]) -> dict[str, str | None]:
    """The English label of each QID; None for one that is missing or now redirects elsewhere."""
    labels: dict[str, str | None] = {}
    for i in range(0, len(qids), 50):
        batch = qids[i : i + 50]
        query = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "labels",
                "languages": "en|mul",
                "format": "json",
            }
        )
        req = urllib.request.Request(f"https://www.wikidata.org/w/api.php?{query}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            entities = json.load(r)["entities"]
        for qid in batch:
            e = entities.get(qid, {})
            ok = e.get("id") == qid and e.get("labels") is not None  # a missing item has no labels
            # Many items keep their English name only as the language-neutral `mul` label.
            names = e.get("labels", {})
            labels[qid] = (names.get("en") or names.get("mul") or {}).get("value", "") if ok else None
    return labels


def wikidata() -> int:
    """Print each concept beside the Wikidata label of every item it maps to; fail on a dead or redirected QID."""
    schemes = scheme.load(VOCABULARY)
    links = [
        (s.slug, cid, c["label"], rel, local)
        for s in schemes.values()
        for cid, c in s.concepts.items()
        for rel, prefix, local in scheme.mappings(c)
        if prefix == WIKIDATA
    ]
    labels = wikidata_labels(sorted({link[4] for link in links}))
    bad = 0
    for slug, cid, label, rel, qid in links:
        found = labels[qid]
        bad += found is None
        shown = found if found is not None else "MISSING OR REDIRECTED"
        sys.stdout.write(f"{slug}/{cid}\t{label}\t{rel}\t{qid}\t{shown}\n")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    """Run one stage: `fetch|build|validate` (sourceledger), `rdf [--out DIR]` or `wikidata`."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["rdf"]:
        p = argparse.ArgumentParser(prog="r9lab-vocabulary rdf", description=rdf.__doc__)
        p.add_argument("--out", type=Path, default=DIST, help="output directory (default: dist)")
        return rdf(p.parse_args(args[1:]).out)
    if args[:1] == ["wikidata"]:
        return wikidata()
    return sourceledger.main(args, parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


def entry() -> NoReturn:
    """The `r9lab-vocabulary` command."""
    if sys.argv[1:2] in (["rdf"], ["wikidata"]):
        sys.exit(main())
    sourceledger.entry(parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


if __name__ == "__main__":
    entry()
