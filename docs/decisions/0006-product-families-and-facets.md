---
status: accepted
date: 2026-11-26
---

# Product families for navigation, facets as their own schemes later

## Context and Problem Statement

Writing definitions for the product types turned up types that fit two families (a GPS
receiver: telecom or audio and video?) and families that cut across WEEE categories. The
families group 27 types today. They could stay a single tree, become several faceted schemes,
or give way to an outside classification. Concept IRIs are published, so a structure that
later forces new ids is costly.

## Considered Options

* One tree of families, with a second `broader` where a type really sits in two (polyhierarchy)
* Group the types by UNU-KEY
* Facets (such as power source or product group under the EU ecodesign rules) as separate
  SKOS concept schemes

## Decision Outcome

Chosen: one tree with sparse polyhierarchy now, and facets as separate schemes when they are
needed, added next to the tree, not in place of it.

* Families are for browsing. A type gets a second parent only where a reader would look for
  it in both families. Each extra edge is a decision, not a default.
* Outside product classes (CN, ECLASS, UNSPSC, UNU-KEY, WEEE, CPC) stay in `mappings`, never in
  `broader`. The EU passport registry asks for CN codes, and no ecodesign act mandates a
  product classification, so mapping out is enough.
* A facet scheme starts when the first family outside electrical and electronic equipment
  arrives, or when the types pass about 60. Where an EU passport sector vocabulary exists
  (CIRPASS-2 publishes battery categories and chemistries), the facet maps to it rather than
  copying it.
* Definitions are written to read well after the parent's label, since a vision-language
  model gets label, parent and definition as one prompt.

### Consequences

* Good: the tree stays consistent for classifiers that predict parent and child together,
  and a facet adds a scheme without changing a concept id.
* Bad: until a facet exists, a question such as "every battery-powered product" needs the
  mappings or a manual list.

### Why not UNU-KEY

UNU-KEY has no codes outside electrical and electronic equipment, and its names are licensed,
so the vocabulary cannot reuse them as labels. It stays a mapping.

## More Information

* CIRPASS-2 DPP core ontology and sector vocabularies: <https://dpp.vocabulary-hub.eu/>
* Multiple inheritance for parts that are both material-level and sector passports, in the
  OntoCrafter Ceramics Ontology: <https://arxiv.org/abs/2606.14814>
* Context-rich descriptions beat class-only prompts for open-vocabulary waste detection:
  <https://arxiv.org/abs/2508.18799>
