---
name: R9lab tag mapping review
description: A blind, timed rating page for one expert at a time; it records judgement and never steers it.
colors:
  ground: "Canvas"
  text: "CanvasText"
  muted: "color-mix(in srgb, CanvasText 72%, Canvas)"
  line: "color-mix(in srgb, CanvasText 45%, Canvas)"
  hover: "color-mix(in srgb, CanvasText 8%, Canvas)"
  focus: "Highlight"
typography:
  body:
    fontFamily: "system-ui, sans-serif"
    fontSize: "17px"
    lineHeight: 1.45
  tag:
    fontFamily: "system-ui, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 600
  concept:
    fontFamily: "system-ui, sans-serif"
    fontSize: "1.25rem"
  small:
    fontFamily: "system-ui, sans-serif"
    fontSize: "0.9rem"
rounded:
  key: "0.25rem"
  button: "0.5rem"
  card: "0.75rem"
spacing:
  gap: "0.5rem"
  card: "1rem"
components:
  card:
    backgroundColor: "{colors.ground}"
    rounded: "{rounded.card}"
    padding: "{spacing.card}"
    width: "34rem"
  verdict-button:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.text}"
    rounded: "{rounded.button}"
    height: "3rem"
  verdict-button-hover:
    backgroundColor: "{colors.hover}"
---

# Design

The page lives in `src/r9lab_vocabulary/review/` (templates, `static/review.css`, `static/review.js`).
[PRODUCT.md](PRODUCT.md) says who uses it, and [docs/review-protocol.md](docs/review-protocol.md)
holds the rules it must keep. A change that could shift a verdict or its timing needs a new
protocol version.

## Overview

One card on a plain page, nothing else to look at. The design is neutral on purpose: the page
records an expert's verdict and its timing, so anything that draws the eye to one answer, or slows
one answer down, is a defect. Plainness here is the product, not a missing style.

## Colors

System colours only (`Canvas`, `CanvasText`, `Highlight`), mixed for muted text and lines, so light,
dark and forced-colours modes get the same emphasis without a second palette. Muted text is about
9:1 against the ground and lines at least 3.3:1, in both modes. No hue carries meaning: there is no
green for Agree or red for Disagree.

## Typography

The platform sans at 17px. The tag is the largest text, then the concept label; the relation is
bold at body size, because it decides the verdict. The concept id, notes and help are smaller and
muted.

## Layout

A single column, at most 34rem wide, centred, 1rem padding. The header holds progress and Pause on
one line, the help line below. The card follows, then the line saying what was recorded, with Undo.
At phone width the three verdict buttons stay in one row.

## Elevation & Depth

None. The card is a 1px line, the pause notice a dashed one. No shadows.

## Shapes

Rounded corners in three steps: keys 0.25rem, buttons 0.5rem, the card 0.75rem.

## Components

- **Verdict buttons**: Agree, Unsure, Disagree, in that fixed order, identical in size, colour and
  border. Each has a one-letter key (`a`, `u`, `d`). They are disabled while a verdict is on its way.
- **Card tag**: the heading; it takes focus when a card appears (`tabindex="-1"`, no ring), so no
  verdict button ever looks preselected.
- **Recorded line**: a `role="status"` line naming the tag and verdict just recorded, with Undo (`z`).
- **Pause**: a toggle button (`aria-pressed`, `p`) that hides the card and stops the clock.
- **Focus ring**: 3px `Highlight` outline, 2px offset, on `:focus-visible` only.

## Do's and Don'ts

- Do keep the three verdicts identical. Don't colour, enlarge, reorder or pre-focus one of them.
- Do keep every timing-relevant behaviour on the server or reported to it (`away`).
- Don't show anything that hints at what proposed a mapping: tool, confidence, justification.
- Don't add motion or a success flourish after a verdict; the next card is the feedback.
- Don't load anything from another origin: the CSP is `default-src 'self'`.
