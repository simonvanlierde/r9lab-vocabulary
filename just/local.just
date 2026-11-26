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

# Rebuild mappings/r9lab-tags.sssom.tsv from the review log in mappings/r9lab-tags/. `just check` fails while it is out of date.
curate:
    uv run python -m r9lab_vocabulary.curate build

# Serve the tag-mapping review page on http://127.0.0.1:<port> for the raters in R9LAB_RATERS (ORCID CURIEs) and print each one's link. Ctrl-C stops it and rebuilds the published file; just still reports the run as interrupted.
review port="8740":
    #!/usr/bin/env bash
    set -u
    trap true INT  # let Ctrl-C stop the page, then still rebuild
    uv run --extra review python -m r9lab_vocabulary.review --port {{ port }}
    status=$?
    uv run python -m r9lab_vocabulary.curate build || exit
    exit "$status"

# The review page in Docker (docker/review/compose.yaml), published on 127.0.0.1:8740 for a proxy to serve. Same variables as `review`, plus R9LAB_ALLOWED_HOSTS and R9LAB_PUBLISH. Ctrl-C stops it and rebuilds the published file.
review-stack:
    #!/usr/bin/env bash
    set -u
    trap true INT  # let Ctrl-C stop the stack, then still rebuild
    R9LAB_UID="$(id -u)" R9LAB_GID="$(id -g)" docker compose -f docker/review/compose.yaml up --build
    status=$?
    docker compose -f docker/review/compose.yaml down
    uv run python -m r9lab_vocabulary.curate build || exit
    exit "$status"

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
# NOTE: .github/workflows/python.yml pins the same sssom version; change both together.
sssom-validate:
    uvx --exclude-newer "1 week" --from sssom==0.4.22 sssom validate dist/r9lab-vocabulary.sssom.tsv

# Check the tag-mapping review log and warn about each verdict on a withdrawn proposal. `just check` runs this last.
local-check:
    uv run --locked python -m r9lab_vocabulary.curate check

# Load dist/r9lab-vocabulary.ttl into a throwaway PyST (tests/pyst/compose.yaml, Docker) and check every scheme and concept statement comes back. Needs `just rdf` first.
pyst-round-trip port="8741":
    #!/usr/bin/env bash
    set -euo pipefail
    compose=(docker compose --progress quiet -f tests/pyst/compose.yaml)
    trap '"${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1' EXIT
    PYST_PORT={{ port }} "${compose[@]}" up --build --detach --wait
    uv run python tests/pyst/round_trip.py dist/r9lab-vocabulary.ttl --url http://127.0.0.1:{{ port }}
