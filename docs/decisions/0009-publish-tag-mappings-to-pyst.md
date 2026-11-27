---
status: proposed
date: 2026-11-27
---

# Publish reviewed tag mappings to PyST

## Context and Problem Statement

A PyST client should be able to look up a concept given an R9lab tag and the field
it came from. The [release workflow](../../.github/workflows/release.yml) packages
field-qualified mapping subjects as SSSOM
([ADR 0008](0008-tag-ids-carry-their-field.md)). PyST stores a tag and a field as
the two source concepts in one association. PyST's XKOS convention treats them
as a joint condition. [PyST data model](https://docs.pyst.dev/data-model/#conditional-conceptassociation)

## Considered Options

- Serve the released SSSOM file and let each client resolve the field-qualified ID.
- Publish SKOS links from field-qualified tag concepts in PyST.
- Publish conditional PyST associations derived from the released SSSOM.

## Proposed Decision

Use the conditional associations as a read-only view of a vocabulary release.
The [review log](0005-mapping-review-log.md) records verdicts. The released SSSOM
holds the predicate and reviewer attribution for each published mapping.

1. Read the tag SSSOM and SKOS graph from the same release. Require
   `mapping_set_version` and the graph's `owl:versionInfo` to agree with the tag
   version, omitting its leading `v`. Validate subject IDs, unique subjects,
   and live target IRIs before loading. Publish rows with a nonempty
   `reviewer_id` and a concept target. That column records at least one agreement
   and no rejection. Blank reviewers and `sssom:NoTermFound` produce no
   association.
2. Create a tag-string concept for each eligible normalized label and a field
   concept for each allowed field. Use separate schemes for the tag strings and
   the fields. Keep their lookup IDs distinct from the field-qualified subjects
   in ADR 0008. Under the vocabulary base, use `pyst/strings/<sha256>`,
   where the digest is over the UTF-8 tag after trimming and lowercasing.
   Use `pyst/fields/<field>` for the field.
3. Create one correspondence per target scheme. Set `xkos:compares` to the tag,
   field and target schemes. Set `owl:versionInfo` to the release version and
   `dcterms:references` to the tag SSSOM asset. Give each eligible row an
   association with the tag and field as the two `xkos:sourceConcept` values and
   the vocabulary concept as its single `xkos:targetConcept`. An eligible
   `r9lab-tag:material/pc` row gives the source pair `pc` and `material`, with
   `materials:m0026` as the target. The correspondence is
   `pyst/correspondences/<target scheme slug>`. Append a slash and the SHA-256
   of the expanded SSSOM subject IRI to get the association ID.
4. Load schemes, concepts and vocabulary relationships, then correspondences
   and associations. Send expanded JSON-LD. Add the association IDs to each
   correspondence with a separate `POST /api/v1/made_ofs/` call using
   `xkos:madeOf`. The correspondence create request rejects that property.
   Read back the linked associations and compare their source pairs and targets
   with the input.

Use the correspondence IRI, tag-string IRI and `kind=conditional` to filter
`GET /api/v1/associations/`. The pinned API filters on one source IRI. Clients
must require exactly the two source IDs in the unordered tag-and-field pair,
require a single target, and look across the target correspondences. Zero
matches means no reviewed link in this release. Multiple matches for a pair
mean the view is inconsistent.
Keep the relation and reviewer evidence in the release's SSSOM. Association
membership alone gives no match strength.
[Pinned PyST API](https://github.com/cauldron/py-semantic-taxonomy/blob/57ac3fe616e8831d8d252f377fd6ffbfa62635f6/src/py_semantic_taxonomy/adapters/routers/api_router.py) ·
[Pinned PyST association model](https://github.com/cauldron/py-semantic-taxonomy/blob/57ac3fe616e8831d8d252f377fd6ffbfa62635f6/src/py_semantic_taxonomy/domain/entities.py)

## Release and recovery

[ADR 0004](0004-versioned-iris-and-scheme-dates.md) keeps vocabulary IRIs stable.
PyST keys objects by IRI and returns 409 on duplicate creation. Build the view
in an empty, isolated PyST database and verify it before making it visible.
Promote the endpoint together with a release manifest giving the version and
the versioned SSSOM asset URL and SHA-256. Keep the preceding endpoint and
manifest available for rollback. Each endpoint serves one snapshot, so a
client can keep using the same release throughout a lookup.

A retry can rebuild the same snapshot from the same assets. A revised snapshot
has only the eligible rows from its release, so withdrawn rows fall away.
If the host cannot stage and switch snapshots, keep serving the versioned
SSSOM until an operator has verified an update and recovery path.

## Consequences

Clients can look up a tag within its original field. They join against the
versioned SSSOM to recover the mapping strength and provenance. Consumers of
generic XKOS need PyST's convention to interpret the source pair.

## Confirmation

The [PyST round trip](../../tests/pyst/round_trip.py) checks the same synthetic
tag in two fields with different targets, correspondence membership, and the
SSSOM reference URL.

The [local staging prototype](../../tests/pyst/stage_tags.py) checks both asset
digests and the release versions before it writes to PyST. Its input
`release.json` has `version` (without `v`), `graph_sha256`, `tags_sha256`, and
the versioned `tags_url`. Take the digests from the release files you intend
to stage. Start a fresh disposable PyST at the endpoint supplied to `stage`.

```sh
uv run python tests/pyst/stage_tags.py stage r9lab-vocabulary.ttl r9lab-tags.sssom.tsv release.json staged.json --url http://127.0.0.1:8741
uv run python tests/pyst/stage_tags.py activate staged.json active.json
```

The staged manifest appears only after the vocabulary, correspondence
membership, and field-qualified lookups agree with the input. `activate`
recomputes the fingerprint from the stored release metadata, endpoint URL
and live graph before it replaces the local pointer. Keep both staged manifests and their servers running during a
local rollback rehearsal. Pass the earlier staged manifest to `activate` to
restore it. The prototype uses loopback and the disposable stack's token.

Before publishing, agree on the host, switch and rollback procedure. Rehearse
a failed load and a rollback through the real client-facing endpoint.
