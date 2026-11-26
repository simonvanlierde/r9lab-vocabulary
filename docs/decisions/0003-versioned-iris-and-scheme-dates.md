---
status: accepted
date: 2026-11-26
---

# Version IRIs under the base, dates from the sources and git

## Context and Problem Statement

FAIR checkers and dataset search read who made a vocabulary, when, and which release it is.
Each scheme needs an `owl:versionIRI`, and its shape is published: once a release carries it,
changing it breaks every link to that release. The dates must be true and the build must
write the same files from the same commit.

## Considered Options

* Version IRIs per scheme: `<scheme>/<version>/`
* Version IRIs per release: `https://w3id.org/r9lab/vocabulary/<version>/<scheme>/`
* `dct:modified` as the build date, or as the date of the commit built

## Decision Outcome

Chosen: per release. `owl:versionIRI` is `https://w3id.org/r9lab/vocabulary/<version>/` plus the
scheme's path, such as `.../0.1.0/materials/`. One w3id rule per release, or one rule with the
version as a group, can send the whole prefix to that release's files. Concept ids start with a
letter, so a version path never collides with a concept IRI.

* `dct:created` is the `created` date in each scheme's YAML: the date of the commit that added
  the file. The vocabulary node and the code-only schemes take the earliest of them.
* `dct:modified` is the date of the commit built (`git log -1`), not the build date, so two
  builds of one commit are the same files. Outside a git checkout it is left out.
* `dct:creator` and `dct:publisher` are the ORCID iDs of the authors in `CITATION.cff`, and
  `dcat:landingPage` its `repository-code`, so the build repeats no fact `CITATION.cff` holds.

### Consequences

* Good: one redirect rule covers every versioned IRI of a release.
* Bad: until the w3id redirect is registered, the version IRIs do not resolve.
* Bad: a build of uncommitted edits carries the date of the last commit.

### Confirmation

`tests/test_scheme.py` checks the metadata on the built graph, and the SHACL shapes in
`shapes/r9lab.shacl.ttl` on every scheme of every build.
