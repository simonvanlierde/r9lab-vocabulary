"""Fixtures and constants the test modules share; `pythonpath` in pyproject.toml lets them import it."""

from __future__ import annotations

import contextlib
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from r9lab_vocabulary import checks, pipeline, scheme

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parent.parent
# A code set that holds every code, for a test that does not check codes.
EVERYTHING = type("All", (set,), {"__contains__": lambda *_: True})()
Schemes = dict[str, scheme.Scheme]
VERSIONS = {"bafu": {"2025-v2", "2026-v1"}}
# The metadata block a test SSSOM file starts with.
HEAD = "#curie_map:\n#  r9lab-tag: https://w3id.org/r9lab/vocabulary/tags/\n"


def tsv(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    """An SSSOM file: `HEAD`, then `columns` and one line per row, a missing field empty."""
    return HEAD + "\n".join(["\t".join(columns), *("\t".join(r.get(c, "") for c in columns) for r in rows)]) + "\n"


@pytest.fixture(scope="module")
def schemes() -> dict[str, scheme.Scheme]:
    """The real vocabulary, loaded once per module."""
    return scheme.load(ROOT / "vocabulary")


TEXT = {"definition": "d", "example": "e", "note": "n"}


def one(concepts: dict, meta: dict | None = None) -> dict[str, scheme.Scheme]:
    """One scheme `t` (or `meta`'s slug) holding `concepts`, with `meta` over a title, description and id letter.

    Each concept in use gets placeholder text, so a test checks only its own rule.
    """
    concepts = {
        cid: {**TEXT, **c} if isinstance(c, dict) and not c.get("deprecated") else c for cid, c in concepts.items()
    }
    meta = {"title": "t", "description": "d", "id_letter": "t", **(meta or {})}
    return {meta.get("slug", "t"): scheme.Scheme(meta.get("slug", "t"), meta, concepts)}


def _git(cwd: Path, *args: str, day: str = "2026-01-01", time: str = "12:00:00Z") -> None:
    stamp = f"{day}T{time}"
    env = {"GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp, "PATH": os.environ["PATH"]}
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false", *args],  # noqa: S607
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git() -> Callable[..., None]:
    """`git(cwd, *args, day=..., time=...)`: git in `cwd` as a throwaway committer at `time` (noon UTC) on `day`."""
    return _git


def built[T](load: Callable[[], T]) -> T:
    """`load()` of `just pipeline` output, in ROOT; skips while it is missing, fails if PIPELINE_OUTPUT_REQUIRED=1."""
    try:
        with contextlib.chdir(ROOT):
            return load()
    except FileNotFoundError as e:
        if os.environ.get("PIPELINE_OUTPUT_REQUIRED") == "1":
            pytest.fail(str(e))
        pytest.skip(str(e))


@pytest.fixture
def stub_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[..., None]:
    """`stub_sources(names=None, *, codes=EVERYTHING, concepts=None)`: fake the built sources `rdf` and `names` read.

    `names` maps each BAFU version to its names, and `codes` is every outside prefix's known
    codes. With `concepts` (the YAML under `concepts:`), the test runs in `tmp_path` on one
    scheme `t` holding them and an empty tags file; without, in ROOT on the real vocabulary.
    """

    def stub(
        names: dict[str, list[str]] | None = None, *, codes: set[str] = EVERYTHING, concepts: str | None = None
    ) -> None:
        monkeypatch.setattr(pipeline, "known_codes", lambda: dict.fromkeys(pipeline.SOURCE_CODES, codes))
        monkeypatch.setattr(pipeline, "name_lists", lambda: {"bafu": names or {}})
        if concepts is None:
            monkeypatch.chdir(ROOT)
            return
        (tmp_path / "vocabulary").mkdir()
        text = f"scheme: {{slug: t, title: t, description: d, id_letter: t}}\nconcepts:\n  {concepts}\n"
        (tmp_path / "vocabulary" / "t.yaml").write_text(text)
        (tmp_path / "mappings").mkdir()
        (tmp_path / "mappings" / "r9lab-tags.sssom.tsv").write_text("\t".join(checks.TAG_COLUMNS) + "\n")
        monkeypatch.chdir(tmp_path)

    return stub
