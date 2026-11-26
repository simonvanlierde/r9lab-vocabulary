"""Pins that live in more than one file and that no hook compares."""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent


def pins(pattern: str, *paths: str) -> set[str]:
    """Every value `pattern` captures in the files, found or not."""
    found = {m for p in paths for m in re.findall(pattern, (ROOT / p).read_text(), re.MULTILINE)}
    assert found, f"{pattern!r} matches nothing in {paths}"
    return found


def test_sssom_pin_agrees_between_ci_and_just():
    assert len(pins(r"sssom==([\d.]+)", ".github/workflows/python.yml", "just/local.just")) == 1


def test_prek_pin_agrees_between_ci_and_readme():
    ci = pins(r"PREK_VERSION: ([\d.]+)", ".github/workflows/checks.yml", ".github/workflows/advisories.yml")
    assert ci == pins(r"prek==([\d.]+)", "README.md")


def test_uv_pin_agrees_across_workflows():
    paths = sorted((ROOT / ".github/workflows").glob("*.yml"))
    text = "".join(p.read_text() for p in paths)
    versions = re.findall(r'(?m)^\s+version: "(0\.\d+\.\d+)"', text)
    # One pin per setup-uv step, so a step added without one fails here.
    assert len(versions) == text.count("astral-sh/setup-uv@")
    assert len(set(versions)) == 1
