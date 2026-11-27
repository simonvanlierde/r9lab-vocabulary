# Open Repair Data Standard product crosswalk

Status **proposed**, 2026-11-27.

Use `product_category_id` from the ORDS v0.3 electrical and electronic equipment
(EEE) codelist. The 40 IDs below were checked against the Open Repair Alliance CSV
and the standard's category descriptions. The CSV is published under CC BY-SA 4.0
and pinned at SHA-256
`c9309e6146bd64f2bc635bc296926413ead8fe8bb9dee14479b4d8e978ab4ba1`.
[Standard §3.4.2](https://standard.openrepair.org/standard.html#product-category-values) ·
[Pinned CSV](https://media.githubusercontent.com/media/openrepair/data/2af16342c751f56e28e2f62d018f051e7f22aed0/OpenRepairData_v0.3_Product_Categories_eee.csv) ·
[Reuse terms](https://github.com/openrepair/data/tree/2af16342c751f56e28e2f62d018f051e7f22aed0)

Read the relation **from R9lab to ORDS**. A broad match lets a specific R9lab type
roll up to an ORDS category. Going the other way, an ORDS repair may have several
candidate types and requires more detail before assigning one. `No match` means
the draft proposes no link to a current R9lab product type. Product IDs refer to
[the product scheme](../../vocabulary/products.yaml).

| ORDS ID | R9lab product ID | Proposed relation | Scope for review |
| --- | --- | --- | --- |
| 1 | — | No match | No climate-control type. |
| 2 | `p0014` laptop charger | Broad | Adapters include laptop chargers alongside other chargers and batteries. |
| 3 | — | No match | Product use determines this group. The luminaire type spans other uses. |
| 4 | — | No match | A desktop is a whole product. Its parts have their own types. |
| 5–6 | — | No match | No camera type. |
| 7 | `p0029` electric fan | Broad | The ORDS scope includes fan heaters. |
| 8 | — | No match | No standalone TV or monitor type. |
| 9 | `p0031` electric shaver, `p0033` electric foot file | Broad | General powered grooming category. Confirm foot files with a repair data curator. |
| 10 | — | No match | No portable entertainment player type. |
| 11 | `p0019` headphones | Close | Confirm partner handling of earbuds and headsets. |
| 12 | — | No match | No integrated stereo type. |
| 13 | `p0020` speaker | Close | Overlap covers separate hi-fi speakers. Portable speakers may be grouped elsewhere. |
| 14 | `p0025` electric kettle | Exact | Same powered water-boiling appliance. |
| 15 | `p0024` luminaire | Close | Desk and floor fittings overlap. Check fixed and professional fittings. |
| 16 | `p0007` laptop | Close | Confirm that ORDS separates tablets and detachables consistently. |
| 17–18 | — | No match | Residual categories need item-level evidence. |
| 19 | `p0015` mobile phone | Broad | ORDS includes other handheld telecommunications devices. |
| 20–21 | — | No match | No powered instrument or paper shredder type. |
| 22 | `p0009` docking station, `p0012` computer mouse, `p0013` computer keyboard | Broad | Confirm docking stations across providers. Add-in cards and internal power supplies need separate evidence. |
| 23 | `p0021` radio | Close | Portable receivers overlap. R9lab also includes mains-powered receivers. |
| 24–27 | — | No match | No powered tool, printer/scanner, projector or sewing machine type. |
| 28–29 | — | No match | Residual groups need item-level evidence. |
| 30 | `p0008` tablet, `p0018` GPS navigation device | Broad | ORDS includes e-readers and lists satellite navigation as an example. |
| 31 | `p0026` toaster | Exact | Same powered bread toaster. |
| 32–35 | — | No match | No toy, gaming accessory, vacuum or watch type. `p0022` spans remotes for other equipment too. |
| 36 | — | No match | Brewing and grinding have different scopes. |
| 37 | `p0027` coffee grinder | Broad | The ORDS scope explicitly includes coffee grinders. |
| 38 | — | No match | No game console type. |
| 39 | `p0032` hair dryer | Close | Confirm handling of non-handheld dryers. |
| 40 | `p0028` clothes iron | Close | Confirm handling of steam-generator irons. |

Before release, review the close matches and the routing of hair dryers between
9 and 39. Check that forward rollups use exact and broad links only, and keep
the source ID on each repair record. Use the pinned CSV to reject unknown IDs
and require an explicit disposition for all 40 codes. Use identifiers only in
the crosswalk and keep the upstream codelist under its own terms. If no
publisher IRIs are available, propose a versioned ORDS code datatype under
[ADR 0007](../decisions/0007-outside-codes-without-iris.md) before wiring the
crosswalk into the export.
