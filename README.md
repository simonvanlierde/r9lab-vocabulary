# r9lab-vocabulary

[![python](https://github.com/simonvanlierde/r9lab-vocabulary/actions/workflows/python.yml/badge.svg)](https://github.com/simonvanlierde/r9lab-vocabulary/actions/workflows/python.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/simonvanlierde/r9lab-vocabulary/badge)](https://scorecard.dev/viewer/?uri=github.com/simonvanlierde/r9lab-vocabulary)
[![Software Heritage](https://archive.softwareheritage.org/badge/origin/https://github.com/simonvanlierde/r9lab-vocabulary/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/simonvanlierde/r9lab-vocabulary)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Status: experimental. Concept ids are stable from v0.1.0 on; labels, mappings and the
product types may still change.

Questions and bugs: see [CONTRIBUTING.md](.github/CONTRIBUTING.md).

R9lab reference vocabulary: product types and component and material classes as SKOS, with crosswalks to CPC 2.1, UNU-KEYs, Wikidata and BAFU

## What is in it

Four SKOS concept schemes, written by hand in [`vocabulary/`](vocabulary/) and built into one
graph:

| Scheme | Concepts | Top level |
| --- | --- | --- |
| [Material classes](vocabulary/materials.yaml) | 58 | Ashby's six material families: metal, polymer, elastomer, glass, ceramic, hybrid |
| [Component classes](vocabulary/components.yaml) | 24 | Battery, lithium-ion cell, circuit boards, electronic components, display, cable, magnet, motor, transformer, loudspeaker driver |
| [Product types](vocabulary/products.yaml) | 33 | Six product families over 27 types, a first cut from the R9lab lab corpus |
| [Pilot classes](vocabulary/pilot-classes.yaml) | 10 | The ten coarse material classes a photo study scores, kept as a `skos:Collection` |

Each concept maps (`skos:exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`,
`relatedMatch`) to the CPC 2.1 subclasses on [vocab.sentier.dev](https://vocab.sentier.dev),
PMDco v3.1.2, Wikidata, and to UNU-KEY v1 and v2 and R9lab CPV codes. Each product type also has a
`broadMatch` to its category in Annex III to the WEEE Directive 2012/19/EU (`weee6:1` to
`weee6:6`), a fragment on the directive's ELI. Materials and components also
carry candidate patterns for names in outside lists that have no ids, such as BAFU activity
names (`names: {bafu: [...]}`). Each pattern is checked against every pinned version of its list,
today BAFU:2025 v2 and BAFU:2026 v1, and written out as `dist/name-matches.csv` with a match
count per version. A pattern is a Python regular expression matched case-insensitively anywhere
in the name (`re.search`).

Concept ids are opaque and never reused: a concept that goes away is marked `deprecated`,
with `replaced_by`, and stays in the file. Licensed code lists (UNU-KEYs) are linked by code
only; none of their names is copied.

## Usage

Get the built files from the [releases](https://github.com/simonvanlierde/r9lab-vocabulary/releases),
or build them:

```sh
just update      # fetch the pinned CPC 2.1, PMDco and BAFU files, then write dist/
just names       # print every name each pattern matches (--summary for counts)
just wikidata    # print every Wikidata link beside the item's current label
```

`just update` runs `just pipeline` and then `just rdf`, and prints how the match counts in
`dist/name-matches.csv` changed. `just rdf` alone needs the pipeline output. It writes
`dist/r9lab-vocabulary.ttl`, the same graph as JSON-LD, and `dist/name-matches.csv`.

`just rdf` refuses to write anything while a rule is broken: an unknown `broader`, a cycle,
a duplicate label, an `exactMatch` that is also a `broadMatch`, a CPC code or PMDco id
missing from the pinned files, a WEEE category other than 1 to 6, or a name pattern that matches no live name in a version.

### Write a concept's text

Each concept in `vocabulary/*.yaml` carries:

- `definition`: one sentence (`skos:definition`), with `source` naming where it comes from,
  as a URL or a citation such as `Ashby 2017, sec. 2.2` (`dcterms:source`).
- `example`: one string or a list (`skos:example`), things a record would name.
- `note`: what the concept leaves out and the nearest concept it is told apart from
  (`skos:scopeNote`).
- `editorial_note`: remarks for maintainers, such as a missing BAFU dataset
  (`skos:editorialNote`).

The vocabulary is CC0, so a definition is written in our own words: Ashby and IEC 60050
are cited, not quoted. Wikidata descriptions are CC0 and may be reused as they are.
Concepts still without the three texts are listed in `tests/pending-text.txt`, and the tests
fail on any other concept that lacks one.

### Add a version of a name list

A source whose id is `<family>-<version>` is one version of a name list, such as
`bafu-2026-v1`.

1. Add a `[[source]]` block to `sources.toml` with that id, its URL and its terms. Leave
   `sha256` empty for the first fetch, then pin the hash it prints.
2. Run `just update`. Each pattern that no longer matches is reported by concept and version.
3. Fix those patterns. A pattern for a name only some versions use is written
   `{pattern: '...', versions: [2026-v1]}`.
4. Run `just names --source <id>` and read the new matches.

A new family, such as an ecoinvent release, also needs a reader in `NAME_LISTS` in
`src/r9lab_vocabulary/pipeline.py`.

## Development

You need [uv](https://docs.astral.sh/uv/) and [just](https://just.systems).

```sh
uv sync
uv tool install prek==0.5.7   # once per machine, the version CI uses
prek install     # git hooks
```

`just` lists the tasks. They mirror what [.github/workflows/](.github/workflows/) runs.

```sh
just check       # lint, types and tests for every stack here
just fmt         # apply each stack's fixes and formatting
just hooks       # the git hooks, as the checks workflow runs them
just pipeline    # fetch, build and validate every source in sources.toml
just data-release   # write the folder to publish: the redistributable data, datapackage.json, SHA256SUMS
```

`just check` skips the tests that read the pipeline output when it is missing. `just test-full`
runs the pipeline first and then every test, as CI does.

## Pipeline

[`sources.toml`](sources.toml) declares every input: its URL, its reuse
terms, and whether the pipeline reads it yet (`status`). `just fetch` downloads each
implemented source to `data/raw/` with a fetch record. `just build` writes
`data/processed/<id>.parquet` with zstd compression and an explicit string schema.
The project-wide `output_format` in `sources.toml` selects Parquet; set it to `"csv"` for CSV.
`just validate` checks the published output against the fetch
records. Neither directory goes into git. `just data-release` writes `release/` for publishing and `just data-release-check` checks it. [ATTRIBUTION.md](ATTRIBUTION.md) lists what
this repository reuses, and on what terms.

Commit `data/fetches.jsonl` after a fetch that changes it: it holds checksums, not
data, and is the history of every version of each source. Once a week, CI fetches again
and comments on a "Source data revised upstream" issue when a source changed, so keep
Issues turned on for this repository.

## License

The code is under [Apache-2.0](LICENSE). The vocabulary in `vocabulary/` and the files built
from it are dedicated to the public domain under [CC0 1.0](LICENSES/CC0-1.0.txt).
[ATTRIBUTION.md](ATTRIBUTION.md) lists what it links to and on what terms.
