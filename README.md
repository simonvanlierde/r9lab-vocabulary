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
| [Component classes](vocabulary/components.yaml) | 23 | Battery, circuit boards, electronic components, display, cable, magnet, motor, transformer, loudspeaker driver |
| [Product types](vocabulary/products.yaml) | 33 | Six product families over 27 types, a first cut from the R9lab lab corpus |
| [Pilot classes](vocabulary/pilot-classes.yaml) | 10 | The ten coarse material classes a photo study scores, kept as a `skos:Collection` |

Each concept maps (`skos:exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`,
`relatedMatch`) to the CPC 2.1 subclasses on [vocab.sentier.dev](https://vocab.sentier.dev),
PMDco v3.1.2, Wikidata, and to UNU-KEY v1 and R9lab CPV codes. Materials and components also
carry candidate patterns for BAFU activity names, checked against BAFU:2025 v2 and BAFU:2026 v1
and written out as `dist/bafu-candidates.csv` with a match count per release.

Concept ids are opaque and never reused: a concept that goes away is marked `deprecated`,
with `replaced_by`, and stays in the file. Licensed code lists (UNU-KEYs) are linked by code
only; none of their names is copied.

## Usage

Get the built files from the [releases](https://github.com/simonvanlierde/r9lab-vocabulary/releases),
or build them:

```sh
just vocab       # fetch the pinned CPC 2.1, PMDco and BAFU files, then write dist/
just bafu        # print every BAFU activity each pattern matches
just wikidata    # print every Wikidata link beside the item's current label
```

`just rdf` refuses to write anything while a rule is broken: an unknown `broader`, a cycle,
a duplicate label, an `exactMatch` that is also a `broadMatch`, a CPC code or PMDco id
missing from the pinned files, or a BAFU pattern that matches no live activity in a release.
To follow a new BAFU release, add it to `sources.toml` as `bafu-<year>-v<n>`; a pattern for a
name only some releases use is written `{pattern: '...', releases: [2026-v1]}`. It writes `dist/r9lab-vocabulary.ttl`, the same graph as
JSON-LD, and `dist/bafu-candidates.csv`.

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
