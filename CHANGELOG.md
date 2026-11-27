# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The SKOS export identifies the scheme that defines each concept and collection,
  names its creators, and includes source citations in schema.org format.
- Citation metadata describes the tag mapping and its review log.
- BAFU plug activities now map to electrical connector. Cable keeps its cable activities.

### Added

- Thirty component classes cover unmapped R9lab tags and recurring hardware, assemblies and controls. The tag proposals include scope checks for ambiguous labels.
- Four SKOS concept schemes: 59 material classes under Ashby's six families, 55 component classes, 33 product types, and the eleven coarse material classes of a pilot study as a collection. Concept ids are stable: a concept that goes away is deprecated with `replaced_by`, never deleted. Misspellings that records use are hidden labels (`skos:hiddenLabel`), found by search but never shown. See [What is in it](README.md#what-is-in-it).
- Typed crosswalks from each concept to CPC 2.1, PMDco v3.1.2, Wikidata and EU CPV codes, and from each product type to its WEEE Directive category and its UNU-KEY v1 and v2 codes ([ADR 0007](docs/decisions/0007-outside-codes-without-iris.md)). Materials and components also carry patterns for BAFU activity names, checked against BAFU:2025 v2 and BAFU:2026 v1.
- Every concept in use has a definition with its source, examples and a scope note; the README lists the [sorting rules](README.md#sort-a-part) the notes follow.
- Each GitHub release carries the SKOS graph as Turtle and JSON-LD, every mapping as SSSOM, the vocabulary's SHACL shapes, and `labels.json` and `labels.md`, each concept's text and pilot keys for model prompts. See [Usage](README.md#usage).
- Each scheme and the vocabulary as a whole carry who made them, when, and which release they are, with a version IRI such as `https://w3id.org/r9lab/vocabulary/0.1.0/materials/` ([ADR 0004](docs/decisions/0004-versioned-iris-and-scheme-dates.md)).
- `mappings/r9lab-tags.sssom.tsv` maps the R9lab material and keyword tags, typos included, to concepts. A tag's id carries the field it was typed in, so "pc" as a material and as a product keyword can map apart ([ADR 0008](docs/decisions/0008-tag-ids-carry-their-field.md)). It is built from a [review log](docs/decisions/0005-mapping-review-log.md) of machine proposals and raters' verdicts, by `just curate`.
- `just review` serves a page for rating the tag mappings one blind card at a time, following the [review protocol](docs/review-protocol.md). Each rater signs in with their own link, and `just review-stack` runs the page in Docker for a proxy of your choice to serve.
- `just rdf` and `just check` refuse a broken vocabulary before anything is written: an unknown link, a cycle, a duplicate label or notation, a code missing from the pinned source files, a mapping to a deprecated concept, or a concept in use without its texts.
- `just pyst-round-trip` loads the built graph into a throwaway [PyST](https://github.com/cauldron/py-semantic-taxonomy) in Docker and fails on any scheme or concept statement that does not come back.
- `just names` prints what each BAFU pattern matches, `just wikidata` lists each Wikidata link beside the item's current label, and `just diff <tag>` lists what changed since a release and fails when a concept id was deleted.

[Unreleased]: https://github.com/simonvanlierde/r9lab-vocabulary/commits/HEAD
