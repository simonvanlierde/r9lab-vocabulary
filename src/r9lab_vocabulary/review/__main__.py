"""`python -m r9lab_vocabulary.review [--port N]`: serve the review page on this machine only."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from r9lab_vocabulary import curate


def main(argv: list[str] | None = None) -> int:
    """Serve the page for the rater named in `R9LAB_REVIEWER`; 2 without an ORCID CURIE or a review log."""
    parser = argparse.ArgumentParser(prog="r9lab_vocabulary.review", description=__doc__)
    parser.add_argument("--port", type=int, default=8740, help="port on 127.0.0.1 (default 8740)")
    args = parser.parse_args(argv)
    reviewer = os.environ.get("R9LAB_REVIEWER", "")
    if not curate.ORCID.fullmatch(reviewer):
        sys.stderr.write("error: set R9LAB_REVIEWER to your ORCID CURIE, such as orcid:0000-0002-1825-0097\n")
        return 2
    log = Path(curate.REVIEWS)
    if not log.is_file() or log.stat().st_size == 0:
        sys.stderr.write(f"error: {log} is missing or empty; restore it from git, run from the repository root\n")
        return 2
    import uvicorn  # noqa: PLC0415 - the review extra; the rest of the package runs without it

    from r9lab_vocabulary.review import create_app  # noqa: PLC0415

    # The progress stream stays open; without a timeout, stopping the server waits on it forever.
    uvicorn.run(create_app(Path(), reviewer), host="127.0.0.1", port=args.port, timeout_graceful_shutdown=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
