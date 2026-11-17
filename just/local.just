# This repo's own recipes; copier updates never touch this file.

# Check vocabulary/*.yaml against itself and the pinned sources, then write dist/ (Turtle, JSON-LD, BAFU candidates). Needs `just pipeline` first.
rdf:
    uv run r9lab-vocabulary rdf

# Print every Wikidata link beside the item's current label; fails on a missing or redirected item. Live network.
wikidata:
    uv run r9lab-vocabulary wikidata

# Everything from the network to dist/.
vocab: pipeline rdf
