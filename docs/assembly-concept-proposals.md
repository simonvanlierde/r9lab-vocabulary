# Component proposals for internal assemblies and controls

Use these proposals when the record's name, parent and photo agree.
A name such as frame, button or screen can describe several types of
parts. The YAML links each candidate to searched CPC 2.1 codes or
Wikidata items and states its scope.

| Candidate | Replacement cue | Pilot key when known |
| --- | --- | --- |
| c0046 equipment support frame | A chassis or internal frame that carries working parts. | Use the measured material key. |
| c0047 equipment mounting bracket | A bracket that attaches a part at a local mounting point. | Use the measured material key. |
| c0048 keyboard keycap | A removable letter, function or space key cover. | `plastic` for a plastic keycap. |
| c0049 pushbutton actuator cap | A loose button, button cap or plunger. Check whether the record contains the electrical contacts. | `plastic` or `rubber` when the recorded material supports it. |
| c0050 mouse scroll wheel | The wheel itself, optionally with its tread. A scroll encoder or separate tread needs its own classification. | Use the measured material key. |
| c0051 electrical switch | A switch recorded with its contact mechanism. | `electronics` |
| c0052 optical lens | A lens element. Inspect a cover window or a camera module separately. | `display_glass` for glass, `plastic` for polymer. |
| c0053 mechanical hinge | An articulated hinge. Check that a pin or cover is not recorded on its own. | Use the measured material key. |
| c0054 internal electric fan assembly | A fan with motor and blades installed inside a host. Check scope if the tag says fan blades. | Use the measured material or assembly scope. |
| c0055 haptic vibration actuator | A tactile feedback module. Use it for records labelled with a motor-part tag only after confirming their function. | Check the actuator's build before applying `motor_transformer` or another key. |

Two pilot examples are particularly sensitive to scope. A whole fan
contains a motor, and its blade material does not classify the assembly.
A haptic actuator can use a rotary motor, a linear resonant actuator or
another mechanism. The concept itself carries no fixed material key.
