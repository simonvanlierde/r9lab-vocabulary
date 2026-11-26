"""A review page for the tag mappings: one card at a time, blind to what proposed it, each verdict timed.

Run with `just review`, or `just review-stack` in Docker. The page appends each verdict to
`mappings/r9lab-tags/reviews.sssom.tsv` as it is given, and both recipes rebuild the published file
when the page stops. `docs/review-protocol.md` holds the rules a rater follows.

Each rater signs in by opening their own link, `/r/<token>`, which sets a cookie. The token is an
HMAC of their ORCID under a secret that never leaves the server, so whoever holds the link reviews
as that rater: send it to them alone.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import math
import secrets
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import jinja2
import markupsafe
from fastapi import FastAPI, Form, Header, HTTPException, Request
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
# The page must not be framed by another site, which could trick a click on a verdict, and loads
# nothing from elsewhere.
SECURITY_HEADERS = [
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"default-src 'self'; frame-ancestors 'none'"),
    (b"x-content-type-options", b"nosniff"),
]
LOCAL_HOSTS = ("127.0.0.1", "localhost")
COOKIE = "r9lab_rater"
CARD_ERROR = markupsafe.Markup('<p id="card" role="alert">{} <a href="/">Reload</a></p>')
PAGE_ERROR = markupsafe.Markup('<!doctype html><html lang="en"><title>Tag mapping review</title><p role="alert">{}</p>')
TEMPLATES = Jinja2Templates(env=jinja2.Environment(loader=jinja2.FileSystemLoader(HERE / "templates"), autoescape=True))


class Session:
    """One rater's queue over the log: proposals they have not judged, in an order seeded by their ORCID."""

    def __init__(self, root: Path, reviewer: str, lock: threading.Lock | None = None) -> None:
        self.root, self.reviewer = root, reviewer
        self.csrf = secrets.token_urlsafe(24)
        self.shown_at: dict[tuple[str, str, str], float] = {}
        _, _, self.predictions = curate.read(root / curate.PREDICTIONS)
        self.concepts = {
            f"{slug}:{cid}": c for slug, s in scheme.load(root / "vocabulary").items() for cid, c in s.concepts.items()
        }
        self.proposed = {curate.key(p): p for p in self.predictions}
        # One verdict per card, even from a double click or two tabs; the app shares one lock
        # between its raters, so two appends to the log never interleave.
        self.lock = lock or threading.Lock()
        # Sorting on a hash of ORCID and key gives each rater their own order, the same after a
        # restart, and a new proposal slots in without moving the others.
        self.order = sorted(self.proposed, key=self.card_id)
        self.last: tuple[tuple[str, str, str], str] | None = None  # this page's last verdict, for undo
        self.again: tuple[str, str, str] | None = None  # an undone card, shown before the queue

    def card_id(self, key: tuple[str, str, str]) -> str:
        """The card's name in the form: says nothing about where the proposal sits in the file."""
        return hashlib.sha256("\t".join((self.reviewer, *key)).encode()).hexdigest()

    def reviews(self) -> list[dict[str, str]]:
        """Every rater's verdicts, read from the log each time, so another rater's page shows up."""
        return curate.read(self.root / curate.REVIEWS)[2]

    def queue(self) -> list[tuple[str, str, str]]:
        """Keys of the proposals this rater has not judged yet, in their order."""
        done = {curate.key(r) for r in self.reviews() if r["reviewer_id"] == self.reviewer}
        return [k for k in self.order if k not in done]

    def current(self) -> tuple[str, str, str] | None:
        """The key of the card this rater is on: an undone one, else the first in their queue."""
        return self.again or next(iter(self.queue()), None)

    def card(self) -> dict[str, str | bool] | None:
        """The next proposal, blinded: no justification, tool, confidence or comment. Notes when it was shown."""
        key = self.current()
        if key is None:
            return None
        row = self.proposed[key]
        self.shown_at.setdefault(key, time.monotonic())
        concept = self.concepts.get(row["object_id"], {})
        return {
            "card": self.card_id(key),
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

    def record(self, card: str, verdict: str, away: float = 0.0) -> None:
        """Append the verdict on `card`, its seconds less the `away` the page reports (hidden or paused).

        409 when `card` is not the card this rater is on, 500 when the log refuses the row.
        """
        with self.lock:
            key = self.current()
            if key is None or self.card_id(key) != card:
                raise HTTPException(409, "This card was already judged.")
            row = self.proposed[key]
            shown = self.shown_at.get(key)
            seconds = "" if shown is None else f"{max(time.monotonic() - shown - away, 0):.1f}"
            try:
                curate.append_review(self.root, {
                    **{c: row[c] for c in (*curate.KEY, "mapping_justification")},
                    "reviewer_id": self.reviewer,
                    "reviewer_agreement": VERDICTS[verdict],
                    "review_seconds": seconds,
                    "review_date": dt.datetime.now(tz=dt.UTC).date().isoformat(),
                })  # fmt: skip
            except ValueError as e:
                raise HTTPException(500, str(e)) from e
            self.shown_at.pop(key, None)  # only now: a failed write keeps the time for the retry
            self.last, self.again = (key, verdict), None

    def undo(self) -> None:
        """Show the last judged card again; its new verdict is a new row, and the latest row counts."""
        with self.lock:
            if self.last is None:
                raise HTTPException(409, "Nothing to undo.")
            if (showing := self.current()) is not None:
                self.shown_at.pop(showing, None)  # its clock starts again when it comes back
            self.again, self.last = self.last[0], None


def rater_token(secret: bytes, reviewer: str) -> str:
    """The token in a rater's link: the same for one secret and ORCID, so a link outlives a restart."""
    return hmac.new(secret, reviewer.encode(), hashlib.sha256).hexdigest()[:32]


def session_of(sessions: dict[str, Session], token: str) -> Session | None:
    """The session whose link token this is, compared in constant time; None for an unknown token."""
    return next((s for t, s in sessions.items() if secrets.compare_digest(t, token)), None)


def signed_in(sessions: dict[str, Session], request: Request) -> Session:
    """The session of the rater whose cookie this is; 401 without one."""
    if (session := session_of(sessions, request.cookies.get(COOKIE, ""))) is None:
        raise HTTPException(401, "Open the review link you were given to sign in.")
    return session


def not_cross_site(request: Request) -> None:
    """Refuse a request another site's page made: browsers mark it in Sec-Fetch-Site.

    A cross-site GET of the page would start a card's clock, and of the stream would hold it open.
    """
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        raise HTTPException(403, "cross-site request")


def same_origin(request: Request, session: Session, token: str) -> None:
    """Refuse a verdict from another site: it is marked cross-site, and it cannot read the token."""
    not_cross_site(request)
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
    """An error as a message: in the card's place for htmx, else as a page, so a rater reads what to do next."""
    page = CARD_ERROR if request.headers.get("hx-request") else PAGE_ERROR
    html = page.format(exc.detail)
    return HTMLResponse(html, status_code=exc.status_code, headers=exc.headers)


def next_card(request: Request, session: Session, hx_request: str | None) -> Response:
    """After a verdict or an undo: the card that is up now for htmx, or back to the page without JavaScript."""
    if not hx_request:
        return RedirectResponse("/", status_code=303)
    return TEMPLATES.TemplateResponse(request, "card.jinja", {"s": session, "card": session.card()})


def progress_event(session: Session) -> str:
    """One server-sent event carrying the progress line."""
    html = TEMPLATES.get_template("progress.jinja").render(progress=session.progress(), s=session)
    return f"data: {html.replace(chr(10), '')}\n\n"


async def progress_stream(request: Request, session: Session) -> AsyncIterator[str]:
    """A progress event now and after each change to the log, until the page closes or the server stops."""
    seen = None
    try:
        while not await request.is_disconnected():
            stat = (session.root / curate.REVIEWS).stat()
            if (stat.st_mtime_ns, stat.st_size) != seen:  # size too: two appends can share an mtime tick
                seen = stat.st_mtime_ns, stat.st_size
                yield progress_event(session)
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        return  # the server is stopping; nothing to report


def create_app(
    root: Path, reviewers: list[str], secret: bytes, allowed_hosts: tuple[str, ...] = LOCAL_HOSTS
) -> FastAPI:
    """The review page for the log under `root`, for `reviewers` (ORCID CURIEs) who sign in with their links.

    `allowed_hosts` are the names the page answers to: a site that points its own name at the
    server gets a 400, so add only the names the page is served under.
    """
    lock = threading.Lock()
    sessions = {rater_token(secret, r): Session(root, r, lock) for r in reviewers}

    app = FastAPI(title="R9lab tag mapping review", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(allowed_hosts))
    app.add_middleware(SecurityHeaders)
    # Starlette types handlers as taking any Exception; this one is registered for HTTPException only.
    app.add_exception_handler(HTTPException, error_in_place_of_card)  # ty: ignore[invalid-argument-type]

    @app.get("/r/{token}")
    def sign_in(request: Request, token: str) -> Response:
        """Set the rater's cookie and go to the page. Open to other sites: the link arrives by mail or chat."""
        if session_of(sessions, token) is None:
            raise HTTPException(404, "This review link is not known; ask for a new one.")
        response = RedirectResponse("/", status_code=303)
        # Lax, not Strict: a Strict cookie is held back from the redirect after a click in a mail.
        response.set_cookie(
            COOKIE, token, max_age=90 * 86400, httponly=True, samesite="lax", secure=request.url.is_secure
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        not_cross_site(request)
        session = signed_in(sessions, request)
        context = {"s": session, "card": session.card(), "progress": session.progress()}
        return TEMPLATES.TemplateResponse(request, "page.jinja", context)

    @app.post("/verdict")
    def verdict(
        request: Request,
        card: Annotated[str, Form()],
        verdict: Annotated[str, Form()],
        token: Annotated[str, Form()],
        away: Annotated[float, Form()] = 0.0,
        hx_request: Annotated[str | None, Header()] = None,
    ) -> Response:
        session = signed_in(sessions, request)
        same_origin(request, session, token)
        if verdict not in VERDICTS:
            raise HTTPException(422, f"verdict must be one of {', '.join(VERDICTS)}")
        if not math.isfinite(away) or away < 0:
            raise HTTPException(422, "away must be a number of seconds, 0 or more")
        session.record(card, verdict, away)
        return next_card(request, session, hx_request)

    @app.post("/undo")
    def undo(
        request: Request, token: Annotated[str, Form()], hx_request: Annotated[str | None, Header()] = None
    ) -> Response:
        session = signed_in(sessions, request)
        same_origin(request, session, token)
        session.undo()
        return next_card(request, session, hx_request)

    @app.get("/progress")
    async def progress(request: Request) -> StreamingResponse:
        """Every rater's count, sent again whenever the review log changes (another rater's page included)."""
        not_cross_site(request)
        return StreamingResponse(progress_stream(request, signed_in(sessions, request)), media_type="text/event-stream")

    return app
