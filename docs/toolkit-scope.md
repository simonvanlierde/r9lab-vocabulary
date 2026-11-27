# Vocabulary toolkit scope

**Draft for review.** A toolkit for maintainers who turn local labels into versioned
concept schemes and need to publish reproducible links to other classifications.
R9lab is the first case. Its repair and disassembly data need stable IDs for products,
components and materials, and the same shortened tag can mean different things in
different fields.

## First workflow

1. Author a small vocabulary in Git with stable concept IDs, definitions and source
   citations. Store changes to concepts and mappings in reviewable diffs.
2. Propose local tag mappings with the field as part of the key. Preserve the
   source, relation and human verdict, including unresolved tags.
3. Check mapping targets against pinned sources and report added, changed,
   withdrawn and unresolved links between releases. Let a project supply its own
   checks, such as the BAFU pattern checks for each inventory release.
4. Build versioned SKOS and SSSOM files for use without a server. A publishing
   adapter can load a reviewed view into PyST.

## Prior art and boundaries

| Tool | What it already does and where it fits |
| --- | --- |
| [nomenclature](https://github.com/IAMconsortium/nomenclature) | Git-backed IAMC codelists, project validation and model-specific region mappings. Its definitions and mapping layout is prior art for project configuration. Keep IAMC processing and aggregation there. |
| [PyST](https://docs.pyst.dev/) and [OpenRefine](https://openrefine.org/docs/manual/reconciling) | PyST serves SKOS/XKOS schemes and associations. OpenRefine supports interactive reconciliation through services. A toolkit should emit data these tools can serve or consume. |
| [SSSOM](https://mapping-commons.github.io/sssom/) and [SHACL](https://www.w3.org/TR/shacl/) | Reuse the mapping interchange format and graph validation language. Keep field-specific identity in the source key and review provenance in SSSOM. |
| [sourceledger](https://github.com/simonvanlierde/sourceledger) | Reuse source pins, checksums and reuse terms. Project code decides whether a mapping target or name pattern holds against the source. |
| [PMDco](https://github.com/materialdigital/core-ontology) and [Départ de Sentier vocabularies](https://vocab.sentier.dev/) | Reuse external identifiers and existing classifications where their scopes fit. R9lab remains a project vocabulary. |

Keep label discovery in word-list tools such as sensebank and preserve their
proposals as candidate input. Use the project review workflow for verdicts.
Domain authoring, web hosting, passport compliance, repair-record import and
inventory selection belong with the tools and people that own those decisions.

## First milestone

Build the same SKOS and SSSOM from a pinned Git revision on two runs. Trace one
raw tag through its field, reviewed mapping and published concept, and report
one unresolved tag. Try the workflow on a second vocabulary before extracting
shared code from R9lab.
