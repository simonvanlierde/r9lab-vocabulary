"""The real vocabulary against the pinned sources `just pipeline` built, not a fixture.

They skip until the pipeline has run. CI runs it first and sets
PIPELINE_OUTPUT_REQUIRED=1, so there a missing output fails instead of skipping.
"""

from __future__ import annotations

import os
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
