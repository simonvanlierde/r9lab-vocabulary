# Attribution and reuse terms

This file records what this repository reuses from others, and on what terms.
The code is under Apache-2.0 (see [LICENSE](LICENSE)). That license covers only
the code written here. The source data and everything listed below keep their own terms.

## Reused conventions and identifiers

The vocabulary links to these schemes by identifier. It copies no text from them beyond
the identifiers, except where a concept's own label is the common name of the thing.

| Reused | From | License | Where it lives here |
| --- | --- | --- | --- |
| The six material families as the top of the material axis | Ashby, *Materials Selection in Mechanical Design*, 5th ed., 2017, section 2.2, Fig. 2.1, ISBN 9780081005996 | Cited, not copied | `vocabulary/materials.yaml` |
| CPC 2.1 subclass codes and IRIs | UN Statistics Division; IRIs as served by [vocab.sentier.dev](https://vocab.sentier.dev) | UN terms of use | `cpc:` mappings |
| PMDco term IRIs | [materialdigital/core-ontology](https://github.com/materialdigital/core-ontology) v3.1.2 | CC BY 4.0 | `pmdco:` mappings |
| Wikidata item ids | [Wikidata](https://www.wikidata.org) | CC0 1.0 | `wd:` mappings |
| WEEE categories 1-6, as fragments on the directive's ELI; each product type's category is taken from its UNU-KEY by the UNU-KEY to EU-6 table | Directive 2012/19/EU, Annex III; Baldé et al., *The Global E-waste Monitor 2017*, Annexes, UNU, ITU and ISWA, 2017, checked against Table 2 of the 2026 E-waste Statistics Guidelines | EU legal text, free reuse; codes only | `weee6:` mappings |
| UNU-KEY v1 codes (codes only) | Forti et al., *E-waste Statistics: Guidelines on Classification, Reporting and Indicators*, 2nd ed., UNU, 2018 | CC BY-NC-SA 3.0 IGO; names not copied | `unu1:` mappings |
| SKOS SHACL shapes (`skos.shacl.ttl` at commit ce46984), trailing whitespace trimmed | [skohub-io/skohub-shapes](https://github.com/skohub-io/skohub-shapes) | Apache-2.0 | `tests/fixtures/skohub-skos.shacl.ttl` |
| UNU-KEY v2 codes (codes only), and the v1 code list | Lysaght et al., *E-waste Statistics: Guidelines on Classifications, Reporting and Indicators*, 3rd ed., UNITAR, 2026, [doi:10.5281/zenodo.18328494](https://doi.org/10.5281/zenodo.18328494), Tables 2 and 19 | CC BY-NC-SA 4.0; names not copied | `unu2:` mappings; `FIXED_CODES` in `scheme.py` |
| BAFU activity names, as regular expressions | Life Cycle Inventory database of the Swiss Federal Administration, BAFU:2025 v2 and BAFU:2026 v1 | Patterns only, no data | `names.bafu` fields |

## Source data

This repository doesn't redistribute source data. `data/raw/` and
`data/processed/` are gitignored, and `just pipeline` downloads from each
publisher on every run. CI uploads only the `*.fetch.json` records (URL, timestamp,
checksum, byte count, vintage, the server's Last-Modified and ETag) and, from the weekly
run, a revisions report of old and new checksums. Neither holds values.

Each source's terms are in [`sources.toml`](sources.toml): `terms` and
`terms_url` in the publisher's words, `license` as an SPDX id, and `redistribute`,
whether the raw file may be republished. `just validate` fails when an implemented
source lacks any of them. `just build` copies each output's licence and source into
`data/processed/datapackage.json`. `just attribution` prints these facts as a table: paste it over the one below when you change a source.

`data/fetches.jsonl` is committed. It lists each
version of each source the pipeline has fetched, by checksum, and holds no values.

| Source | Terms as stated by the publisher |
| --- | --- |
| UN Central Product Classification (CPC) Version 2.1, structure file | [United Nations website terms of use](https://www.un.org/en/about-us/terms-of-use) |
| Platform MaterialDigital core ontology (PMDco) v3.1.2 | [Attribution 4.0 International](https://github.com/materialdigital/core-ontology/blob/v3.1.2/LICENSE.txt) |
| Life Cycle Inventory database of the Swiss Federal Administration, BAFU:2025 v2 (Brightway project) | [BAFU:20XY Terms of Use (FOEN, 23 June 2026)](https://www.bafu.admin.ch/dam/en/sd-web/-9ZObeMCZy8A/BAFU-20XY%20Terms%20of%20Use_EN.pdf) |
| Life Cycle Inventory database of the Swiss Federal Administration, BAFU:2026 v1 (EcoSpold1) | [BAFU:20XY Terms of Use (FOEN, 23 June 2026)](https://www.bafu.admin.ch/dam/en/sd-web/-9ZObeMCZy8A/BAFU-20XY%20Terms%20of%20Use_EN.pdf) |
