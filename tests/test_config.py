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


def test_review_port_agrees_between_image_compose_and_server():
    expose = pins(r"(?m)^EXPOSE (\d+)$", "docker/review/Dockerfile")
    compose = pins(r'(?m)^\s+- "\$\{R9LAB_PUBLISH:-[\d.]+:(\d+)\}:\d+"$', "docker/review/compose.yaml")
    container = pins(r'(?m)^\s+- "\$\{R9LAB_PUBLISH:-[\d.]+:\d+\}:(\d+)"$', "docker/review/compose.yaml")
    default = pins(r'"--port", type=int, default=(\d+)', "src/r9lab_vocabulary/review/__main__.py")
    assert expose == compose == container == default


def test_review_image_python_agrees_with_python_version():
    image = pins(r"(?m)^FROM \S+-python([\d.]+)-", "docker/review/Dockerfile")
    assert image == {(ROOT / ".python-version").read_text().strip()}
