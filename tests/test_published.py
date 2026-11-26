"""The real vocabulary against the pinned sources `just pipeline` built, not a fixture.

They skip until the pipeline has run. CI runs it first and sets
PIPELINE_OUTPUT_REQUIRED=1, so there a missing output fails instead of skipping.
The narrowed-pattern test also runs on a literal copy of the names, so `just check`
covers it without the pipeline.
"""

from __future__ import annotations

import re

import pytest
from conftest import ROOT, built

from r9lab_vocabulary import checks, pipeline, scheme


@pytest.fixture(scope="module")
def known() -> dict[str, set[str]]:
    return built(pipeline.known_codes)


def test_every_cpc_code_and_pmdco_id_is_in_the_pinned_sources(known: dict[str, set[str]]):
    assert checks.check_codes(scheme.load(ROOT / "vocabulary"), known) == []


def test_the_pinned_sources_are_the_expected_size(known: dict[str, set[str]]):
    assert len(known["cpc"]) == 4596
    assert {"PMD_0000852", "PMD_0010003"} <= known["pmdco"]


@pytest.fixture(scope="module")
def lists() -> dict[str, dict[str, list[str]]]:
    return built(pipeline.name_lists)


@pytest.fixture(scope="module")
def matches(lists: dict[str, dict[str, list[str]]]) -> list[scheme.Match]:
    return checks.name_matches(scheme.load(ROOT / "vocabulary"), lists)


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


# Names a narrowed pattern must leave out ("not") or take ("is"), as spelt in both pinned BAFU releases.
_CELLS = ["LFP", "LTO", "Li-ion, NMC111", "NCA", "NMC-111", "NMC-622"]
NARROWED = {
    "Polystyrene scrap, old, at plant": {"not": {"materials/m0024"}},
    "Particle board, cement bonded, at plant": {"not": {"materials/m0055"}},
    "LCD flat screen, 17 inches, at plant": {"not": {"components/c0015"}},
    "Sheet rolling, steel": {"not": {"materials/m0003"}},
    "Sheet rolling, chromium steel": {"not": {"materials/m0004"}},
    "Sheet rolling, aluminium": {"not": {"materials/m0007"}},
    "Wire drawing, copper": {"not": {"materials/m0009"}},
    **{f"Battery cell, {c}": {"is": {"components/c0024"}, "not": {"components/c0002"}} for c in _CELLS},
}


@pytest.mark.parametrize("source", ["literal", "pinned"])
def test_the_narrowed_patterns_keep_their_names_out(source: str, request: pytest.FixtureRequest):
    if source == "pinned":
        lists = request.getfixturevalue("lists")
        assert all(set(NARROWED) <= set(names) for names in lists["bafu"].values())
    else:
        lists = {"bafu": {"2025-v2": list(NARROWED), "2026-v1": list(NARROWED)}}
    hit: dict[str, set[str]] = {n: set() for n in NARROWED}
    for slug, cid, _, _, _, names in checks.name_matches(scheme.load(ROOT / "vocabulary"), lists):
        for n in set(names) & set(NARROWED):
            hit[n].add(f"{slug}/{cid}")
    wrong = {n: hit[n] for n, want in NARROWED.items() if hit[n] & want["not"] or not want.get("is", set()) <= hit[n]}
    assert wrong == {}
