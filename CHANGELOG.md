# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Material classes topped by Ashby's six families, component classes, a first cut of product types, and the ten pilot material classes as a collection.
- Crosswalks to CPC 2.1, PMDco v3.1.2, Wikidata, UNU-KEY v1 codes and R9lab CPV codes, plus candidate patterns for BAFU activity names.
- `just rdf` checks the vocabulary and its CPC and PMDco links against pinned source files, then writes Turtle, JSON-LD and `name-matches.csv`. Each name pattern must match a live name in every pinned version of its list it applies to (BAFU:2025 v2 and BAFU:2026 v1).
- `mappings/r9lab-tags.sssom.tsv` maps the R9lab material and keyword tags (typos included) to concepts, or to `sssom:NoTermFound`, as SSSOM with a `r9lab-tag:` id per tag. `just rdf` refuses a duplicate tag, an unknown predicate or a missing or deprecated concept.
- The tag mappings are built from a review log in `mappings/r9lab-tags/`: machine proposals in `predictions.sssom.tsv`, and one row per rater per verdict in `reviews.sssom.tsv` (`reviewer_agreement`, `review_date`, `review_seconds`). `just curate` rebuilds `mappings/r9lab-tags.sssom.tsv`, which keeps its id and columns, and refuses a log that breaks a rule; `just check` fails on a broken log rule, a tag every rater rejected, or an out-of-date file, and warns about verdicts on a withdrawn proposal.
- `just review` serves a page on 127.0.0.1 for reviewing the tag mappings, one card at a time, blind to what proposed each one, and appends each verdict to the review log with the time it took; `docs/review-protocol.md` holds the rules. It needs the `review` extra (FastAPI, htmx) and the rater's ORCID in `R9LAB_REVIEWER`.
- `just names` prints every name each pattern matches, or with `--summary` the count per version.
- `just update` fetches, builds and checks everything and prints how the match counts changed; `just test-full` runs the tests as CI does.
- `just wikidata` lists every Wikidata link beside the item's current label and fails on a missing or redirected item.
- Concepts take an `example` (`skos:example`), an `editorial_note` (`skos:editorialNote`) and a `source` for the definition (`dcterms:source`); `note` stays the scope note. `just rdf` refuses a concept in use without a definition, an example and a scope note.
- Every concept has a definition with its source where one fits, examples and a scope note saying what it is told apart from. The README lists the sorting rules the notes follow. Remarks for maintainers, mapping caveats and UNU-KEY, WEEE and CPC codes sit in the editorial note, which stays out of model prompts.
- The pilot classes lost the short prompt glosses they carried; the pilot's prompt text stays in its registration. Plastic, rubber and battery link `narrow`, so their subtypes inherit the pilot key, and battery also takes a bare cell cut from a pack. The magnet class is labelled permanent magnet and maps to it; its key stays `magnet`.
- ABS, acrylic (PMMA) and acetal (POM) are labelled by the names people use, and primary cell is now primary battery, like its siblings. GPS navigation device sits under both telecommunications and audio and video equipment, and small household appliance takes in power strips.
- The weekly CI run checks every Wikidata link against the live API, so a merged or deleted item fails it.
- `just diff <tag>` lists the concepts added, deprecated, removed, remapped and relabelled since a release, as Markdown, and fails when a concept id was deleted instead of deprecated. It also lists a concept that was deprecated with no replacement or is no longer deprecated.
- Each scheme and the vocabulary as a whole (a `dcat:Dataset` of the schemes) say who made them, when, and which release they are, with a version IRI such as `https://w3id.org/r9lab/vocabulary/0.1.0/materials/`, and carry the fields PyST needs. `just rdf` takes the date from `SOURCE_DATE_EPOCH` when set.
- SHACL shapes, published as `r9lab.shacl.ttl` beside the graph: every concept has an English label and a scheme, mappings point at IRIs, a deprecated concept is replaced by one in use, and every scheme carries its release metadata. The tests run them with skohub-shapes' SKOS rules.
- `just rdf` also writes `r9lab-vocabulary.sssom.tsv`, every curated mapping as an SSSOM row with its curator's ORCID; `just sssom-validate` and CI check it with sssom-py. Mappings a tool suggests stay in a separate file until a person promotes them.
- Pilot keys now reach the non-ferrous metals, ceramics, natural materials, foams and composites, so aluminium, copper, a ceramic insulator, leather, cork, a foam pad and FR-4 each carry one. A new pilot class, electric motor or transformer (`motor_transformer`), takes whole motors and mains transformers, and a whole loudspeaker driver counts as permanent magnet.
- `just rdf` also writes `labels.json` and `labels.md`: each non-deprecated concept with its label, ancestor path, definition and pilot classes, as text for model prompts. `labels.json` also carries each concept's scope note and examples, but never its editorial note. Each concept's `pilot_any` lists the pilot keys of every concept below it, so a coarse answer such as "metal" can be scored.
- Each product type links (`broadMatch`) to its WEEE Directive category, `weee6:1` to `weee6:6`, derived from its UNU-KEY. `just rdf` refuses any other `weee6` code.
- Each product type with a UNU-KEY v1 code also links to its UNU-KEY v2 code (`unu2:`), from the 2026 E-waste Statistics Guidelines. `just rdf` refuses a `unu1` or `unu2` code that is not in that edition's key list.
- A `lithium-ion cell` component (c0024), related to `lithium-ion battery`, takes the BAFU "Battery cell, ..." datasets.

### Changed

- `just build` can reuse BAFU activity names from an unchanged archive. [The data directory](data/README.md) explains how to clear the local cache.
- `lithium-ion battery` now matches battery packs only, including "Battery, rechargeable, prismatic, LiNCM"; the cells moved to `lithium-ion cell`.
- The BAFU patterns for wood, polystyrene and liquid-crystal display no longer match cement-bonded particle board, polystyrene scrap or the 17-inch LCD monitor.
- GPS navigation device is UNU-KEY 0402 (WEEE category 5), not 0305 (category 6), and radio is 0402 (v2: 0403), not 0201, as the guidelines' key descriptions and HS tables place them.
- Laptop charger is UNU-KEY 0201 (WEEE category 5), not 0301, because the 0201 description lists adapters: where a key description names a product, it wins over the HS and CPC tables. Graphics card is 0301, the nearest key for a PC part, not 0302 (desktops).
- Steel, stainless steel, aluminium and copper no longer match the BAFU sheet-rolling and wire-drawing services.

### Fixed

- `just check` now rejects a notation written as `1` and as `"1"`, a `replaced_by` that points at the concept itself or at a deprecated concept, and a concept with an empty body (reported as "no label" instead of crashing).
- `just rdf`, `just names`, `just wikidata` and `just diff` print an `error:` line and exit 1, instead of a traceback or a silent pass, for a folder with no `vocabulary/*.yaml`, a file that is not valid YAML or has no `scheme` slug or `concepts` mapping, a missing `mappings/r9lab-tags.sssom.tsv` or a short row in it. A pilot class with `notation: null` is keyed by its id in `labels.json`, not "None".

[Unreleased]: https://github.com/simonvanlierde/r9lab-vocabulary/commits/HEAD
