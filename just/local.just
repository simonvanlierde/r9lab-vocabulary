# This repo's own recipes; copier updates never touch this file.

# Check vocabulary/*.yaml against itself and the pinned sources, then write dist/ (Turtle, JSON-LD, SHACL shapes, name matches). Needs `just pipeline` first.
rdf:
    uv run r9lab-vocabulary rdf

# Print every name each `names` pattern matches, as scheme/id, source, pattern, name. `--source bafu-2026-v1` for one source, `--summary` for counts.
names *args:
    uv run r9lab-vocabulary names {{ args }}

# Print every Wikidata link beside the item's current label; fails on a missing or redirected item. Live network.
wikidata:
    uv run r9lab-vocabulary wikidata

# Print, as Markdown for the release notes, the concepts added, deprecated, removed, remapped and relabelled since a tag (`just diff v0.1.0`). Fails on a concept id that vanished instead of being deprecated.
diff ref:
    uv run r9lab-vocabulary diff {{ ref }}

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

# Run at the end of `just check`: the SHACL shapes (own and skohub-shapes) over dist/r9lab-vocabulary.ttl, the file a release ships. tests/test_shacl.py runs them on the graph vocabulary/ builds, in CI too.
local-check:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -f dist/r9lab-vocabulary.ttl ] || { echo "local-check: no dist/r9lab-vocabulary.ttl, so SHACL ran only in the tests; \`just rdf\` writes it"; exit 0; }
    shapes=$(mktemp)
    trap 'rm -f "$shapes"' EXIT
    cat shapes/r9lab.shacl.ttl shapes/skohub-skos.shacl.ttl >"$shapes"
    uv run --locked pyshacl -sf turtle -s "$shapes" dist/r9lab-vocabulary.ttl

# Check dist/r9lab-vocabulary.sssom.tsv against the SSSOM schema with sssom-py, run by uvx so it stays out of the lock. Needs `just rdf` first.
sssom-validate:
    uvx --exclude-newer "1 week" --from sssom==0.4.22 sssom validate dist/r9lab-vocabulary.sssom.tsv
