---
status: accepted
date: 2026-11-26
---

# Tag mappings built from a review log

## Context and Problem Statement

Machines propose the mappings from R9lab tags to concepts, and people check them. Each verdict
should keep who proposed the mapping, with what, who reviewed it, and how long that took.
Agreement between raters is reported, so two raters' verdicts on one mapping must both survive.
Readers of `mappings/r9lab-tags.sssom.tsv` must keep its id and columns.

## Considered Options

* `reviewer_id` filled in by hand in the published file
* SSSOM Curator's four files (`predictions`, `positive`, `negative`, `unsure`)
* An append-only review log: proposals in one file, one row per rater per verdict in another,
  and the published file built from both

## Decision Outcome

Chosen: the review log, in `mappings/r9lab-tags/`. `predictions.sssom.tsv` holds machine rows
only. `reviews.sssom.tsv` gets one row per rater per verdict, with SSSOM 1.1's
`reviewer_agreement` and `review_date` and a `review_seconds` extension. `just curate` builds the
published file, which keeps its `mapping_set_id`, columns and justifications.

Hand edits keep one reviewer per row and lose the time a verdict took. Curator's four files put
each mapping in one file, so they hold one verdict, and its accept rewrites the justification to
`ManualMappingCuration` and drops the tool, which loses what proposed the mapping.

### Consequences

* Good: a verdict never overwrites a proposal or another rater's verdict, so agreement between
  raters and acceptance per proposer can be counted from the files.
* Good: with no reviews, the built file is byte-identical to the hand-made one it replaces.
* Bad: sssom-py 0.4.22 reads `reviewer_agreement` and `review_date` but drops the
  `review_seconds` extension, and its schema does not yet list `semapv:AgentBasedMatching`, so
  `sssom validate` reports every machine row. The log's own rules run in `just check` instead.
* Bad: the published file is generated, so a hand edit to it fails `just check`.
* Bad: a rejection takes the tag out of the published file, so `just check` fails until the tag
  gets a new proposal. The old proposal's verdicts stay in the log, unused, with a warning.
