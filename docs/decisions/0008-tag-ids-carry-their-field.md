---
status: accepted
date: 2026-11-26
---

# Tag ids carry the field the tag was typed in

## Context and Problem Statement

An R9lab tag is a line in a part's description, `Material: PC` or `Keyword: Laser Module`. The same
letters can mean different things in different fields: "PC" in a `Material:` line is polycarbonate,
and as a product keyword it would be a personal computer. A tag mapping needs that context, and
SSSOM has no place for it: a mapping is always true, with no condition, and two rows for one subject
mean both, not one of them (SSSOM's interpretation of one-to-many mappings,
[sssom#540](https://github.com/mapping-commons/sssom/issues/540)). Tag ids are published in
`mappings/r9lab-tags.sssom.tsv`, so they must be fixed before the first release.

## Considered Options

* Keep one id per tag, `r9lab-tag:pc`, and record the field in a comment or an extension column
* One id per field and tag, `r9lab-tag:material/pc`, each with its own plain SSSOM row
* XKOS conditional concept associations (tag plus field to concept), as PyST models them

## Decision Outcome

Chosen: one id per field and tag. The subject is `r9lab-tag:` plus `material/` or `keyword/` plus
the URL-encoded tag, under `https://w3id.org/r9lab/vocabulary/tags/`. Each row stays true on its
own, so any SSSOM tool reads it correctly. A tag typed in both fields gets two rows, which map alike
when the tag means the same in both.

A comment or extension column would leave the context out of the key, so a tool that joins on
`subject_id` would merge the two meanings. XKOS associations exist in PyST but are its own reading
of XKOS, with no field for review metadata, so they can be a published view of this file later, not
its source.

A tag that could be one of several concepts, as "rubber" is natural or synthetic, maps with
`skos:broadMatch` to the concept that covers them all, here elastomer. Rows to each narrower concept
would claim the tag is both.

### Consequences

* Good: ambiguous tags get separate mappings, and the context is in the key every tool joins on.
* Bad: a tag typed in both fields is reviewed twice, and a new R9lab field needs a new prefix here
  and in `checks.TAG_FIELDS`.
