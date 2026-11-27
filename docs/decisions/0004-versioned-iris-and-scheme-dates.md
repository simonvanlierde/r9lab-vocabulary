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
version as a group, can send the whole prefix to that release's files. The version takes the
path segment right after the base, where scheme slugs also sit. A version starts with a digit and
`just rdf` refuses a slug that does not start with a lower-case letter, so the two never collide.

The version-specific rule is pending. The registered w3id rule sends everything under the base to the
repository, so a version IRI resolves to the repository, not to its release. Adding the
per-release rule is a follow-up once the first release is tagged.

* `dct:created` is the `created` date in each scheme's YAML: the date of the commit that added
  the file. The vocabulary node takes the earliest of them.
* `dct:modified` is `SOURCE_DATE_EPOCH` when set, else the date of the commit built (`git log
  -1` in the package's own checkout, never in a repository around it), not the build date, so
  two builds of one commit are the same files. With neither, `just rdf` stops with an error,
  because the shapes require the date.
* `dct:creator` and `dct:publisher` are the ORCID iDs of the authors in `CITATION.cff`, and
  `dcat:landingPage` its `repository-code`, so the build repeats no fact `CITATION.cff` holds.
  The publisher is the first author only.
* Each also carries `dct:title` and `dct:language`, is typed `schema:DefinedTermSet` with its
  title as `schema:name` for dataset search, and, for PyST, has a `skos:definition` and
  `bibo:status` accepted, as every concept does.

### PyST and releases

PyST's examples load each release of a vocabulary as its own concept scheme. Here the concept
IRIs carry no version, by design: a concept IRI must stay the same across releases to stay
persistent, and only the scheme's `owl:versionIRI` names the release. PyST keys schemes and
concepts by IRI and answers a second create with 409, so one PyST holds one release of each
scheme. A new release updates that PyST in place; older releases stay in the GitHub releases.
`just pyst-round-trip` loads a release into an empty PyST; the update path is not scripted yet.

### Consequences

* Good: one redirect rule covers every versioned IRI of a release.
* Bad: until the per-release w3id rule exists, the version IRIs resolve to the repository, not
  to the release.
* Bad: a PyST shows only the release last loaded into it.
* Bad: a build of uncommitted edits carries the date of the last commit.

### Confirmation

`tests/test_golden.py` pins the metadata a fixture builds to, and `tests/test_shacl.py` runs the
shapes in `shapes/r9lab.shacl.ttl` on every scheme of the real build.
