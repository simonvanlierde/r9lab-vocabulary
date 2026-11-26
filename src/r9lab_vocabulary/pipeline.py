"""Fetch, build and validate the reference sources, then build the vocabulary from them.

The source stages come from sourceledger: each download gets a fetch record, and every
output row names the bytes it came from (see https://github.com/simonvanlierde/sourceledger).
What is this project's own is `parse`, which reads each raw file, and the `rdf`, `names` and
`wikidata` commands, which turn `vocabulary/*.yaml` into SKOS, list what each name pattern
matches, and check its Wikidata links.

A name list is a source whose id is `<family>-<version>` (`bafu-2026-v1`) for a family in
`NAME_LISTS`. Supporting a new family means one reader here; a new version of a known
family is one more `[[source]]` block.
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
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, cast

import rdflib
import sourceledger
import yaml
from sourceledger import Source

from r9lab_vocabulary import scheme

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

VOCABULARY = Path("vocabulary")
DIST = Path("dist")
CITATION = Path("CITATION.cff")  # its first author curates every mapping
PROCESSED = Path("data/processed")
USER_AGENT = "r9lab-vocabulary (https://github.com/simonvanlierde/r9lab-vocabulary)"
CPC_SOURCE, PMDCO_SOURCE, WIKIDATA = "cpc21", "pmdco", "wd"
NAME_COLUMNS = ["code", "name", "location"]
IMPLEMENTED = "implemented"
XML_CHUNK = 8192  # bytes fed per step; parsing stops at the first chunk holding the whole head
REF = "referenceFunction"
HEAD = {REF: "name", "geography": "location"}  # EcoSpold1 tag -> attribute


def ecospold1_head(data: bytes) -> tuple[str, str] | None:
    """(name, location) of an EcoSpold1 process, read from its head only.

    Both sit in `processInformation`, before the exchanges that make up most of the file,
    so parsing stops there (about half the build time on BAFU:2026).
    """
    # The archive is pinned by SHA-256, and expat since 2.6 caps entity expansion.
    parser = ET.XMLPullParser(events=("start",))
    found: dict[str, str] = {}
    for i in range(0, len(data), XML_CHUNK):
        parser.feed(data[i : i + XML_CHUNK])
        for _, el in cast("Iterator[tuple[str, ET.Element]]", parser.read_events()):
            tag = el.tag.rpartition("}")[2]
            if tag in HEAD and tag not in found:
                found[tag] = el.get(HEAD[tag], "")
        if len(found) == len(HEAD):
            break
    if REF not in found:
        return None
    return found[REF], found.get("geography", "")


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
                head = ecospold1_head(z.read(member))
                if head is None:
                    msg = f"{member}: no referenceFunction"
                    raise ValueError(msg)
                code = Path(member).stem.removeprefix("process_")
                rows.append({"code": code, "name": head[0], "location": head[1]})
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
            return [dict(zip(NAME_COLUMNS, (r or "" for r in row), strict=True)) for row in con.execute(query)]
        finally:
            con.close()


@dataclass(frozen=True)
class NameList:
    """A family of versioned name lists: how to read one version, and which names are live."""

    read: Callable[[bytes], list[dict[str, str]]]
    live: Callable[[str], bool]


NAME_LISTS = {
    # BAFU marks a withdrawn dataset by prefixing its name with "xx" or "xxx".
    "bafu": NameList(parse_bafu, lambda name: not name.lower().startswith("xx")),
}


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
    if (family := source["id"].partition("-")[0]) in NAME_LISTS:
        return NAME_COLUMNS, NAME_LISTS[family].read(payload)
    return sourceledger.parse_source(source, payload)


def known_codes() -> dict[str, set[str]]:
    """The CPC codes and PMDco ids in the processed sources; error if they were not built."""
    paths = {"cpc": PROCESSED / "cpc21.parquet", "pmdco": PROCESSED / "pmdco.parquet"}
    if missing := [str(p) for p in paths.values() if not p.exists()]:
        msg = f"{', '.join(missing)} missing; run `just pipeline` first"
        raise FileNotFoundError(msg)
    return {
        "cpc": {r["code"] for r in sourceledger.read_output(paths["cpc"])},
        "pmdco": {r["id"] for r in sourceledger.read_output(paths["pmdco"])},
    }


def name_lists() -> dict[str, dict[str, list[str]]]:
    """Family -> version -> live names, for every name-list source in sources.toml; error if one was not built."""
    ids = [
        s["id"]
        for s in sourceledger.load_manifest()
        if s["id"].partition("-")[0] in NAME_LISTS and s.get("status") == IMPLEMENTED
    ]
    paths = {i: PROCESSED / f"{i}.parquet" for i in ids}
    if missing := [str(p) for p in paths.values() if not p.exists()]:
        msg = f"{', '.join(missing)} missing; run `just pipeline` first"
        raise FileNotFoundError(msg)
    lists: dict[str, dict[str, list[str]]] = {}
    for i, path in paths.items():
        family, _, ver = i.partition("-")
        live = NAME_LISTS[family].live
        lists.setdefault(family, {})[ver] = [r["name"] for r in sourceledger.read_output(path) if live(r["name"])]
    return lists


def _versions(lists: dict[str, dict[str, list[str]]]) -> dict[str, set[str]]:
    return {family: set(vs) for family, vs in lists.items()}


def rdf(out: Path) -> int:
    """Check the vocabulary against itself and the pinned sources, then write it to `out`."""
    schemes = scheme.load(VOCABULARY)
    try:
        known = known_codes()
        lists = name_lists()
        errors = scheme.validate(schemes, _versions(lists)) + scheme.check_codes(schemes, known)
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        return 3
    if errors:  # a broken pattern would not compile below
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    matches = scheme.name_matches(schemes, lists)
    errors = [
        f"{slug}/{cid}: {family} pattern {pattern!r} matches no live name in {family}-{ver}"
        for slug, cid, family, ver, pattern, hits in matches
        if not hits
    ]
    if errors:
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    ver = version("r9lab-vocabulary")
    author = yaml.safe_load(CITATION.read_text(encoding="utf-8"))["authors"][0]["orcid"]
    paths = [*scheme.write(schemes, ver, out, matches), scheme.write_sssom(schemes, ver, out, author)]
    sys.stdout.writelines(f"{path}\n" for path in paths)
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


def names(source: str | None, *, summary: bool) -> int:
    """Print each name a `names` pattern matches, or with --summary each pattern's count per source."""
    try:
        lists = name_lists()
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        return 3
    if source is not None:
        family, _, ver = source.partition("-")
        if ver not in lists.get(family, {}):
            known = ", ".join(f"{f}-{v}" for f, vs in sorted(lists.items()) for v in sorted(vs))
            sys.stderr.write(f"error: no name-list source {source!r}; known: {known}\n")
            return 2
    schemes = scheme.load(VOCABULARY)
    if errors := scheme.validate(schemes, _versions(lists)):
        sys.stderr.writelines(f"error: {e}\n" for e in errors)
        return 1
    if source is not None:
        lists = {family: {ver: lists[family][ver]}}
    for slug, cid, family, ver, pattern, hits in scheme.name_matches(schemes, lists):
        if summary:
            sys.stdout.write(f"{slug}/{cid}\t{family}-{ver}\t{len(hits)}\t{pattern}\n")
        else:
            sys.stdout.writelines(f"{slug}/{cid}\t{family}-{ver}\t{pattern}\t{name}\n" for name in hits)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run one stage: `fetch|build|validate` (sourceledger), `rdf [--out DIR]`, `names [...]` or `wikidata`."""
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["rdf"]:
        p = argparse.ArgumentParser(prog="r9lab-vocabulary rdf", description=rdf.__doc__)
        p.add_argument("--out", type=Path, default=DIST, help="output directory (default: dist)")
        return rdf(p.parse_args(args[1:]).out)
    if args[:1] == ["wikidata"]:
        return wikidata()
    if args[:1] == ["names"]:
        p = argparse.ArgumentParser(prog="r9lab-vocabulary names", description=names.__doc__)
        p.add_argument("--source", help="one name-list source, such as bafu-2026-v1 (default: all)")
        p.add_argument("--summary", action="store_true", help="one line per pattern and source, with its match count")
        a = p.parse_args(args[1:])
        return names(a.source, summary=a.summary)
    return sourceledger.main(args, parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


def entry() -> NoReturn:
    """The `r9lab-vocabulary` command."""
    if sys.argv[1:2] in (["rdf"], ["wikidata"], ["names"]):
        sys.exit(main())
    sourceledger.entry(parse=parse, prog="r9lab-vocabulary", user_agent="r9lab-vocabulary")


if __name__ == "__main__":
    entry()
