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

## Second vocabulary trial

The [CV × industrial ecology taxonomy input](https://github.com/simonvanlierde/cv-ie-taxonomy/blob/23923a87a9de534e09ce7183cd123f93f78dc646/src/data/taxonomy.json)
produced 12 SKOS concepts and 78 triples. The trial used each existing cell
deep link as its IRI, copied its task label with CC BY 4.0 attribution,
and kept evidence grades and scores in the application. Two builds had identical
bytes and the graph passed the same SkoHub SKOS shapes used here.

The two projects share stable IDs, source pins and graph checks. They differ
in ID syntax, licensing, data model and review workflow. R9lab's YAML validator
expects its own ID format, and its exporter uses R9lab's IRIs and CC0. Start
with a template for publishing checks and release metadata when another project
needs that setup. Extract shared runtime code when a second project needs the
same transformation or validation.
