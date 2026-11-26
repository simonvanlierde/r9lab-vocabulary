"""A review page for the tag mappings: one card at a time, blind to what proposed it, each verdict timed.

Run with `just review`. The page appends each verdict to `mappings/r9lab-tags/reviews.sssom.tsv`
as it is given, under the ORCID in `R9LAB_REVIEWER`; `just review` rebuilds the published file when
the page stops. `docs/review-protocol.md` holds the rules a rater follows.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import random
import secrets
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import jinja2
import markupsafe
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from r9lab_vocabulary import checks, curate, scheme

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

HERE = Path(__file__).parent
VERDICTS = {"agree": "1", "disagree": "-1", "unsure": "0"}
RELATION_WORDS = {
    "skos:exactMatch": "is the same as",
    "skos:closeMatch": "is close to",
    "skos:broadMatch": "is a kind of",
    "skos:narrowMatch": "is broader than",
    "skos:relatedMatch": "is related to",
}
# Escape every template: tags are user-typed text, and the default escapes only `.html` names.
# The page must not be framed by another site, which could trick a click on a verdict.
SECURITY_HEADERS = [
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
]
TEMPLATES = Jinja2Templates(env=jinja2.Environment(loader=jinja2.FileSystemLoader(HERE / "templates"), autoescape=True))


class Session:
    """One rater's queue over the log: proposals they have not judged, in an order seeded by their ORCID."""

    def __init__(self, root: Path, reviewer: str) -> None:
        self.root, self.reviewer = root, reviewer
        self.csrf = secrets.token_urlsafe(24)
        self.shown_at: dict[tuple[str, str, str], float] = {}
        _, _, self.predictions = curate.read(root / curate.PREDICTIONS)
        self.concepts = {
            f"{slug}:{cid}": c for slug, s in scheme.load(root / "vocabulary").items() for cid, c in s.concepts.items()
        }
        self.proposed = {curate.key(p) for p in self.predictions}
        self.lock = threading.Lock()  # one verdict per card, even from a double click or two tabs
        self.order = list(range(len(self.predictions)))
        random.Random(reviewer).shuffle(self.order)  # noqa: S311 - an order, not a secret; the seed is the ORCID, so a rater sees the same order again

    def reviews(self) -> list[dict[str, str]]:
        """Every rater's verdicts, read from the log each time, so another rater's page shows up."""
        return curate.read(self.root / curate.REVIEWS)[2]

    def queue(self) -> list[int]:
        """Indexes into the proposals this rater has not judged yet, in their order."""
        done = {curate.key(r) for r in self.reviews() if r["reviewer_id"] == self.reviewer}
        return [i for i in self.order if curate.key(self.predictions[i]) not in done]

    def card(self) -> dict[str, str | bool] | None:
        """The next proposal, blinded: no justification, tool, confidence or comment. Notes when it was shown."""
        queue = self.queue()
        if not queue:
            return None
        row = self.predictions[queue[0]]
        self.shown_at.setdefault(curate.key(row), time.monotonic())
        concept = self.concepts.get(row["object_id"], {})
        return {
            "i": str(queue[0]),
            "tag": row["subject_label"],
            "relation": RELATION_WORDS.get(row["predicate_id"], row["predicate_id"]),
            "no_term": row["object_id"] == checks.NO_TERM,
            "concept": row["object_label"],
            "concept_id": row["object_id"],
            "definition": concept.get("definition", ""),
            "note": concept.get("note", ""),
        }

    def progress(self) -> dict[str, int]:
        """Cards judged per rater, plus the total under `of`. Verdicts on withdrawn proposals do not count."""
        done: dict[str, set] = {}
        for r in self.reviews():
            if curate.key(r) in self.proposed:
                done.setdefault(r["reviewer_id"], set()).add(curate.key(r))
        return {rater: len(keys) for rater, keys in sorted(done.items())} | {"of": len(self.predictions)}

    def record(self, i: int, verdict: str) -> None:
        """Append the verdict on card `i`; 409 when `i` is not the card this rater is on."""
        with self.lock:
            queue = self.queue()
            if not queue or queue[0] != i:
                raise HTTPException(409, "this card was already judged; reload the page")
            row = self.predictions[i]
            shown = self.shown_at.pop(curate.key(row), None)
            curate.append_review(self.root, {
                **{c: row[c] for c in (*curate.KEY, "mapping_justification")},
                "reviewer_id": self.reviewer,
                "reviewer_agreement": VERDICTS[verdict],
                "review_seconds": f"{time.monotonic() - shown:.1f}" if shown is not None else "",
                "review_date": dt.datetime.now(tz=dt.UTC).date().isoformat(),
            })  # fmt: skip


def same_origin(request: Request, session: Session, token: str) -> None:
    """Refuse a verdict from another site: browsers mark it in Sec-Fetch-Site, and it cannot read the token."""
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        raise HTTPException(403, "cross-site request")
    if not secrets.compare_digest(token, session.csrf):
        raise HTTPException(403, "bad form token; reload the page")


class SecurityHeaders:
    """Add `SECURITY_HEADERS` to every response, the progress stream included."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request on, adding the headers to the response's start message."""

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":  # noqa: PLR2004 - the ASGI message type
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def error_in_place_of_card(request: Request, exc: HTTPException) -> Response:
    """For htmx, an error takes the card's place as a message, so the page says what to do next."""
    if not request.headers.get("hx-request"):
        return await http_exception_handler(request, exc)
    html = markupsafe.Markup('<p id="card" role="alert">{} <a href="/">Reload</a></p>').format(exc.detail)
    return HTMLResponse(html, status_code=exc.status_code)


def create_app(root: Path, reviewer: str) -> FastAPI:
    """The review page for the log under `root`, recording verdicts as `reviewer` (an ORCID CURIE)."""
    session = Session(root, reviewer)
    app = FastAPI(title="R9lab tag mapping review", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    # Only this machine's names: a site that points its own name at 127.0.0.1 gets a 400.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.add_middleware(SecurityHeaders)
    # Starlette types handlers as taking any Exception; this one is registered for HTTPException only.
    app.add_exception_handler(HTTPException, error_in_place_of_card)  # ty: ignore[invalid-argument-type]

    @app.get("/", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        context = {"s": session, "card": session.card(), "progress": session.progress()}
        return TEMPLATES.TemplateResponse(request, "page.jinja", context)

    @app.post("/verdict")
    def verdict(
        request: Request,
        i: Annotated[int, Form()],
        verdict: Annotated[str, Form()],
        token: Annotated[str, Form()],
        hx_request: Annotated[str | None, Header()] = None,
    ) -> Response:
        same_origin(request, session, token)
        if verdict not in VERDICTS:
            raise HTTPException(422, f"verdict must be one of {', '.join(VERDICTS)}")
        session.record(i, verdict)
        if not hx_request:  # a plain form post, without JavaScript
            return RedirectResponse("/", status_code=303)
        return TEMPLATES.TemplateResponse(request, "card.jinja", {"s": session, "card": session.card()})

    @app.get("/progress")
    async def progress(request: Request) -> StreamingResponse:
        """Every rater's count, sent again whenever the review log changes (another rater's page included)."""

        async def stream() -> AsyncIterator[str]:
            seen = None
            while not await request.is_disconnected():
                mtime = (root / curate.REVIEWS).stat().st_mtime_ns
                if mtime != seen:
                    seen = mtime
                    html = TEMPLATES.get_template("progress.jinja").render(progress=session.progress())
                    yield f"data: {html.replace(chr(10), '')}\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
