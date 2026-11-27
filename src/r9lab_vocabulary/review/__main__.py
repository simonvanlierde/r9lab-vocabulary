"""`python -m r9lab_vocabulary.review [--host H] [--port N]`: serve the review page and print each rater's link."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

from r9lab_vocabulary import curate

# Gitignored. Deleting it gives every rater a new link at the next start.
KEY_FILE = Path(".review-secret")


def read_secret() -> bytes:
    """The server's link secret, made on the first start and readable by its owner only.

    `just review-stack` runs this on the host first, as the container sees the file read-only.
    """
    if not KEY_FILE.exists():
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    return KEY_FILE.read_bytes().strip()


def split_list(value: str) -> list[str]:
    """The items of a list separated by commas or spaces."""
    return [item for item in re.split(r"[\s,]+", value) if item]


def main(argv: list[str] | None = None) -> int:
    """Serve the page for the raters in `R9LAB_RATERS`; 2 without valid ORCID CURIEs or a review log.

    `R9LAB_ALLOWED_HOSTS` (separated by commas or spaces, default `127.0.0.1,localhost`) holds the names the page
    is served under, such as a tailnet or tunnel name in front of it.
    """
    parser = argparse.ArgumentParser(prog="r9lab_vocabulary.review", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8740, help="port to listen on (default 8740)")
    args = parser.parse_args(argv)
    raters = split_list(os.environ.get("R9LAB_RATERS", ""))
    if not raters or not all(curate.ORCID.fullmatch(r) for r in raters):
        sys.stderr.write(
            "error: set R9LAB_RATERS to the raters' ORCID CURIEs, such as orcid:0000-0002-1825-0097,"
            " separated by commas or spaces\n"
        )
        return 2
    log = Path(curate.REVIEWS)
    if not log.is_file() or log.stat().st_size == 0:
        sys.stderr.write(f"error: {log} is missing or empty; restore it from git, run from the repository root\n")
        return 2
    if not os.access(log, os.W_OK):
        sys.stderr.write(f"error: {log} is not writable by this user, so no verdict could be saved\n")
        return 2
    import uvicorn  # noqa: PLC0415 - the review extra; the rest of the package runs without it

    from r9lab_vocabulary.review import LOCAL_HOSTS, create_app, rater_token  # noqa: PLC0415

    hosts = tuple(split_list(os.environ.get("R9LAB_ALLOWED_HOSTS", "")) or LOCAL_HOSTS)
    try:
        secret = read_secret()
    except OSError as e:
        sys.stderr.write(f"error: cannot read or make {KEY_FILE}: {e.strerror}\n")
        return 2
    # Bytes of hex. An empty or short key would let anyone derive a rater's link from their ORCID.
    if len(secret) < 32:
        sys.stderr.write(f"error: {KEY_FILE} holds no usable key; delete it to make a new one\n")
        return 2
    sys.stdout.write(
        "Send each rater their own link: the page's address, such as"
        f" http://127.0.0.1:{args.port} or the proxy's, followed by their path.\n"
    )
    for rater in raters:
        sys.stdout.write(f"  {rater}: /r/{rater_token(secret, rater)}\n")
    sys.stdout.flush()
    app = create_app(Path(), raters, secret, hosts)
    # The progress stream stays open; without a timeout, stopping the server waits on it forever.
    uvicorn.run(app, host=args.host, port=args.port, timeout_graceful_shutdown=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
