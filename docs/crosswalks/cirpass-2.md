# CIRPASS-2 Digital Product Passport crosswalk

Status **proposed**, 2026-11-28. Scope is the R9lab material and component schemes.

| Hub source | Download, checksum and reuse terms |
| --- | --- |
| MAT v1.1.0 | [Turtle export](https://dpp.vocabulary-hub.eu/api/ontology/-/version/OntologyVersion_978009d5-042d-4d13-9ed6-7885433c1bce/export?format=ttl), SHA-256 `67432b3479e5cfda839274f880862962225777624fe94bb84832e1c239fc96bc`. The export declares Apache 2.0 and names CC BY 4.0 for use as a document or if Apache 2.0 applicability is disputed. The Hub marks the version as a draft. [Version page](https://dpp.vocabulary-hub.eu/id/specification/eudpp-mat/1.1.0) |
| Electronics v1 / RePlanIT | [Turtle export](https://dpp.vocabulary-hub.eu/api/ontology/-/version/OntologyVersion_31c8432e-e231-4b58-96dc-b34e22fcb54d/export?format=ttl), SHA-256 `c2f01ff2c4575917feea4b6a505df3c519a17203b0a4f6994fa8e85d27e30697`. The export declares CC BY 4.0 in the ontology header. Its 1,218 RDF triples form the same graph as the [pinned RePlanIT maintainer RDF/XML](https://raw.githubusercontent.com/RePlanIT/Ontology/4d187264f6727a6f52f096bc4d4745227c443ad6/RePlanIT_Ontology.owl). [Version page](https://dpp.vocabulary-hub.eu/id/specification/electronics/1) |

Both Hub exports were checked on 2026-11-28. The checksums identify the reviewed
bytes. The consortium's separately published [MAT 1.2.0](https://raw.githubusercontent.com/CIRPASS-2/ontologies-docs/82a73344db80a4481716b26e81f7eddbe5b5fbc7/CORE/mat/ontology.ttl)
defines the same material type properties used below.

## Review and check the table

The [v1 review table](cirpass-2-crosswalk-v1.tsv) records one disposition per
R9lab concept in each applicable Hub module. MAT covers all 59 material
concepts. Electronics covers the same materials and all 25 component concepts.
A blank target with `no-match` records a reviewed gap. Add the applicable table
rows when a release adds a material or component concept. `broad` and `close`
describe the proposed scope from R9lab to Electronics. `contextual` needs
item evidence, such as knowing whether a display module comes from a computer.
Those links describe candidates for typing passport records. The target classes
belong to OWL, and the R9lab terms remain SKOS concepts.

From the repository root, run the checker against the current vocabulary and
the checked-in index of 203 named OWL classes from Hub Electronics v1.

```shell
uv run python -m r9lab_vocabulary.dpp
```

Download the two pinned Turtle files from the table above to check the original
bytes and confirm that the Electronics graph still produces the same class index.

```shell
uv run python -m r9lab_vocabulary.dpp --electronics electronics-v1.ttl --mat mat-v1.1.0.ttl
```

The [class index](cirpass-2-electronics-v1-classes.txt) contains identifiers
only. It comes from the subjects declared as `owl:Class` in the Electronics
export, sorted and written as UTF-8 with one IRI per line.

## Exchange profile

MAT v1.1.0 and v1.2.0 define neither individual material types nor subclasses of
`MaterialType`, so every material row records no direct match. Their
`hasMaterialType` property links a `MaterialOfComposition` declaration to
its `MaterialType`, which can hold the R9lab versioned materials scheme IRI
and local concept ID. Use the scheme version to select the release and look up
the ID there to recover the stable concept IRI.

The [sample exchange](cirpass-2-example.ttl) represents a capacitor with copper
terminals in an illustrative laptop record. RePlanIT supplies the component
class and ICT device relationship. MAT supplies the composition declaration,
scheme and code. The local profile links the component and the MAT declaration
using `r9lab:materialDeclaration` and records the component concept under
`schema:additionalType`. The [local SHACL shapes](../../shapes/dpp-exchange.shacl.ttl)
check these fields on explicit triples, with OWL inference disabled.

```shell
just py-test tests/test_dpp.py
```

The Hub’s public Electronics metadata returned no linked message model and its
public specification search returned no ICTDevice profile on 2026-11-28. The
pinned RePlanIT repository contains the ontology and competency questions. The
published OpenEPCIS electronics shapes use OpenEPCIS classes and properties.
None of their SHACL targets selected nodes in the MAT/RePlanIT sample. The
local validation checks the exchange example. Sector and regulatory conformance
need the applicable product-group requirements and profile.
[Hub Electronics metadata](https://dpp.vocabulary-hub.eu/api/specification/electronics) ·
[RePlanIT source](https://github.com/RePlanIT/Ontology/tree/4d187264f6727a6f52f096bc4d4745227c443ad6) ·
[OpenEPCIS electronics shapes](https://github.com/openepcis/openepcis-dpp-ready/blob/74ad8c77307adec73fab1c417d737d6c6593444a/extensions/eu/electronics/validation/electronics-shapes.ttl) ·
[ESPR](https://eur-lex.europa.eu/eli/reg/2024/1781/oj)
