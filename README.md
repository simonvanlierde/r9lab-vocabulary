# r9lab-vocabulary

[![python](https://github.com/simonvanlierde/r9lab-vocabulary/actions/workflows/python.yml/badge.svg)](https://github.com/simonvanlierde/r9lab-vocabulary/actions/workflows/python.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/simonvanlierde/r9lab-vocabulary/badge)](https://scorecard.dev/viewer/?uri=github.com/simonvanlierde/r9lab-vocabulary)
[![Software Heritage](https://archive.softwareheritage.org/badge/origin/https://github.com/simonvanlierde/r9lab-vocabulary/)](https://archive.softwareheritage.org/browse/origin/?origin_url=https://github.com/simonvanlierde/r9lab-vocabulary)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

The R9lab reference vocabulary: product types and component and material classes for repair
and disassembly records, as SKOS, with crosswalks to CPC 2.1, UNU-KEYs, WEEE categories, PMDco,
Wikidata and BAFU.

Status: experimental. Concept ids are stable from v0.1.0 on; labels, mappings and the
product types may still change. The `https://w3id.org/r9lab/vocabulary/` IRIs do not resolve
yet: the redirect is waiting for review at w3id.org.

Questions and bugs: see [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## What is in it

Four SKOS concept schemes, written by hand in [`vocabulary/`](vocabulary/) and built into one
graph:

| Scheme | Concepts | Top level |
| --- | --- | --- |
| [Material classes](vocabulary/materials.yaml) | 59 | Ashby's six material families: metal, polymer, elastomer, glass, ceramic, hybrid |
| [Component classes](vocabulary/components.yaml) | 25 | Battery, lithium-ion cell, circuit boards, electronic components, display, cable, magnet, motor, transformer, loudspeaker driver |
| [Product types](vocabulary/products.yaml) | 33 | Six product families over 27 types, a first cut from the R9lab lab corpus |
| [Pilot classes](vocabulary/pilot-classes.yaml) | 11 | The eleven coarse material classes a pilot study sorts photographed parts into, kept as a `skos:Collection` |

Each concept maps (`skos:exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`,
`relatedMatch`) to the CPC 2.1 subclasses on [vocab.sentier.dev](https://vocab.sentier.dev),
PMDco v3.1.2, Wikidata and EU CPV codes. The CPV code is the one R9lab stores, padded to its 8
digits (R9lab's 302131 is `cpv:30213100`). Where a UNU-KEY covers a whole product type, the graph
records the edition and code as a typed literal such as `r9lab:unuKey "0303"^^r9lab:UNUKEYv1`
([ADR 0007](docs/decisions/0007-outside-codes-without-iris.md)). Each leaf product type has a
`broadMatch` to its category in Annex III to the WEEE Directive 2012/19/EU (`weee6:1` to
`weee6:6`), a fragment on the directive's ELI. Materials and components also
carry candidate patterns for names in outside lists that have no ids, such as BAFU activity
names (`names: {bafu: [...]}`). Each pattern is checked against every pinned version of its list,
today BAFU:2025 v2 and BAFU:2026 v1, and written out as `dist/name-matches.csv` with a match
count per version. A pattern is a Python regular expression matched case-insensitively anywhere
in the name (`re.search`).

[`mappings/r9lab-tags.sssom.tsv`](mappings/r9lab-tags.sssom.tsv) maps each R9lab
`Material:` or `Keyword:` tag, in lower case and typos included, to a concept, as
[SSSOM](https://mapping-commons.github.io/sssom/): `skos:exactMatch`, `closeMatch`, or
`broadMatch` when the tag is narrower than the concept. A tag with no concept maps to
`sssom:NoTermFound`. Each tag's `subject_id` is `r9lab-tag:`, the field it was typed in, and the
URL-encoded tag (`r9lab-tag:material/pc%2Babs`, under `https://w3id.org/r9lab/vocabulary/tags/`), so
"pc" as a material and as a product keyword are two tags ([ADR 0008](docs/decisions/0008-tag-ids-carry-their-field.md)).
A tag that could be one of several concepts, such as "rubber", maps with `broadMatch` to the concept
over all of them. Joined on `concept` with `dist/name-matches.csv`, it gives each
tag its BAFU activity names.

`just curate` builds that file from a review log in [`mappings/r9lab-tags/`](mappings/r9lab-tags/):

- `predictions.sssom.tsv` holds what machines proposed, with no reviewer.
- `reviews.sssom.tsv` gets one row per rater per verdict, and a rater's latest row counts.
- The built file keeps every proposal no rater rejected, with the raters who agreed in
  `reviewer_id`. A row with no reviewer is still a proposal, not a curated mapping.

[ADR 0005](docs/decisions/0005-mapping-review-log.md) says why it is a log, and
[`docs/review-protocol.md`](docs/review-protocol.md) how verdicts are counted.

Concept ids are opaque and never reused: a concept that goes away is marked `deprecated`,
with `replaced_by`, and stays in the file. The UNU-KEY names are under a non-commercial
licence, so only their codes are kept.

Each scheme, and the vocabulary as a whole (`https://w3id.org/r9lab/vocabulary/`, a
`dcat:Dataset` made of the schemes), says who made it, when, and which release it is, with a
version IRI such as `https://w3id.org/r9lab/vocabulary/0.1.0/materials/`.
[ADR 0004](docs/decisions/0004-versioned-iris-and-scheme-dates.md) lists the fields and where
each comes from.

## Usage

Each [release](https://github.com/simonvanlierde/r9lab-vocabulary/releases) carries the files
listed below, except `name-matches.csv`, plus `mappings/r9lab-tags.sssom.tsv`. Or build them:

```sh
just update      # fetch the pinned CPC 2.1, PMDco and BAFU files, then write dist/
just names       # print every name each pattern matches (--summary for counts)
just wikidata    # print every Wikidata link beside the item's current label
just diff v0.1.0 # what changed since a release, as Markdown for its notes
```

`just diff <tag>` reads `vocabulary/` at the tag and lists the concepts added, deprecated and
removed since, and those whose mappings or label changed. It exits 1 when a concept id at the
tag is gone: deprecate a concept with `replaced_by`, never delete it.

`just update` runs `just pipeline` and then `just rdf`, and prints how the match counts in
`dist/name-matches.csv` changed. `just rdf` alone needs the pipeline output. It writes:

- `dist/r9lab-vocabulary.ttl` and `dist/r9lab-vocabulary.jsonld`: the SKOS graph.
  `just pyst-round-trip` loads it into a throwaway [PyST](https://github.com/cauldron/py-semantic-taxonomy)
  in Docker, reads every scheme and concept back and fails on a statement lost or added.
  `tests/pyst/round_trip.py` says how the graph is reshaped for PyST's API.
- `dist/name-matches.csv`: each name pattern with its match count per version.
- `dist/r9lab.shacl.ttl`: the vocabulary's own SHACL shapes. Check a copy of the graph with
  `pyshacl -s r9lab.shacl.ttl r9lab-vocabulary.ttl`.
- `dist/r9lab-vocabulary.sssom.tsv`: every mapping as an [SSSOM](https://mapping-commons.github.io/sssom/)
  row, for tools that read crosswalks without parsing SKOS. `just sssom-validate` checks it
  with sssom-py. Mappings from or to a deprecated concept are left out; the SKOS graph keeps
  them. The file has no `mapping_date` column, because the YAML records no date per mapping.
  A UNU-KEY row is an SSSOM 1.0 literal mapping, with the code in `object_label` and no `object_id`.
- `dist/labels.json` and `dist/labels.md`: per scheme, each non-deprecated concept by id with
  its IRI, label, label path from its top concept, definition, and the keys of the pilot
  classes it falls under (`pilot`), plus the keys of every concept below it (`pilot_any`). A model prompt can quote them. `labels.json` also carries
  each scope note and example; the editorial note stays out. Evaluation answers are not kept
  in this repository.

The shapes require an English `prefLabel` and an `inScheme` on every concept, IRIs as mapping
targets, a replacement in use for a deprecated concept, and the release metadata above on every
scheme. The tests run them, with [skohub-shapes](https://github.com/skohub-io/skohub-shapes)'
SKOS rules (`tests/fixtures/skohub-skos.shacl.ttl`), on the graph `vocabulary/` builds.

`just rdf` refuses to write anything while a rule is broken: an unknown `broader`, a cycle,
a duplicate label, an `exactMatch` that is also a `broadMatch`, a CPC code or PMDco id
missing from the pinned files, a WEEE category other than 1 to 6, or a name pattern that matches no live name in a version.
The scheme slugs `tags` and `terms` are taken by other IRIs under the base.

Every `r9lab-vocabulary` command exits 0 on success and 1 on a broken rule, or for `wikidata` a
missing or redirected item. Exit 2 is a bad argument (an unknown `names --source`, a `diff` ref
with no `vocabulary/`), and 3 means the pipeline output is missing: run `just pipeline`.

### Review the tag mappings

`just review` runs with the `review` extra (FastAPI, uvicorn), and needs the raters' ORCID CURIEs
in `R9LAB_RATERS`, separated by commas:

```sh
R9LAB_RATERS=orcid:0000-0002-1825-0097,orcid:0000-0001-5109-3700 just review
```

It serves the page on 127.0.0.1:8740 and prints one link per rater. Each rater opens their own
link, which signs them in. A link stays the same across restarts. To revoke one rater, remove
their ORCID from `R9LAB_RATERS` and restart; to give every rater a new link, delete
`.review-secret` (gitignored). Ctrl-C stops the page and rebuilds the published file.

`just review-stack` runs the same page in Docker (`docker/review/compose.yaml`) with the checkout
mounted read-only except `mappings/`, so verdicts land in the log as before. It publishes on
127.0.0.1:8740 only. To let raters on other machines in, run a proxy on this host in front of
127.0.0.1:8740, such as `tailscale serve 8740`, a Cloudflare Tunnel or Caddy, and set:

- `R9LAB_ALLOWED_HOSTS`: the names the page is served under, separated by commas, such as
  `127.0.0.1,review.example.org`. Other names get a 400.
- `R9LAB_PUBLISH`: where Docker publishes the port, `127.0.0.1:8740` by default.

Each rater's link is the page's address followed by the `/r/...` path printed for them
(`docker compose` shows it in the stack's output): `http://127.0.0.1:8740` here, the proxy's
address for raters elsewhere. [`docs/review-protocol.md`](docs/review-protocol.md) has the rules
a rater follows.

### Write a concept's text

Each concept in `vocabulary/*.yaml` carries:

- `definition`: one sentence (`skos:definition`), with `source` naming where it comes from,
  as a URL or a citation such as `Ashby 2017, sec. 2.2` (`dcterms:source`).
- `example`: one string or a list (`skos:example`), things a record would name.
- `note`: what the concept leaves out and the nearest concept it is told apart from
  (`skos:scopeNote`).
- `editorial_note`: remarks for maintainers, such as a missing BAFU dataset
  (`skos:editorialNote`). It ships in the published graph, so write it for outside readers
  too; `labels.json` leaves it out.
- `hidden`: misspellings a record uses, as a list (`skos:hiddenLabel`), so search finds
  "trasformer" without showing it.

The vocabulary is CC0, so a definition is written in our own words: Ashby and IEC 60050
are cited, not quoted. Wikidata descriptions are CC0 and may be reused as they are.
`just rdf` refuses a concept in use that lacks one of the three texts.

### Sort a part

The notes follow these rules, and a new note must not break them:

- A part goes by the material that makes up most of its mass. That holds for filled grades
  too: PA66-GF30 is polyamide, but a silicone thermal pad that is mostly ceramic filler goes by the ceramic.
- A foam goes by its polymer when the record names it, and a metal foam goes by its metal.
- Glass-fibre reinforced polymer is for laminates and continuous-fibre or resin parts. Woven
  glass fabric is glass fibre, not textile.
- A plated part goes by its base metal, unless the record lists the plating on its own.
- Enamelled winding wire in a coil, motor or transformer goes by its metal, not cable.
- Ferrous means iron-based (Ashby). Stainless steel has at least 10.5 % chromium.
- Elastomers are their own family. "Polymer" means plastics.
- A battery is one or more cells fitted for use (IEC 60050-482). A bare cell cut from a pack
  is a lithium-ion cell. The pilot's battery class takes both.
- In the pilot, a ceramic part is "other", and a fabric that is mostly plastic by mass is
  "plastic".

### Suggested mappings

Every entry under `mappings:` is curated by a person, and the SSSOM file says so
(`semapv:ManualMappingCuration`, with the curator's ORCID). A mapping a model or matching tool
suggests never goes there. It goes in a separate SSSOM file under `suggestions/`, with the
tool's own justification (such as `semapv:LLMBasedMatching`), which the build does not read. A
person promotes a suggestion by checking it and copying it into `mappings:`.

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

## Proposals for review

- [Open Repair Data Standard crosswalk](docs/crosswalks/ords.md)
- [CIRPASS-2 Digital Product Passport crosswalk](docs/crosswalks/cirpass-2.md)
- [UNU-KEY and BAFU source checks](docs/crosswalks/source-checks.md)
- [PyST tag mappings](docs/decisions/0009-publish-tag-mappings-to-pyst.md) and [toolkit scope](docs/toolkit-scope.md)

`just crosswalk-check` validates the ORDS and CIRPASS-2 review tables. The
proposals have their own validation and stay outside the vocabulary release exports.

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

`just check` skips the tests that read the pipeline output when it is missing, and ends with
`curate check`, which fails on a broken review-log rule or an out-of-date tag file. `just test-full`
runs the pipeline first and then every test, as CI does.

The version in `pyproject.toml` goes into the version IRIs and both SSSOM files: after changing
it, run `just curate` to rewrite the tag file's header.

`tests/test_golden.py` pins the Turtle a small fixture in `tests/fixtures/golden/` builds to. After
a deliberate change to the output, rewrite it with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`
and read the diff.

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
Issues turned on for this repository. A source with a `sha256` pin in `sources.toml` (every
implemented one here) never reaches that issue: new bytes fail `just fetch` on every run, pull
requests included, and the weekly run opens or comments on a "Weekly pipeline run failed" issue
instead. Pin the new
hash once you have checked the revision.

## License

The code is under [Apache-2.0](LICENSE). The vocabulary in `vocabulary/` and the files built
from it are dedicated to the public domain under [CC0 1.0](LICENSES/CC0-1.0.txt).
[ATTRIBUTION.md](ATTRIBUTION.md) lists what it links to and on what terms.
