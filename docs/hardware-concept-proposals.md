# Component proposals for recurring teardown hardware

Use these as candidate part classifications. Confirm that the named part
is the item recorded before applying a proposal. Keep the material
classification when it is known. The labels file leaves the pilot key
empty for these concepts because the part's material or assembly scope
determines it.

| Candidate | Replacement cue | Pilot key when known |
| --- | --- | --- |
| c0036 screw or bolt | Screw or bolt with its own record. Check that the name is about the fastener. | `ferrous` for steel, `non_ferrous` for brass, or the measured material key. |
| c0037 fastener nut | Nut, wing nut or locknut. | Use the measured material key. |
| c0038 hardware washer | Flat washer or lock washer. Use a seal for a part whose primary role is stopping leaks. | Use the measured material key. |
| c0039 mechanical spring | Coil, leaf or torsion spring. | `ferrous` for a steel spring. |
| c0040 gear wheel | A gear or pinion. Check scope for a gearbox or mixed assembly. | `plastic` or the measured metal key. |
| c0041 mechanical bearing | Rolling-element bearing or plain bushing. Check whether the record also includes its housing. | Use the measured material key. |
| c0042 equipment housing or housing panel | A case, shell or protective outer panel. Check whether it is an interior mounting frame. | Use the measured material key. |
| c0043 heat sink | Passive finned or spreading piece. Keep the fan separate if it has its own record. | `non_ferrous` for aluminium or copper. |
| c0044 electrical connector | Loose plug, socket or terminal assembly. Use cable for a lead recorded with its plug. | Inspect the assembly. Use `cable` for the complete lead. |
| c0045 mechanical seal | Gasket, O-ring or shaft seal. | `rubber` for the elastomer forms, or the measured material key. |

The YAML records the CPC 2.1 and Wikidata links. CPC codes that depend on
material or host device remain related links. BAFU has a CPU heat sink
activity and a combined hinges-and-screws activity. Neither establishes
an equivalent activity for the respective general concept.
