---
status: proposed
date: 2026-11-27
---

# Publish resolvable concept IRIs and per-scheme release files

## Context

The current w3id redirect reaches the repository for both `Accept: text/html`
and `Accept: text/turtle`. A request for a concept, a scheme, or a version reaches
the same page. Applications that store concept IRIs need those IRIs to keep working
after a release, including when a concept is deprecated.

The combined Turtle graph has four SKOS schemes. [VocPub 5.4][vocpub] requires
one scheme per vocabulary file. The existing combined graph is useful to PyST
and to readers that use cross-scheme mappings in a single load. [ADR 0004][versions]
sets the persistent and versioned IRI patterns.

## Considered options

- Publish one bundle and a repository landing page.
- Add per-scheme RDF release assets and a resolver with distinct RDF and HTML
  representations. Retain the bundle for existing clients.
- Run a vocabulary service as the authoritative store and route public IRIs to it.

## Proposed decision

Build one RDF file per scheme from the same YAML and keep the combined download
as the dataset distribution. Keep all existing scheme and concept IRIs. Put the
membership, collection and agent metadata for each scheme into its file. Include
the definitions of any local properties and datatypes the file uses, including
the UNU-KEY datatypes in the product scheme. Keep cross-scheme mapping targets as links. Validate each file against a pinned
VocPub validator before publishing and run the existing checks on the bundle.

Use immutable assets for every version and route version IRIs to those assets.
Route unversioned IRIs to the current release through w3id. For concept requests,
return RDF for that concept or an HTML page that identifies it directly. Use a
303 redirect where appropriate and send `Vary: Accept` if the response varies
by media type. Keep deprecated concepts resolvable with their replacement links.
Preserve the existing bundle download URLs and archive releases with the DOI
record. A vocabulary catalogue and a DOI archive serve discovery and preservation.

Before changing w3id, test the latest and older version of one scheme, a live
concept, a deprecated concept, a missing IRI, and both HTML and RDF Accept
headers. Agree who owns the resolver, catalogue entry and redirect updates.
The publishing contract matters even if the serving platform later changes.

## Consequences

- Readers can load a single scheme and resolve stable and archived identifiers.
- Release checks cover both standalone files and the combined graph.
- A resolver and release archive need a named maintainer, monitoring and a
  migration path. Switching the public routing before those are in place risks
  breaking stored links.

[vocpub]: https://agldwg.github.io/vocpub-profile/profile.html
[versions]: 0004-versioned-iris-and-scheme-dates.md
