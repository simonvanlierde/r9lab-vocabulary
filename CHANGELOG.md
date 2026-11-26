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
- `just diff <tag>` lists the concepts added, deprecated, removed, remapped and relabelled since a release, as Markdown, and fails when a concept id was deleted instead of deprecated.
- Each scheme and the vocabulary as a whole say who made and publishes them (ORCID), when they were created and last changed, their language and landing page, and a version IRI per release, such as `https://w3id.org/r9lab/vocabulary/0.1.0/materials/`. The vocabulary is a `dcat:Dataset` and `schema:DefinedTermSet` of its schemes.

[Unreleased]: https://github.com/simonvanlierde/r9lab-vocabulary/commits/HEAD
