# CIRPASS-2 Digital Product Passport crosswalk

Status **proposed**, 2026-11-27. Scope is the R9lab material and component schemes.

| Source | Download and reuse evidence |
| --- | --- |
| CIRPASS-2 MAT | The [DPP Vocabulary Hub](https://dpp.vocabulary-hub.eu/) lists a Turtle export and Apache 2.0 for MAT v1.0.3. The consortium's [MAT 1.2.0 Turtle](https://raw.githubusercontent.com/CIRPASS-2/ontologies-docs/82a73344db80a4481716b26e81f7eddbe5b5fbc7/CORE/mat/ontology.ttl), issued 2026-10-30, declares CC BY 4.0 with Apache 2.0 for software use or where CC BY applicability is disputed. This draft uses that file, SHA-256 `3fe35c0fbc077abe7c6a18416862fbe425b83806760cc8b8cd4930a2e0240b50`. |
| Hub Electronics / ICTDevice | The [Electronics v1 entry](https://dpp.vocabulary-hub.eu/ontology/Ontology_1bc9a0f2-f483-4fc6-bce9-ec904aabac62) identifies RePlanIT and lists an export. Its version row has no licence. The separately published [RePlanIT RDF/XML](https://raw.githubusercontent.com/RePlanIT/Ontology/4d187264f6727a6f52f096bc4d4745227c443ad6/RePlanIT_Ontology.owl) declares CC BY 4.0 and has SHA-256 `df4a2c499e640d864fb0ae6c6d44b514f6a0fdfb9cbf0376a75572076a26eafe`. The candidates below use those maintainer bytes. Hub export parity and reuse terms remain open. |

## Materials in MAT

MAT models how a passport declares composition. Its `hasMaterialType` links a
`MaterialOfComposition` to a sector-specific `MaterialType`. MAT 1.2.0 defines
no named material types for the [59 R9lab material concepts](../../vocabulary/materials.yaml),
so all 59 have **no direct MAT term match**.

Propose an exchange profile that pairs `eudpp:materialTypeScheme` with the
R9lab materials scheme IRI and `eudpp:materialTypeValue` with its local concept
ID. For example, a declared polycarbonate material can use the scheme
`https://w3id.org/r9lab/vocabulary/materials/` and value `m0026`. The
composition node and its type are passport data. The profile still needs a
sample with the target sector's SHACL or schema before adoption. A classification
alone supplies no composition percentage, origin, or passport conformity.

## Candidates from RePlanIT

`rp:` is `http://www.semanticweb.org/RePlanIT/`, `matonto:` is
`http://matonto.org/ontologies/matonto#`, and `ncit:` is
`http://purl.obolibrary.org/obo/NCIT_`. All targets below are declared OWL
classes in the pinned RDF/XML. Close and broad describe the meaning of the
alignment from R9lab to RePlanIT for review. A passport record can use an OWL
class to type an observed item and retain the R9lab concept ID as its
classification. Any RDF mapping should preserve that distinction.

| R9lab IDs | Candidate target | Proposed alignment and scope |
| --- | --- | --- |
| `c0001` battery | `ncit:C49839` | Close. Check pack and cell scope in the ICT profile. |
| `c0002–c0004` | `ncit:C49839` | Broad. Battery chemistry and primary use remain in R9lab. |
| `c0005–c0008` | — | No match. A generic hardware class or an example chip does not identify these boards and components. |
| `c0009` capacitor, `c0012` inductor | `rp:Capacitor`, `rp:Inductor` respectively | Close. Same device functions within the ICT context. |
| `c0010–c0011`, `c0013` | — | No match. No corresponding resistor, diode or transformer class. |
| `c0014` display | `rp:Display` | Close. Check treatment of integrated displays and standalone monitors. |
| `c0015–c0016` | `rp:Display` | Broad. Target leaves the display technology unspecified. |
| `c0017–c0025` | — | No match. In particular, a port is distinct from a cable, and a laptop speaker class needs scope evidence before aligning a bare driver. |
| `m0001`, `m0020`, `m0043`, `m0046`, `m0050` | `matonto:Metals`, `matonto:Polymers`, `matonto:Glasses`, `matonto:Ceramics`, `matonto:Composites` respectively | Close. Family-level candidates only. |
| `m0002`, `m0006`, `m0009`, `m0011`, `m0013–m0014`, `m0017–m0018` | `rp:Ferrous`, `rp:NonFerrous`, `rp:Copper`, `rp:Brass`, `rp:Tin`, `rp:Nickel`, `rp:Gold`, `rp:Silver` respectively | Close. Check pure and commercial material grades. |
| All other material IDs | — | No direct match proposed. In particular, elemental aluminium and magnesium do not identify their alloys, and a generic plastic class does not identify polycarbonate or an ABS blend. |

Before release, obtain the Hub electronics export and confirm its terms, compare
these class IRIs and meanings to the pinned maintainer file, and validate a
passport example with a material declaration and a component. Pin the selected
exports with checksums, record attribution, and make the build reject a missing
or wrong-kind target. These are mappings to project models. Product-group
obligations depend on the applicable EU acts.
[ESPR](https://eur-lex.europa.eu/eli/reg/2024/1781/oj)
