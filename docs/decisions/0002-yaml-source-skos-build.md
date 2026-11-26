---
status: accepted
date: 2026-11-17
---

# Hand-written YAML, built into SKOS, with links checked against pinned sources

## Context and Problem Statement

R9lab needs one reference vocabulary for product types, component classes and material
classes that the app, py-semantic-taxonomy (PyST), a photo study and an alias reviewer can
all read. People edit it; machines consume it. Each outside identifier it links to has to
exist, and licensed code lists may not be copied.

## Considered Options

* Edit Turtle or JSON-LD by hand
* Edit the concepts in PyST or another SKOS editor and export
* Write one YAML file per scheme and build the RDF from it

## Decision Outcome

Chosen: one YAML file per scheme, built into one SKOS graph by `just rdf`. YAML diffs read
well in review and carry comments; the build adds the inverse links (`narrower`,
`hasTopConcept`) so they cannot drift.

* Concept ids are opaque (`m0001`), never reused; a concept that goes away is deprecated with
  `replaced_by`.
* Concept IRIs sit under `https://w3id.org/r9lab/vocabulary/`, so they survive a move of the
  repository or a change of host. The w3id redirect still has to be registered.
* CPC codes and PMDco ids are checked against files pinned by checksum in `sources.toml`;
  Wikidata ids against the live API by `just wikidata`.
* UNU-KEY codes are kept as codes only, since their names are CC BY-NC-SA. How they and the
  CPV codes are published is in [ADR 0007](0007-outside-codes-without-iris.md).
* BAFU activities have no IRIs, so the BAFU link is a list of name patterns written out as a
  CSV, not RDF. Each version of a name list is its own pinned source (`bafu-2026-v1`), read for
  names only, and every pattern must match a live name in each version it applies to. A
  pattern can be scoped to some versions, so one file follows the annual releases without
  forking, and another list without ids (an ecoinvent release) is one more reader.

### Consequences

* Good: every outside id in a release has been checked against a named version of its source.
* Good: PyST, sensebank and the app read the same built files.
* Bad: nobody can edit the vocabulary in a SKOS editor and round-trip it; edits go through the YAML.
* Bad: until the w3id redirect is registered, the concept IRIs do not resolve.

### Confirmation

`just check` runs the rule tests on the real files; after `just pipeline`, the published-data
tests check every CPC code and PMDco id against the pinned files.
