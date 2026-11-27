# Vocabulary publication audit

## Graph and validation

The 2026-11-27 audit ran on the Turtle built by `just rdf` from commit
`45be82a` and again after the metadata changes below. The build had four
schemes and 128 concepts. No export records were sent to a validator.

| Check | Before | After |
| --- | --- | --- |
| VocPub 5.4 | 144 violations, 121 warnings | 1 violation, 4 warnings |
| Published SKOS integrity conditions | No inconsistencies found | No inconsistencies found |
| HTML and Turtle requests to a concept IRI | Repository HTML for both | [ADR 0009](decisions/0009-resolve-vocabulary-iris.md) proposes the serving change |

Run the [pinned VocPub validator][validator] with pySHACL 0.40.2 and advanced
features enabled.

```sh
just rdf
pyshacl -a -s validator.ttl -f turtle dist/r9lab-vocabulary.ttl
```

The validator SHA-256 is
`98d61d950c43786444fdd5453221ce02fdc4378bd86eedfe5731c2282f226820`.
The remaining violation is the limit of one concept scheme per file, reported
as 2.1.02 and 2.1.03. The four warnings concern the origin of the pilot
collection and three concepts without a source citation. The collection gets
its content from the containing scheme. Concept citations need a credible
reference for the particular definition.

The metadata changes add defining-scheme links, the collection definition
and membership in its scheme, named and typed creators, scheme provenance,
a repository link, and machine-readable citations derived from the concept
sources already present.

The SKOS pass checked S9, S13, S14, S27, S35, S37 and S46 on the merged graph
and W3C schema after OWL RL inference. That covers disjoint classes and
labels, preferred labels per language, association versus hierarchy,
ordered collection membership lists, and exact mappings that also assert
incompatible relations. The existing SHACL test also runs SkoHub's shapes.
Its collection rule treats the subject of `skos:inScheme` as a concept or
scheme. SKOS leaves that property's subject unconstrained. The test removes
that trigger and the local shapes check S37 against the actual types.
[W3C SKOS Reference][skos]

## Ten FAIR vocabulary rules

| Rule | Evidence or remaining work |
| --- | --- |
| 1. Custodianship | The contribution guide identifies the maintainer and GitHub review process. |
| 2. Licensing | The graph and tag mappings declare CC0. [ATTRIBUTION.md](../ATTRIBUTION.md) records upstream terms and limits on redistribution. |
| 3. Term completeness | Every live concept has a definition, example and note. Tag and part gaps in R9lab records need their own review. |
| 4. Traceable maintenance | The YAML, mapping review log, issues and decisions have Git history. |
| 5. Persistent identifiers | Concepts have opaque w3id IRIs. Version IRIs are documented in [ADR 0004](decisions/0004-versioned-iris-and-scheme-dates.md). |
| 6. Machine-readable terms | The build emits SKOS Turtle and JSON-LD, with SSSOM for mappings. The release workflow builds these formats from the tracked sources. |
| 7. Vocabulary metadata | The graph has licensing, creator, publisher, version, dates, language, and repository metadata. The audit adds defining relationships and provenance. |
| 8. Registration and preservation | Confirm a public vocabulary catalogue entry and a versioned DOI deposit when publishing the first release. The w3id registration provides the identifier namespace. |
| 9. Human and machine access | Both Accept requests reached repository HTML in the live check. Concept and version resolution is in [ADR 0009](decisions/0009-resolve-vocabulary-iris.md). |
| 10. Revision publication | The release workflow builds immutable assets, and `just diff` checks concept removal. Keeping superseded terms and versions resolvable needs the proposed public routing. |

[Cox et al., Ten simple rules for making a vocabulary FAIR][fair]

[validator]: https://raw.githubusercontent.com/AGLDWG/vocpub-profile/9d78dad42c69d4efbb3c048f4026b3a63018f44e/validators/validator.ttl
[skos]: https://www.w3.org/TR/skos-reference/
[fair]: https://doi.org/10.1371/journal.pcbi.1009041
