# This repo's own recipes; copier updates never touch this file.

# Check vocabulary/*.yaml against itself and the pinned sources, then write dist/ (Turtle, JSON-LD, BAFU candidates). Needs `just pipeline` first.
rdf:
    uv run r9lab-vocabulary rdf

# Print every BAFU activity each `bafu` pattern matches, as scheme/id, release, pattern, name. Pass `--release 2026-v1` for one release.
bafu *args:
    uv run r9lab-vocabulary bafu {{ args }}

# Print every Wikidata link beside the item's current label; fails on a missing or redirected item. Live network.
wikidata:
    uv run r9lab-vocabulary wikidata

# Everything from the network to dist/.
vocab: pipeline rdf
