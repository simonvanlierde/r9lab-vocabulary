# Open Repair Data Standard product crosswalk

Status **proposed**, 2026-11-27.

The [review table](../../mappings/ords-v0.3-eee.csv) covers all 40 codes in
the ORDS v0.3 electrical and electronic equipment (EEE) codelist. Each row
records one proposed link or an explicit `no_match`, with its reason.
The R9lab columns use stable IDs from the [product scheme](../../vocabulary/products.yaml).
The upstream codelist keeps its CC BY-SA 4.0 terms. The review table uses ORDS
codes and independently written notes.
[Standard §3.4.2](https://standard.openrepair.org/standard.html#product-category-values) ·
[Pinned codelist](https://media.githubusercontent.com/media/openrepair/data/2af16342c751f56e28e2f62d018f051e7f22aed0/OpenRepairData_v0.3_Product_Categories_eee.csv) ·
[Reuse terms](https://github.com/openrepair/data/tree/2af16342c751f56e28e2f62d018f051e7f22aed0)

Read each proposed relation **from R9lab to ORDS**. After review, an exact
or broad link can support a rollup to the ORDS category. A reverse lookup
through any broad or close relation needs item evidence, including when
the table has just one candidate. Keep the original `product_category_id`
when joining ORDS records. A `no_match` leaves the product ID blank.

## Check the draft

Run the offline check from the repository root. It checks the table against
the 40 pinned codes and IDs of live leaf product types. It allows one
exact or broad rollup per product type.

```sh
uv run --locked python -m r9lab_vocabulary.ords
```

To verify against the publisher's bytes, download the pinned codelist to
the ignored raw data folder. The checker verifies its SHA-256 before
reading the IDs.

```sh
curl --fail --location --max-time 30 --output data/raw/ords-v0.3-eee.csv \
  https://media.githubusercontent.com/media/openrepair/data/2af16342c751f56e28e2f62d018f051e7f22aed0/OpenRepairData_v0.3_Product_Categories_eee.csv &&
uv run --locked python -m r9lab_vocabulary.ords --codelist data/raw/ords-v0.3-eee.csv
```

## Before publication

Review the close matches, the boundary between ORDS 9 and 39 for hair
dryers, and the foot-file and docking-station proposals. The CSV preserves
relation grades and unresolved categories for review. It stays separate from
the vocabulary's production RDF and SSSOM exports.

## Export positive proposals

Use `--sssom` to write a separate draft TSV. It uses the pinned codelist
as the source of each literal category code. The review table still carries
all `no_match` dispositions.

```sh
uv run --locked python -m r9lab_vocabulary.ords --sssom > ords-v0.3-eee.draft.sssom.tsv
```

The pinned `sssom-py` 0.4.22 validates this TSV. A TSV-to-TSV conversion
preserved all 20 proposals, including the relation and source version.
Use the TSV for SSSOM exchange. The default RDF conversion drops the target
type and codelist source, so a production RDF representation still needs
a format that preserves both. [ADR 0007](../decisions/0007-outside-codes-without-iris.md)
