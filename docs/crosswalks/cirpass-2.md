# CIRPASS-2 Digital Product Passport crosswalk

Status **proposed**, 2026-11-28. Scope is the R9lab material and component schemes.

| Hub source | Download, checksum and reuse terms |
| --- | --- |
| MAT v1.1.0 | [Turtle export](https://dpp.vocabulary-hub.eu/api/ontology/-/version/OntologyVersion_978009d5-042d-4d13-9ed6-7885433c1bce/export?format=ttl), SHA-256 `67432b3479e5cfda839274f880862962225777624fe94bb84832e1c239fc96bc`. The export declares Apache 2.0 and names CC BY 4.0 for use as a document or if Apache 2.0 applicability is disputed. The Hub marks the version as a draft. [Version page](https://dpp.vocabulary-hub.eu/id/specification/eudpp-mat/1.1.0) |
| Electronics v1 / RePlanIT | [Turtle export](https://dpp.vocabulary-hub.eu/api/ontology/-/version/OntologyVersion_31c8432e-e231-4b58-96dc-b34e22fcb54d/export?format=ttl), SHA-256 `c2f01ff2c4575917feea4b6a505df3c519a17203b0a4f6994fa8e85d27e30697`. The export declares CC BY 4.0 in the ontology header. Its 1,218 RDF triples form the same graph as the [pinned RePlanIT maintainer RDF/XML](https://raw.githubusercontent.com/RePlanIT/Ontology/4d187264f6727a6f52f096bc4d4745227c443ad6/RePlanIT_Ontology.owl). [Version page](https://dpp.vocabulary-hub.eu/id/specification/electronics/1) |

Both Hub exports were checked on 2026-11-28. The checksums identify the reviewed
bytes. The consortium's separately published [MAT 1.2.0](https://raw.githubusercontent.com/CIRPASS-2/ontologies-docs/82a73344db80a4481716b26e81f7eddbe5b5fbc7/CORE/mat/ontology.ttl)
defines the same material type properties used below.

## Materials in MAT

MAT models how a passport declares composition. Its `hasMaterialType` links a
`MaterialOfComposition` to a sector-specific `MaterialType`. The checked MAT
exports define neither individual material types nor subclasses of `MaterialType`.
All [59 R9lab material concepts](../../vocabulary/materials.yaml) therefore have
**no direct MAT term match**.

The proposed profile places the R9lab **versioned materials scheme IRI** and the
local concept ID on the passport's `MaterialType` node. Use the scheme version
to select the release, then look up the ID in that release to recover the stable
concept IRI. The example declares polycarbonate using the proposed 0.1.0 scheme
version.

```turtle
@prefix eudpp: <https://w3id.org/eudpp#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

[] a eudpp:MaterialOfComposition ;
   eudpp:hasMaterialType [
     a eudpp:MaterialType ;
     eudpp:materialTypeScheme "https://w3id.org/r9lab/vocabulary/0.1.0/materials/"^^xsd:anyURI ;
     eudpp:materialTypeValue "m0026"
   ] .
```

The classification supplies the declared material type. A passport producer
must supply the composition facts and check the target sector's schema.

## Candidates from RePlanIT

`rp:` is `http://www.semanticweb.org/RePlanIT/`, `matonto:` is
`http://matonto.org/ontologies/matonto#`, and `ncit:` is
`http://purl.obolibrary.org/obo/NCIT_`. All targets below are declared OWL
classes in Hub Electronics v1. The alignments describe meaning from R9lab to
RePlanIT for review. A passport record can use an OWL class to type an observed
item and retain the R9lab concept ID as its classification. Contextual
candidates need item-level evidence before that typing.

| R9lab IDs | Candidate target | Proposed alignment and scope |
| --- | --- | --- |
| `c0001` battery | `ncit:C49839` | Close. Confirm pack and bare-cell scope in an ICT profile. |
| `c0002–c0004` | `ncit:C49839` | Broad. Battery chemistry and primary use remain in R9lab. |
| `c0005–c0008` | — | No direct match proposed. The hardware class is too general and the chip classes cover individual types. |
| `c0009` capacitor, `c0012` inductor | `rp:Capacitor`, `rp:Inductor` respectively | Close. The functions align within the ICT scope. |
| `c0010–c0011`, `c0013` | — | No direct match proposed for these devices. |
| `c0014–c0016` displays | `rp:Display` | Contextual. Use for computer display modules. The R9lab types also cover phones, wearables and other products. |
| `c0017–c0022`, `c0024–c0025` | — | No direct match proposed. A port covers the host connection rather than the cable, and a battery class is insufficient for a bare cell. |
| `c0023` loudspeaker driver | `rp:Speakers` | Contextual. RePlanIT covers both integrated and external computer speakers. Restrict this candidate to integrated computer speaker units. |
| `m0001`, `m0020`, `m0043`, `m0046`, `m0050` | `matonto:Metals`, `matonto:Polymers`, `matonto:Glasses`, `matonto:Ceramics`, `matonto:Composites` respectively | Close. Family-level candidates. |
| `m0002`, `m0006`, `m0009`, `m0011`, `m0013–m0014`, `m0017–m0018` | `rp:Ferrous`, `rp:NonFerrous`, `rp:Copper`, `rp:Brass`, `rp:Tin`, `rp:Nickel`, `rp:Gold`, `rp:Silver` respectively | Close. Check pure and commercial material grades when applying the links. |
| `m0003` carbon and low-alloy steel | `rp:CarbonSteel` | Contextual. Check the alloy grade against the RePlanIT carbon steel definition before using this class. |
| All other material IDs | — | No direct match proposed. Elemental aluminium and magnesium do not identify their alloys. A generic plastic class does not identify polycarbonate or an ABS blend. |

Before publishing, pin the selected exports by checksum and record attribution
and reuse terms in the source manifest. Check candidate target kind and existence
against the pins and validate a sample with a material declaration and component
against the chosen sector's schema. Keep contextual candidates out of automatic
classification. Product-group obligations depend on the applicable EU acts.
[ESPR](https://eur-lex.europa.eu/eli/reg/2024/1781/oj)
