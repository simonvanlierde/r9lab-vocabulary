"""The real vocabulary against the pinned sources `just pipeline` built, not a fixture.

They skip until the pipeline has run. CI runs it first and sets
PIPELINE_OUTPUT_REQUIRED=1, so there a missing output fails instead of skipping.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from r9lab_vocabulary import pipeline, scheme

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def known() -> Iterator[dict[str, set[str]]]:
    before = Path.cwd()
    os.chdir(ROOT)
    try:
        yield pipeline.known_codes()
    except FileNotFoundError as e:
        if os.environ.get("PIPELINE_OUTPUT_REQUIRED") == "1":
            pytest.fail(str(e))
        pytest.skip(str(e))
    finally:
        os.chdir(before)


def test_every_cpc_code_and_pmdco_id_is_in_the_pinned_sources(known: dict[str, set[str]]):
    assert scheme.check_codes(scheme.load(ROOT / "vocabulary"), known) == []


def test_the_pinned_sources_are_the_expected_size(known: dict[str, set[str]]):
    assert len(known["cpc"]) == 4596
    assert {"PMD_0000852", "PMD_0010003"} <= known["pmdco"]


@pytest.fixture(scope="module")
def lists() -> Iterator[dict[str, dict[str, list[str]]]]:
    before = Path.cwd()
    os.chdir(ROOT)
    try:
        yield pipeline.name_lists()
    except FileNotFoundError as e:
        if os.environ.get("PIPELINE_OUTPUT_REQUIRED") == "1":
            pytest.fail(str(e))
        pytest.skip(str(e))
    finally:
        os.chdir(before)


@pytest.fixture(scope="module")
def matches(lists: dict[str, dict[str, list[str]]]) -> list[scheme.Match]:
    return scheme.name_matches(scheme.load(ROOT / "vocabulary"), lists)


def test_the_pinned_bafu_releases_are_the_published_size(lists: dict[str, dict[str, list[str]]]):
    # Process counts as published: 11,747 in 2025 v2 (bw2io databases.json), 11,947 in 2026 v1 (sentier-brightway).
    # Each has 1,289 withdrawn "xx" datasets, which are not live.
    assert {v: len(n) + 1289 for v, n in lists["bafu"].items()} == {"2025-v2": 11747, "2026-v1": 11947}


def test_every_name_pattern_matches_a_live_name_in_every_version(matches: list[scheme.Match]):
    assert [m[:5] for m in matches if not m[5]] == []


def test_every_branch_of_an_alternation_matches_something(matches: list[scheme.Match]):
    # The first (a|b|...) group of each pattern, one branch at a time: a dead branch passes the
    # whole-pattern check while hiding a misspelt name. Nested groups are not split.
    dead = []
    for slug, cid, _, _, pattern, hits in matches:
        if m := re.search(r"\(([^()]*\|[^()]*)\)", pattern):
            for branch in m.group(1).split("|"):
                one = f"{pattern[: m.start()]}({branch}){pattern[m.end() :]}"
                if not any(re.search(one, n, re.IGNORECASE) for n in hits):
                    dead.append((f"{slug}/{cid}", pattern, branch))
    assert sorted(set(dead)) == []
