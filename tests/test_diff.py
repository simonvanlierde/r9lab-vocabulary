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


def test_the_diff_reports_an_undeprecation_and_a_deprecation_with_no_replacement():
    old = {"t": scheme.Scheme("t", {}, {"t01": {"label": "a", "deprecated": True}, "t02": {"label": "b"}})}
    new = {"t": scheme.Scheme("t", {}, {"t01": {"label": "a"}, "t02": {"label": "b", "deprecated": True}})}
    lines, ok = scheme.diff(old, new)
    assert ok
    assert "- `t/t02` b, with no `replaced_by`" in lines
    assert "- `t/t01` a: no longer deprecated" in lines


def _tagged(tmp_path: Path, yaml_text: str) -> None:
    (tmp_path / "vocabulary").mkdir()
    (tmp_path / "vocabulary" / "t.yaml").write_text(yaml_text)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "vocabulary")
    _git(tmp_path, "commit", "-q", "-m", "old")
    _git(tmp_path, "tag", "v1.0.0")


def test_just_diff_of_an_unloadable_ref_is_an_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _tagged(tmp_path, "scheme: {slug: t}\nconcepts:\n  t01: {label: a}\n  t01: {label: b}\n")
    (tmp_path / "vocabulary" / "t.yaml").write_text("scheme: {slug: t}\nconcepts: {}\n")
    monkeypatch.chdir(tmp_path)
    assert pipeline.main(["diff", "v1.0.0"]) == 2
    assert "error: cannot load vocabulary/ at v1.0.0: " in capsys.readouterr().err


def test_just_diff_reads_a_ref_that_looks_like_an_option_as_a_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    _tagged(tmp_path, "scheme: {slug: t}\nconcepts:\n  t01: {label: a}\n")
    monkeypatch.chdir(tmp_path)
    assert pipeline.diff(f"--output={tmp_path / 'out.tar'}") == 2
    assert "not a valid object name: --output=" in capsys.readouterr().err
    assert pipeline.main(["diff", "v1.0.0"]) == 0
    assert capsys.readouterr().out.endswith("No concept added, deprecated, removed, remapped or relabelled.\n")
