"""Checks against live services, run only on the weekly schedule (TRIPWIRE=1).

Wikidata merges and deletes items, so a link that was live when it was added can die
later. The weekly run fails on it instead of a pull request.
"""

from __future__ import annotations

import os

import pytest
from conftest import ROOT

from r9lab_vocabulary import pipeline

pytestmark = pytest.mark.skipif(
    os.environ.get("TRIPWIRE") != "1", reason="live network; the weekly run sets TRIPWIRE=1"
)


def test_every_wikidata_link_is_live(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.chdir(ROOT)
    code = pipeline.wikidata()
    dead = [line for line in capsys.readouterr().out.splitlines() if line.endswith("MISSING OR REDIRECTED")]
    assert code == 0, dead
