# Review protocol for the tag mappings

Version 0, 26 November 2026. A change to these rules gets a new version and date here; each
verdict carries its `review_date`, so it can be matched to the rules it followed.

## What a rater judges

Each card shows one R9lab tag, as users typed it, and one proposed link to a concept: the
relation in words ("is a kind of" for `skos:broadMatch`, "is the same as" for `skos:exactMatch`,
"is close to" for `skos:closeMatch`) and the concept's label, definition and scope note. A card
can also say the tag has no concept in the vocabulary (`sssom:NoTermFound`).

- **Agree**: the link holds as written, relation included. For a no-concept card: no concept in
  the vocabulary fits the tag.
- **Disagree**: the link is wrong. A right concept with the wrong relation (`exactMatch` where the
  tag is narrower) is a disagree too. For a no-concept card: some concept does fit.
- **Unsure**: the tag and the concept's text are not enough to decide.

Judge the tag as a user would mean it on a product's part list. Misspellings count as the word
they misspell.

## Blinding and order

- The card hides what proposed the link, the proposer's justification, confidence and comment.
- Each rater gets every proposal once, in an order set by their ORCID, so two raters see different
  orders and one rater sees the same order after a restart. A new proposal slots in without
  moving the others.
- Raters work alone. The page shows how many cards each rater has judged, never their verdicts.
- Do not look a card up elsewhere before the verdict; the time a verdict takes is part of the
  record.

## What is recorded

Each verdict appends one row to `mappings/r9lab-tags/reviews.sssom.tsv`: the mapping, the
rater's ORCID CURIE (`reviewer_id`), `reviewer_agreement` (1 agree, -1 disagree, 0 unsure),
`review_date` (the UTC date), and `review_seconds`, the time from the card's first showing since the
page last started to the verdict, measured on the server. The page shows each card once; a rater who
changes their mind adds a row to the log by hand. Their latest row counts, and the earlier one stays.

## How verdicts become the published file

`just curate` builds `mappings/r9lab-tags.sssom.tsv` from proposals and verdicts:

- a proposal one or more raters agree with, and none rejects, is published with those raters
  in `reviewer_id`;
- a proposal that only drew rejections is left out, and `just check` fails until its tag gets a
  new proposal; the rejections stay in the log;
- a proposal with raters on both sides, or with no verdict yet, is published with no reviewer,
  as a proposal.

Agreement between raters is computed from the latest verdict per rater per mapping.
