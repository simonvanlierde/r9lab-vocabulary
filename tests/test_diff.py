"""`just diff <tag>`: what changed between two states of the vocabulary, on the golden fixture and its next release."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from r9lab_vocabulary import pipeline, scheme

if TYPE_CHECKING:
    import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OLD, NEW = FIXTURES / "golden" / "vocabulary", FIXTURES / "next" / "vocabulary"


def test_both_fixture_states_break_no_rule():
    for d in (OLD, NEW):
        assert scheme.validate(scheme.load(d), {}) == [], d


def test_the_diff_lists_what_was_added_deprecated_remapped_and_relabelled():
    lines, ok = scheme.diff(scheme.load(OLD), scheme.load(NEW))
    assert ok
    assert lines == [
        "### Added",
        "",
        "- `tools/t04` torque wrench",
        "",
        "### Deprecated",
        "",
        "- `parts/p02` nut, replaced by `parts/p01`",
        "",
        "### Mappings",
        "",
        "- `tools/t01` hand tool: added close wd:Q1; dropped exact wd:Q1",
        "",
        "### Labels",
        "",
        "- `tools/t02`: screwdriver -> flat screwdriver",
        "",
    ]


def test_a_concept_id_that_vanished_fails_the_diff():
    new = scheme.load(NEW)
    del new["tools"].concepts["t03"]
    lines, ok = scheme.diff(scheme.load(OLD), new)
    assert not ok
    assert "- `tools/t03` old screwdriver: deprecate it with `replaced_by` instead of deleting it" in lines


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_just_diff_reads_the_vocabulary_at_a_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    shutil.copytree(OLD, tmp_path / "vocabulary")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "vocabulary")
    _git(tmp_path, "commit", "-q", "-m", "old")
    _git(tmp_path, "tag", "v1.0.0")
    shutil.rmtree(tmp_path / "vocabulary")
    shutil.copytree(NEW, tmp_path / "vocabulary")
    monkeypatch.chdir(tmp_path)
    assert pipeline.main(["diff", "v1.0.0"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("## Vocabulary changes since v1.0.0\n")
    assert "- `tools/t04` torque wrench\n" in out
    (tmp_path / "vocabulary" / "parts.yaml").unlink()
    assert pipeline.main(["diff", "v1.0.0"]) == 1
    assert "- `parts/p01` screw: deprecate it" in capsys.readouterr().out
    assert pipeline.main(["diff", "v9"]) == 2
    assert "v9" in capsys.readouterr().err
