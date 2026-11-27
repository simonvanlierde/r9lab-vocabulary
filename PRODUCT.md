# Product

## Platform

web

## Users

- **Vocabulary users.** Researchers who sort the parts and materials in repair and
  disassembly records: a model prompt that scores photos against the pilot classes, an LCA
  study that links a material class to its BAFU activity names, a tool that reads the SSSOM
  crosswalks. They read the built files (`dist/`), never a UI.
- **Raters.** Two domain experts who judge the machine-proposed mappings from R9lab tags to
  concepts, one card at a time. Each opens their own link to the review page, served from one machine, and rates alone.

## Product Purpose

A small, versioned SKOS vocabulary of product types and component and material classes, with
crosswalks to the code lists LCA and waste statistics already use (CPC 2.1, UNU-KEYs, WEEE
categories, Wikidata, PMDco, BAFU). It lets messy lab records be counted and compared. Success
is that a concept id means the same thing in every release, and that each published mapping
says who checked it.

## Positioning

The concepts are sized to what a photo or a part list can tell apart, not to a statistical
code list, and every mapping out is typed (exact, close, broad, narrow). The tag mappings come
from a blind, timed review log, so agreement between raters can be reported per proposal.

## Operating Context

- Concepts are written by hand in `vocabulary/*.yaml`; `just rdf` builds and checks them.
- Proposals for the tag mappings come from machines; raters add verdicts on the review page
  (`src/r9lab_vocabulary/review/`), bound to `127.0.0.1`, following
  [`docs/review-protocol.md`](docs/review-protocol.md). `just curate` builds the published file.
- The review page is the project's only interface. Raters use it on a laptop, with a keyboard,
  in sessions of many cards.

## Capabilities and Constraints

- Concept ids are opaque and never reused; a concept that goes away is deprecated.
- Licensed code lists (UNU-KEYs) are linked by code only, never by name.
- The review page must not bias a verdict: it hides the proposer, shows each card once, keeps
  the order per rater fixed, and times each verdict on the server. A change that could shift
  verdicts or their timing needs a new protocol version.
- The page runs without a build step: server-rendered Jinja templates, htmx, one static script.

## Evidence on Hand

- The R9lab lab corpus tags (`mappings/r9lab-tags.sssom.tsv`) and the review log in
  `mappings/r9lab-tags/`.
- No usage data, testimonials or rater results yet; do not invent any.

## Product Principles

1. Stable ids over tidy ones: deprecate, never delete or renumber.
2. Every claim has a source: a definition cites where it comes from, a mapping who curated it.
3. The review page records judgement; it never steers it. Equal weight for each verdict.
4. Small and checkable: a rule lives in `just check`, not in a reviewer's memory.

## Accessibility & Inclusion

WCAG 2.2 AA for the review page. The command line keeps the rules in
[`docs/accessibility.md`](docs/accessibility.md).
