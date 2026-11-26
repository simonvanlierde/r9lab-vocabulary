"""Fixtures the test modules share."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _git(cwd: Path, *args: str, day: str = "2026-01-01") -> None:
    stamp = f"{day}T12:00:00Z"
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
    """`git(cwd, *args, day=...)`: git in `cwd` as a throwaway committer, dated noon UTC on `day`, with no HOME."""
    return _git
