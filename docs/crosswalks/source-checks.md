# UNU-KEY and BAFU source checks

Checked 2026-11-27 against the vocabulary at `45be82a`.

## UNU-KEY

Compared the 54 v1 and 57 v2 entries in `FIXED_CODES` with 2018 Table 1 and
2026 Table 2. Both sets agree with their sources. All 27 leaf product types
have one valid four-digit code per edition. The six navigation families have
no code. Compared the pairs with 2026 Annex 2, Table 19, and used Annexes 3 and
4 for product-specific exceptions. The following groups account for all 27
types. Source labels and descriptions stay in the publishers' files.
[2018 guidelines](https://digitallibrary.un.org/record/4099628) ·
[2026 guidelines and annexes](https://doi.org/10.5281/zenodo.18328494)

| R9lab product IDs | v1 | v2 | Scope check |
| --- | --- | --- | --- |
| `p0007–p0008` | 0303 | 0303 | Table descriptions cover both. |
| `p0009`, `p0012–p0013`, `p0017` | 0301 | 0301 | The descriptions cover mice, keyboards and routers. Docking stations fit the accessory scope. CPC 47223 also covers equipment under 0305, so keep the more specific evidence for routers. |
| `p0010–p0011` | 0301 | 0301 | Review use as reporting codes for internal parts. Annex 4 places CPC 45281 under 0301, which supports the graphics-card link as a candidate. The internal power supply has weaker support. |
| `p0014`, `p0028–p0030` | 0201 | 0201 | Descriptions support adapters, clothes irons and small ventilators. Generic trade headings can be wider than the R9lab type. Review passive power strips and the limits of the fan type before using the codes for reporting. |
| `p0015` | 0306 | 0306 | Cellular phones. |
| `p0016` | 0305 | 0305 | Fixed and IP telephones. |
| `p0018` | 0402 | 0402 | Navigation equipment is in the description and 2026 Annex 3. |
| `p0019`, `p0022` | 0401 | 0401 | The descriptions cover headphones and remotes. The CPC heading for remotes also covers navigation equipment, so prefer the product description. |
| `p0020` | 0405 | 0405 | The speaker description and enclosed loudspeaker trade rows support the link. |
| `p0021` | 0402 | 0403 | Review. Annex 2 retains 0402 as 0402. The 2026 HS table sends clock radios (852792) to 0403 and keeps some portable receivers (852719) in 0402. One v2 code cannot cover the mixed R9lab type reliably. |
| `p0023` | 0505 | 0505 | Replaceable LED lamps. |
| `p0024` | 0506 | 0506 | Review. Both editions distinguish household (0506) and professional (0507) fittings. R9lab's definition includes both. |
| `p0025` | 0203 | 0203 | Kettles fit the water-heating scope. |
| `p0026–p0027` | 0202 | 0202 | Toasters and powered grinders fit the food preparation scope. |
| `p0031–p0033` | 0205 | 0205 | The description names shavers and hair dryers. A powered foot file fits by intended use. |

The 2018 PDF checked was the UN Digital Library English copy, SHA-256
`450d12c34a70672f397624280c315c0fc64bed515c627657b28c6681f861434e`.
The 2026 PDF matched the checksum in [sources.toml](../../sources.toml).
Keep the radio and luminaire codes out of automatic reporting until their
scope is settled. Review subtype links or remove the overbroad rollup rather
than asserting both target keys for the whole type.

## BAFU

Verified the raw archives with `r9lab-vocabulary validate` and ran
`r9lab-vocabulary rdf` and `r9lab-vocabulary names --summary`. The archives
matched the pins in [sources.toml](../../sources.toml).

| Release | Archive SHA-256 | Patterns with matches | Sum of per-pattern counts |
| --- | --- | --- | --- |
| BAFU:2025 v2 | `54cb370abba22ad1f6a9f6f9ef65f9fbad5a496fdf785cd5ad9517701b47a38e` | 58 of 58 | 212 |
| BAFU:2026 v1 | `cbaeed4ae79c0be98709c854211cd72725d4f22f8b9b3fe334b7f343fca152f5` | 58 of 58 | 212 |

Every individual count agrees across releases. The totals count candidate
names per pattern, so overlapping patterns can count a name more than once.
Use `just names --summary` to reproduce the per-pattern counts, or read
`dist/name-matches.csv` after `just rdf`. Both exclude obsoleted activities
through the existing source reader. Matching a name establishes a candidate
inventory activity. For example, the cable concept also finds plug-only
activities. A downstream selection still needs the intended object and
activity scope. [FOEN BAFU database](https://data.bafu.admin.ch/en/dataproduct-economy-consumption-lca)

### Counts by concept and pattern

A trailing `␠` represents a literal space in the pattern.

| Concept | Pattern | 2025 v2 | 2026 v1 |
| --- | --- | --- | --- |
| `components/c0002` | `^battery, (li-?ion\|liio)` | 3 | 3 |
| `components/c0002` | `^battery, rechargeable, prismatic, lincm` | 1 | 1 |
| `components/c0003` | `^battery, nimh` | 1 | 1 |
| `components/c0005` | `^printed wiring board, (surface mount\|through-hole), .*surface` | 4 | 4 |
| `components/c0006` | `^printed wiring board, (surface mounted\|through-hole mounted\|mixed mounted)` | 7 | 7 |
| `components/c0006` | `mainboard` | 6 | 6 |
| `components/c0006` | `^printed wiring board, power supply unit` | 3 | 3 |
| `components/c0007` | `^electronic component, (active\|passive), unspecified` | 2 | 2 |
| `components/c0008` | `^integrated circuit` | 5 | 5 |
| `components/c0009` | `^capacitor` | 6 | 6 |
| `components/c0010` | `^resistor` | 4 | 4 |
| `components/c0011` | `^light emitting diode` | 1 | 1 |
| `components/c0012` | `^inductor` | 4 | 4 |
| `components/c0015` | `^lcd (glass\|module\|screen)` | 3 | 3 |
| `components/c0015` | `^backlight, lcd` | 1 | 1 |
| `components/c0016` | `^(led\|oled) (module\|screen)` | 4 | 4 |
| `components/c0017` | `^cable,␠` | 6 | 6 |
| `components/c0017` | `^plugs, inlet and outlet` | 3 | 3 |
| `components/c0020` | `^permanent magnet` | 1 | 1 |
| `components/c0024` | `^battery cell,␠` | 6 | 6 |
| `materials/m0003` | `^steel, (converter\|electric), (unalloyed\|low-alloyed)` | 6 | 6 |
| `materials/m0003` | `^steel sheet` | 6 | 6 |
| `materials/m0004` | `^chromium steel 18/8` | 4 | 4 |
| `materials/m0005` | `^cast iron` | 2 | 2 |
| `materials/m0007` | `^aluminium, (primary\|secondary\|production mix)` | 8 | 8 |
| `materials/m0008` | `^magnesium-alloy` | 2 | 2 |
| `materials/m0009` | `^copper, (primary\|secondary\|at regional storage)` | 7 | 7 |
| `materials/m0009` | `^copper sheet` | 5 | 5 |
| `materials/m0010` | `^bronze` | 1 | 1 |
| `materials/m0011` | `^brass` | 3 | 3 |
| `materials/m0012` | `^zinc, primary` | 1 | 1 |
| `materials/m0013` | `^tin,␠` | 1 | 1 |
| `materials/m0014` | `^nickel, 99\.5%` | 1 | 1 |
| `materials/m0015` | `^solder, (bar\|paste)` | 4 | 4 |
| `materials/m0017` | `^gold\b` | 13 | 13 |
| `materials/m0018` | `^silver\b` | 10 | 10 |
| `materials/m0019` | `^palladium` | 4 | 4 |
| `materials/m0022` | `^polyethylene, (hdpe\|ldpe\|lldpe)` | 3 | 3 |
| `materials/m0023` | `^polypropylene` | 1 | 1 |
| `materials/m0024` | `^polystyrene(?! scrap)` | 11 | 11 |
| `materials/m0025` | `^acrylonitrile-butadiene-styrene` | 1 | 1 |
| `materials/m0026` | `^polycarbonate,␠` | 1 | 1 |
| `materials/m0028` | `^polymethyl methacrylate` | 2 | 2 |
| `materials/m0029` | `^polyvinylchloride,␠` | 4 | 4 |
| `materials/m0030` | `^polyethylene terephthalate` | 2 | 2 |
| `materials/m0031` | `^nylon 6` | 3 | 3 |
| `materials/m0031` | `^glass fibre reinforced plastic, polyamide` | 1 | 1 |
| `materials/m0035` | `^epoxy resin,␠` | 2 | 2 |
| `materials/m0037` | `^polyurethane, (flexible\|rigid) foam` | 3 | 3 |
| `materials/m0040` | `^synthetic rubber` | 1 | 1 |
| `materials/m0041` | `^silicone product` | 1 | 1 |
| `materials/m0044` | `^flat glass,␠` | 2 | 2 |
| `materials/m0045` | `^glass fibre, at plant` | 1 | 1 |
| `materials/m0048` | `^ferrite` | 1 | 1 |
| `materials/m0051` | `^glass fibre reinforced plastic, polyester` | 1 | 1 |
| `materials/m0055` | `^(fibreboard\|particle board)(?!, cement bonded)` | 12 | 12 |
| `materials/m0056` | `^corrugated board` | 8 | 8 |
| `materials/m0056` | `^kraft paper` | 2 | 2 |
