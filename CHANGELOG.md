# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Four SKOS concept schemes: 58 material classes under Ashby's six families, 24 component classes, 33 product types, and the eleven coarse material classes of a pilot study as a collection. Concept ids are stable: a concept that goes away is deprecated with `replaced_by`, never deleted. See [What is in it](README.md#what-is-in-it).
- Typed crosswalks from each concept to CPC 2.1, PMDco v3.1.2, Wikidata and EU CPV codes, and from each product type to its WEEE Directive category and its UNU-KEY v1 and v2 codes ([ADR 0007](docs/decisions/0007-outside-codes-without-iris.md)). Materials and components also carry patterns for BAFU activity names, checked against BAFU:2025 v2 and BAFU:2026 v1.
- Every concept in use has a definition with its source, examples and a scope note; the README lists the [sorting rules](README.md#sort-a-part) the notes follow.
- Each GitHub release carries the SKOS graph as Turtle and JSON-LD, every mapping as SSSOM, the vocabulary's SHACL shapes, and `labels.json` and `labels.md`, each concept's text and pilot keys for model prompts. See [Usage](README.md#usage).
- Each scheme and the vocabulary as a whole carry who made them, when, and which release they are, with a version IRI such as `https://w3id.org/r9lab/vocabulary/0.1.0/materials/` ([ADR 0004](docs/decisions/0004-versioned-iris-and-scheme-dates.md)).
- `mappings/r9lab-tags.sssom.tsv` maps the R9lab material and keyword tags, typos included, to concepts. It is built from a [review log](docs/decisions/0005-mapping-review-log.md) of machine proposals and raters' verdicts, by `just curate`.
- `just review` serves a page on this machine for rating the tag mappings one blind card at a time, following the [review protocol](docs/review-protocol.md).
- `just rdf` and `just check` refuse a broken vocabulary before anything is written: an unknown link, a cycle, a duplicate label or notation, a code missing from the pinned source files, a mapping to a deprecated concept, or a concept in use without its texts.
- `just names` prints what each BAFU pattern matches, `just wikidata` lists each Wikidata link beside the item's current label, and `just diff <tag>` lists what changed since a release and fails when a concept id was deleted.

[Unreleased]: https://github.com/simonvanlierde/r9lab-vocabulary/commits/HEAD
