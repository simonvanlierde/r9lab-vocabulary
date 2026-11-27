---
status: accepted
date: 2026-11-26
---

# Outside codes: the owner's IRIs, or typed literals, never IRIs minted here

## Context and Problem Statement

Product types link to applicable UNU-KEY v1 and v2 codes and to the CPV code R9lab stores for them. Before
v0.1.0 the build minted a concept for each code used, under `https://w3id.org/r9lab/vocabulary/external/`.
Those IRIs would name someone else's codes from our domain, be permanent once released, and
duplicate the CPV IRIs the EU already publishes.

## Considered Options

* Mint code-only concepts under the vocabulary's base (the old build)
* Link the owner's IRIs where there are some, and write the rest as typed literals
* Register the code lists in a public registry (Bioregistry, identifiers.org) to get IRIs

## Decision Outcome

Chosen: the owner's IRIs where they exist, typed literals otherwise.

* CPV: R9lab stores a CPV code with its trailing zeros cut. Padded to 8 digits it is the EU's own
  code, so the mapping targets `http://data.europa.eu/cpv/cpv/<8 digits>` (`cpv:`). All 21 codes
  in use resolved when this was decided, and `validate` checks the 8-digit shape.
* UNU-KEYs have no IRIs. A product type carries `r9lab:unuKey "0303"^^r9lab:UNUKEYv1` (or `UNUKEYv2`),
  with `r9lab:` the vocabulary's own `terms#` namespace, which describes the property and both
  datatypes. The YAML keeps `broad: ['unu1:0303']`, and `validate` refuses any other relation. In
  the SSSOM file the row is a literal mapping (SSSOM 1.0): no `object_id`, the code in
  `object_label`, `object_type: rdfs literal`, and the datatype as `object_source`.
* The codes are not `skos:notation`s: a notation names the concept it is on, not an outside key.

A registry entry would add an outside dependency and a public record for code lists we neither own
nor maintain.

### Consequences

* Good: no IRIs under our base for codes we do not own; CPV links resolve to the EU's data.
* Good: the UNU-KEY names, under a non-commercial licence, stay out of the CC0 files by design.
* Bad: SKOS tools see the UNU-KEY link as a data property, not a mapping.
* Bad: tools older than SSSOM 1.0's literal mappings drop those rows. sssom-py 0.4.22 reads them,
  but drops every row of a set in which all rows are literal mappings.
* Bad: a CPV relation keeps the coarser meaning of R9lab's cut code; it is the padded EU code
  only because CPV pads with zeros.

### Confirmation

`tests/test_export.py` checks the typed codes and the SSSOM literal rows, and that nothing is
written under `external/`. `tests/test_checks.py` checks the CPV shape and the broad-only rule.
