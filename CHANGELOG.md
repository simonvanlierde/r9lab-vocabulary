# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Material classes topped by Ashby's six families, component classes, a first cut of product types, and the ten pilot material classes as a collection.
- Crosswalks to CPC 2.1, PMDco v3.1.2, Wikidata, UNU-KEY v1 codes and R9lab CPV codes, plus candidate patterns for BAFU activity names.
- `just rdf` checks the vocabulary and its CPC and PMDco links against pinned source files, then writes Turtle, JSON-LD and `name-matches.csv`. Each name pattern must match a live name in every pinned version of its list it applies to (BAFU:2025 v2 and BAFU:2026 v1).
- `just names` prints every name each pattern matches, or with `--summary` the count per version.
- `just update` fetches, builds and checks everything and prints how the match counts changed; `just test-full` runs the tests as CI does.
- `just wikidata` lists every Wikidata link beside the item's current label and fails on a missing or redirected item.
- The weekly CI run checks every Wikidata link against the live API, so a merged or deleted item fails it.
- `just rdf` also writes `r9lab-vocabulary.sssom.tsv`, every curated mapping as an SSSOM row with its curator's ORCID; `just sssom-validate` and CI check it with sssom-py. Mappings a tool suggests stay in a separate file until a person promotes them.
- `just rdf` also writes `labels.json` and `labels.md`: each non-deprecated concept with its label, ancestor path, definition and pilot classes, as text for model prompts.
- Each product type links (`broadMatch`) to its WEEE Directive category, `weee6:1` to `weee6:6`, derived from its UNU-KEY. `just rdf` refuses any other `weee6` code.
- Each product type with a UNU-KEY v1 code also links to its UNU-KEY v2 code (`unu2:`), from the 2026 E-waste Statistics Guidelines. `just rdf` refuses a `unu1` or `unu2` code that is not in that edition's key list.
- A `lithium-ion cell` component (c0024), related to `lithium-ion battery`, takes the BAFU "Battery cell, ..." datasets.

### Changed

- `lithium-ion battery` now matches battery packs only, including "Battery, rechargeable, prismatic, LiNCM"; the cells moved to `lithium-ion cell`.
- The BAFU patterns for wood, polystyrene and liquid-crystal display no longer match cement-bonded particle board, polystyrene scrap or the 17-inch LCD monitor.
- GPS navigation device is UNU-KEY 0402 (WEEE category 5), not 0305 (category 6), and radio is 0402 (v2: 0403), not 0201, as the guidelines' key descriptions and HS tables place them.
- Steel, stainless steel, aluminium and copper no longer match the BAFU sheet-rolling and wire-drawing services.

### Fixed

- `just check` now rejects a notation written as `1` and as `"1"`, a `replaced_by` that points at the concept itself or at a deprecated concept, and a concept with an empty body (reported as "no label" instead of crashing).

[Unreleased]: https://github.com/simonvanlierde/r9lab-vocabulary/commits/HEAD
