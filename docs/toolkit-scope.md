# Vocabulary toolkit scope

**Draft for review.** A toolkit for maintainers who turn local labels into versioned
concept schemes and need to publish reproducible links to other classifications.
R9lab is the first case. Its repair and disassembly data need stable IDs for products,
components and materials, and the same shortened tag can mean different things in
different fields.

## First workflow

1. Author a small vocabulary in Git with stable concept IDs, multilingual labels,
   definitions and citations. Record deprecations and replacements in the same files.
2. Propose local tag mappings with the field as part of the key. Preserve the
   source, relation and human verdict, including unresolved tags.
3. Check mapping targets against pinned sources and report added, changed,
   withdrawn and unresolved links between releases. Let a project supply its own
   checks, such as the BAFU pattern checks for each inventory release.
4. Build SKOS and SSSOM with version and source metadata. Check the RDF with
   SHACL and keep release artifacts usable offline. A publishing adapter can load
   a reviewed view into PyST.

## Prior art and boundaries

| Tool | What it already does and where it fits |
| --- | --- |
| [nomenclature](https://github.com/IAMconsortium/nomenclature) and [common-definitions](https://github.com/IAMconsortium/common-definitions) | Reuse the pattern of YAML codelists, pull-request validation and a spreadsheet export for review. Nomenclature has region aggregation and explicit legacy renames. Opaque concept IDs let a label change without changing its identifier. |
| [PyST](https://docs.pyst.dev/), [Skosmos](https://www.skosmos.org/) and [VocBench](https://vocbench.uniroma2.it/) | PyST serves SKOS/XKOS schemes and associations, Skosmos publishes browsable vocabularies, and VocBench supports collaborative editing. Use their existing interfaces for hosting and editing. |
| [SSSOM](https://mapping-commons.github.io/sssom/) and [SHACL](https://www.w3.org/TR/shacl/) | Reuse the mapping interchange format and graph validation language. Keep field-specific identity in the source key and review provenance in SSSOM. |
| [sourceledger](https://github.com/simonvanlierde/sourceledger) | Reuse source pins, checksums and reuse terms. Project code decides whether a mapping target or name pattern holds against the source. |
| [OpenRefine](https://openrefine.org/docs/manual/reconciling) and [PMDco](https://github.com/materialdigital/core-ontology) | OpenRefine can reconcile labels against a service. Map to PMDco identifiers where the scope fits and retain the local concept IDs. |

Keep the R9lab tag grammar, rater protocol, photo-study classes and BAFU pattern
semantics in R9lab. Word-list tools such as sensebank can supply proposals. Each
project decides how to review mappings and what counts as a source match.

## First milestone

Build the same SKOS and SSSOM from a pinned Git revision on two runs. Trace one
raw tag through its field, reviewed mapping and published concept, and report
one unresolved tag. Use the [CV × industrial ecology taxonomy](https://github.com/simonvanlierde/cv-ie-taxonomy)
as the first candidate for a second trial. Export its existing cell IDs and labels
as a small SKOS scheme while preserving its data licence. Keep evidence grades and
scoring in the application. If the trial needs the same runtime checks, consider a
library. If it shares only the layout and recipes, use a Copier template.
