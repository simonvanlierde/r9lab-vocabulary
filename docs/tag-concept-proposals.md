# Component proposals for unmapped tags

Six tags have a proposed mapping. Four need a decision for each record. Each concept's YAML records the
crosswalks found in CPC 2.1 or Wikidata. The code and tag mapping checks run
against the vocabulary before release.

| Export tag | Replacement proposal | Pilot key |
| --- | --- | --- |
| brushless motor stator | Check each record. Use electric motor stator (c0027) for a stator or electric motor (c0022) for a complete motor. | `motor_transformer` for a complete motor or qualifying wound assembly. Check material for a stripped core. |
| camera module | Camera module (c0028). Use the host product for a complete standalone camera. | `electronics` |
| electrical motor part | Keep unresolved at tag level. Complete DC motor → c0022. A rotor or other verified internal part → c0026. A haptic vibration actuator goes to c0055. | `motor_transformer` for a qualifying motor or wound assembly. Inspect other records. |
| electronic foil | Use flexible printed circuit (c0029) only when the record confirms printed tracks. Shielding foil and flat cables take their own classification. | `electronics` for a printed circuit. |
| fan blades | Use fan blade assembly (c0030) for the blades or internal electric fan assembly (c0054) when the motor and blades are together. | `plastic` for moulded plastic blades, or the measured material key. |
| keyboard module | Keyboard module (c0031). A loose keycap or membrane is a separate part. | Check the assembly. Separately recorded boards use `electronics`. |
| lightbulb | Electric light bulb (c0032). Use a more specific class when the technology and product scope are known. | `display_glass` for a glass bulb as specified in the pilot, otherwise inspect. |
| microphone module | Microphone module (c0033). | `electronics` |
| pcb | Printed circuit board (c0034) if population is unknown. Use c0005 for bare or c0006 for populated when known. | `electronics` |
| touchpad | Close match to touchpad module (c0035). Check scope if the record describes the buttons or the cover alone. | `electronics` for the module. |

The PCB parent carries the Wikidata link that previously identified the
bare board as a general printed circuit board. Bare and populated boards
both inherit the existing `electronics` key through the new parent. The key
applies to a camera, microphone or touchpad module removed from its host.
Use the larger assembly’s scope when the module is still attached.

CPC classes that mix parts and other goods are broad or related mappings.
A search of the two pinned BAFU releases found finished keyboards, so the
keyboard module has no BAFU activity mapping. The other entries likewise
have no verified equivalent activity.
