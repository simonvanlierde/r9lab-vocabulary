# Install the venv, writing uv.lock if it is missing or stale. CI uses --locked.
py-sync:
    uv sync

# What CI runs: lint, format check, types, tests, dependency audit and licenses. CI also runs the `just pipeline` stages.
py-check:
    uv run --locked ruff check
    uv run --locked ruff format --check
    uv run --locked ty check
    uv run --locked pytest
    uv audit --locked --preview-features audit-command
    d=$(mktemp -d) && trap 'rm -rf "$d"' EXIT && uv export --locked --no-default-groups --no-hashes --no-annotate --no-header --no-emit-project -q -o "$d/requirements.txt" && { test ! -s "$d/requirements.txt" || uv run --locked --with licensecheck==2026.0.8 licensecheck -r "$d/requirements.txt" --zero; }

# Fix what ruff can fix, then format.
py-fmt:
    uv run ruff check --fix
    uv run ruff format

# Tests with a coverage summary.
py-cov:
    uv run pytest --cov --cov-report=term-missing

# Tests only; extra arguments reach pytest (`just py-test -k name`).
py-test *args:
    uv run pytest {{ args }}

# Download each implemented source in sources.toml to data/raw/, with a fetch record.
fetch:
    uv run r9lab-vocabulary fetch

# Turn data/raw/ into data/processed/, verifying each checksum first.
build:
    uv run r9lab-vocabulary build

# Re-read data/processed/ and re-hash data/raw/ against the fetch records.
validate:
    uv run r9lab-vocabulary validate

# Print the Markdown table of implemented sources and their terms, for ATTRIBUTION.md.
attribution:
    uv run r9lab-vocabulary attribution

# One line per source: status, vintage, last fetch, checksum, licence. Reads no network.
status:
    uv run r9lab-vocabulary status

# The whole chain, from the network to validated output.
pipeline: fetch build validate

# Write the data release folder (default `release`, next to sources.toml): the data without the
# sources whose terms forbid redistribution, datapackage.json and SHA256SUMS. `just release` is the project's own tag.
# Run `just pipeline` first.
data-release out='release':
    uv run r9lab-vocabulary release {{ out }}

# Check a data release folder: SHA256SUMS, and the RO-Crate and Croissant files when sources.toml asks for them.
data-release-check out='release':
    uv run r9lab-vocabulary release --check {{ out }}
