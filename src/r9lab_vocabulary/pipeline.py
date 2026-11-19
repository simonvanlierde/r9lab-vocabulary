"""Fetch, build and validate the reference sources, then build the vocabulary from them.

The source stages come from sourceledger: each download gets a fetch record, and every
output row names the bytes it came from (see https://github.com/simonvanlierde/sourceledger).
What is this project's own is `parse`, which reads each raw file, and the `rdf`, `bafu` and
`wikidata` commands, which turn `vocabulary/*.yaml` into SKOS, list what each BAFU pattern
matches, and check its Wikidata links.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sqlite3
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
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
BAFU_SOURCE = "bafu-"  # id prefix: one source per release, `bafu-2026-v1`
BAFU_COLUMNS = ["code", "name", "location"]
IMPLEMENTED = "implemented"


def parse_bafu(payload: bytes) -> list[dict[str, str]]:
    """Each activity of a BAFU release as code, name and location. Amounts are never read.

    Takes either packaging the release comes in: an EcoSpold1 zip (one process per XML
    file, as FOEN publishes it) or a Brightway project archive (names in `lci/databases.db`).
    """
    if zipfile.is_zipfile(io.BytesIO(payload)):
        rows = []
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for member in sorted(z.namelist()):
                if not member.endswith(".xml"):
                    continue
                # The archive is pinned by SHA-256, and expat since 2.6 caps entity expansion.
                root = ET.fromstring(z.read(member))  # noqa: S314
                ref, geo = root.find(".//{*}referenceFunction"), root.find(".//{*}geography")
                if ref is None:
                    msg = f"{member}: no referenceFunction"
                    raise ValueError(msg)
                code = Path(member).stem.removeprefix("process_")
                rows.append(
                    {
                        "code": code,
                        "name": ref.get("name", ""),
                        "location": "" if geo is None else geo.get("location", ""),
                    }
                )
        return rows
    with tarfile.open(fileobj=io.BytesIO(payload)) as t, tempfile.TemporaryDirectory() as tmp:
        members = [m for m in t.getmembers() if m.name.endswith("/lci/databases.db")]
        f = t.extractfile(members[0]) if len(members) == 1 else None
        if f is None:
            msg = f"expected one lci/databases.db in the Brightway project archive, found {len(members)}"
            raise ValueError(msg)
        db = Path(tmp) / "databases.db"
        with db.open("wb") as out:
            shutil.copyfileobj(f, out)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            query = (
                "SELECT code, name, location FROM activitydataset"
                " WHERE type IN ('process', 'processwithreferenceproduct') ORDER BY code"
            )
            return [dict(zip(BAFU_COLUMNS, (r or "" for r in row), strict=True)) for row in con.execute(query)]
        finally:
            con.close()


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
    if source["id"].startswith(BAFU_SOURCE):
        return BAFU_COLUMNS, parse_bafu(payload)
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


def bafu_names() -> dict[str, list[str]]:
    """The activity names of each BAFU release in sources.toml, keyed as the YAML keys them (`2026-v1`)."""
    ids = [
        s["id"]
        for s in sourceledger.load_manifest()
        if s["id"].startswith(BAFU_SOURCE) and s.get("status") == IMPLEMENTED
    ]
    paths = {i: PROCESSED / f"{i}.parquet" for i in ids}
    if missing := [str(p) for p in paths.values() if not p.exists()]:
        msg = f"{', '.join(missing)} missing; run `just fetch build` first"
        raise FileNotFoundError(msg)
    return {i.removeprefix(BAFU_SOURCE): [r["name"] for r in sourceledger.read_output(p)] for i, p in paths.items()}


def rdf(out: Path) -> int:
    """Check the vocabulary against itself and the pinned sources, then write it to `out`."""
    schemes = scheme.load(VOCABULARY)
    try:
        known = known_codes()
        names = bafu_names()
        errors = scheme.validate(schemes, set(names)) + scheme.check_codes(schemes, known)
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        return 3
    if errors:  # a broken pattern would not compile below
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    matches = scheme.bafu_matches(schemes, names)
    errors = [
        f"{slug}/{cid}: bafu pattern {pattern!r} matches no live activity in BAFU {release}"
        for slug, cid, release, pattern, hits in matches
        if not hits
    ]
    if errors:
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    for path in scheme.write(schemes, version("r9lab-vocabulary"), out, matches):
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


def bafu(release: str | None) -> int:
    """Print every activity each `bafu` pattern matches, to review what a pattern catches."""
    try:
        names = bafu_names()
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        return 3
    if release is not None and release not in names:
        sys.stderr.write(f"error: no BAFU release {release!r}; known: {', '.join(names)}\n")
        return 2
    schemes = scheme.load(VOCABULARY)
    if errors := scheme.validate(schemes, set(names)):
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    wanted = names if release is None else {release: names[release]}
    for slug, cid, rel, pattern, hits in scheme.bafu_matches(schemes, wanted):
        sys.stdout.writelines(f"{slug}/{cid}\t{rel}\t{pattern}\t{name}\n" for name in hits)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one stage: `fetch|build|validate` (sourceledger), `rdf [--out DIR]`, `bafu [--release R]` or `wikidata`."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["rdf"]:
        p = argparse.ArgumentParser(prog="r9lab-vocabulary rdf", description=rdf.__doc__)
        p.add_argument("--out", type=Path, default=DIST, help="output directory (default: dist)")
        return rdf(p.parse_args(args[1:]).out)
    if args[:1] == ["wikidata"]:
        return wikidata()
    if args[:1] == ["bafu"]:
        p = argparse.ArgumentParser(prog="r9lab-vocabulary bafu", description=bafu.__doc__)
        p.add_argument("--release", help="one release, such as 2026-v1 (default: all)")
        return bafu(p.parse_args(args[1:]).release)
    return sourceledger.main(args, parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


def entry() -> NoReturn:
    """The `r9lab-vocabulary` command."""
    if sys.argv[1:2] in (["rdf"], ["wikidata"], ["bafu"]):
        sys.exit(main())
    sourceledger.entry(parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


if __name__ == "__main__":
    entry()
