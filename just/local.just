# This repo's own recipes; copier updates never touch this file.

# Check vocabulary/*.yaml against itself and the pinned sources, then write dist/ (Turtle, JSON-LD, name matches). Needs `just pipeline` first.
rdf:
    uv run r9lab-vocabulary rdf

# Print every name each `names` pattern matches, as scheme/id, source, pattern, name. `--source bafu-2026-v1` for one source, `--summary` for counts.
names *args:
    uv run r9lab-vocabulary names {{ args }}

# Print every Wikidata link beside the item's current label; fails on a missing or redirected item. Live network.
wikidata:
    uv run r9lab-vocabulary wikidata

# Fetch, build and check everything, write dist/, and print how the match counts changed since the last run.
update:
    #!/usr/bin/env bash
    set -euo pipefail
    old=$(mktemp)
    trap 'rm -f "$old"' EXIT
    cp dist/name-matches.csv "$old" 2>/dev/null || : >"$old"
    just pipeline rdf
    if diff "$old" dist/name-matches.csv; then echo "name matches unchanged"; fi

# The tests that read the pinned sources fail, instead of skipping, when the pipeline output is missing. As CI runs them.
test-full: pipeline rdf sssom-validate
    PIPELINE_OUTPUT_REQUIRED=1 uv run pytest

# Check dist/r9lab-vocabulary.sssom.tsv against the SSSOM schema with sssom-py, run by uvx so it stays out of the lock. Needs `just rdf` first.
sssom-validate:
    uvx --from sssom==0.4.23 sssom validate dist/r9lab-vocabulary.sssom.tsv
