---
status: accepted
date: 2026-11-26
---

# WEEE category IRIs as fragments on the directive's ELI

## Context and Problem Statement

Product types link (`broadMatch`) to the six categories of Annex III to Directive
2012/19/EU (WEEE). Neither the EU Publications Office nor anyone else publishes an IRI per
category, and the Official Journal text has a single `anx_III` anchor for the whole annex.
The `weee6` prefix still needs IRIs that name one category each and that a reader can
follow to the law.

## Considered Options

* Fragments on the directive's ELI: `http://data.europa.eu/eli/dir/2012/19/oj#anx_III-<n>`
* Mint the categories under the vocabulary's own base, as for `unu1`, with labels and
  `rdfs:seeAlso` to the ELI
* ELI subdivision IRIs, `http://data.europa.eu/eli/dir/2012/19/anx_III/pnt_<n>/oj`

## Decision Outcome

Chosen: fragments on the ELI, `weee6:<n>` for `<n>` from 1 to 6. The IRI resolves to the
directive and says which annex and point it means, and `validate` refuses any other code.
The `anx_III-<n>` fragments are coined here: the OJ text has no anchor below `anx_III`, so a
browser lands on the directive, not on the category.

The vocabulary's own base would add six concepts to maintain for a link outside readers can
already follow. The subdivision IRIs put the point number in the middle of the path, so they
cannot be built by prefix concatenation, and they were not checked to resolve.

### Consequences

* Good: each link points at the legal text, with no extra concepts to maintain.
* Bad: the fragments are ours, not the EU's; nothing guarantees another dataset uses the same ones.
* Bad: costly to change after the first tag, since outside data may store these IRIs.
  Revisit if the EU publishes IRIs for the categories.

### Confirmation

The `weee6` tests check the IRI a link builds (`tests/test_export.py`) and the codes
`validate` refuses (`tests/test_checks.py`).
