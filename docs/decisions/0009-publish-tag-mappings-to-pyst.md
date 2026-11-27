---
status: proposed
date: 2026-11-27
---

# Publish reviewed tag mappings to PyST

## Context and Problem Statement

A PyST client should be able to look up a concept given an R9lab tag and the field
it came from. The release already carries field-qualified subjects in SSSOM
([ADR 0008](0008-tag-ids-carry-their-field.md)). PyST can represent the tag and
field as two source concepts in a conditional XKOS association. PyST interprets
that pair as a joint condition and documents this as its own XKOS convention.
[PyST data model](https://docs.pyst.dev/data-model/#conditional-conceptassociation)

## Considered Options

- Serve the released SSSOM file and let each client resolve the field-qualified ID.
- Publish SKOS links from field-qualified tag concepts in PyST.
- Publish conditional PyST associations derived from the released SSSOM.

## Proposed Decision

Use the conditional associations as a read-only view of a vocabulary release.
Keep the [review log](0005-mapping-review-log.md) and generated SSSOM authoritative
for the predicate, provenance and verdicts.

1. Read the release's SSSOM and target schemes together. Take live concept
   targets with a nonempty `reviewer_id`. The file also contains unreviewed
   or disputed proposals with blank reviewers. Skip those and
   `sssom:NoTermFound`. Reject malformed subjects or missing target IDs.
2. Decode each field-qualified subject using the same normalization as the
   vocabulary. Create one tag concept per distinct normalized tag and one field
   concept per allowed field. Give these publication concepts their own scheme
   paths so existing SSSOM subject IRIs retain their meaning.
3. Create a correspondence per target scheme, comparing the tag, field and
   target schemes. Create one association per eligible row with the tag and field
   as its two `xkos:sourceConcept` values and the R9lab IRI as its single
   `xkos:targetConcept`. For example, the two sources for
   `r9lab-tag:material/pc` are `pc` and `material`, and the target is
   `materials:m0026` when that row has an agreeing reviewer.
4. Derive association IDs deterministically from the existing SSSOM subject ID
   within the target scheme's correspondence. Expose the release version,
   SSSOM URL and SHA-256 with the view. Clients needing the relation or reviewer
   can rebuild the SSSOM key from the pair and join against that release.
   Association membership alone gives no exact-match guarantee.

Load the schemes and concepts before the correspondences and associations.
Stage and read back a complete release before exposing it. Switch the public
view only after validation, and retain the previous release for rollback.
A repeated load of the same release must expose the same associations. A revised
release must retire links that lost their eligible verdict or target.

## Consequences

Clients can resolve the tag with its field through PyST. They need the versioned
SSSOM for the mapping's strength and evidence. Consumers of generic XKOS need to
know PyST's two-source convention to interpret the links.

## Confirmation

Extend the existing [PyST round trip](../../tests/pyst/round_trip.py) for
correspondences and associations before publishing. Test an eligible row, the
same tag in two fields with distinct targets, a broad match, and unreviewed,
disputed and no-term rows. Read back both source IDs, the target, and the
release pointer. Test repeat publication, target changes, withdrawals and a
failed staged load. The current round trip exercises the vocabulary graph.
