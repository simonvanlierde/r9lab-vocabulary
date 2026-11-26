"""What the build writes, pinned on a small fixture, and the real build through Turtle and JSON-LD.

After a deliberate change to the output, rewrite the expected file and read its diff:
`UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`.
"""

import os
from datetime import date
from typing import TYPE_CHECKING

import pytest
from conftest import ROOT
from rdflib import Graph
from rdflib.compare import graph_diff, to_isomorphic

from r9lab_vocabulary import export, pipeline, scheme

if TYPE_CHECKING:
    from pathlib import Path

GOLDEN = ROOT / "tests" / "fixtures" / "golden"
EXPECTED = GOLDEN / "expected.ttl"


def _same(a: Graph, b: Graph) -> None:
    a, b = to_isomorphic(a), to_isomorphic(b)
    if a != b:
        _, only_a, only_b = graph_diff(a, b)
        nt = {name: g.serialize(format="nt") for name, g in (("first", only_a), ("second", only_b))}
        pytest.fail("".join(f"only in the {name}:\n{triples}\n" for name, triples in nt.items()))


def test_the_build_matches_the_golden_turtle():
    orcids, landing = pipeline.citation(GOLDEN / "CITATION.cff")
    schemes = scheme.load(GOLDEN / "vocabulary")
    g = export.to_graph(schemes, export.About("1.0.0", orcids, landing, date(2026, 2, 1)))
    if os.environ.get("UPDATE_GOLDEN") == "1":
        g.serialize(EXPECTED, format="turtle")
    _same(g, Graph().parse(EXPECTED))


# rdflib's JSON-LD parser builds a ConjunctiveGraph internally whatever the caller passes.
@pytest.mark.filterwarnings("ignore:ConjunctiveGraph is deprecated:DeprecationWarning")
def test_the_real_build_round_trips_through_turtle_and_json_ld(tmp_path: Path):
    orcids, landing = pipeline.citation(ROOT / "CITATION.cff")
    about = export.About("test", orcids, landing, date(2026, 2, 1))
    schemes = scheme.load(ROOT / "vocabulary")
    export.write(schemes, about, tmp_path, [])
    ttl = Graph().parse(tmp_path / "r9lab-vocabulary.ttl")
    _same(ttl, export.to_graph(schemes, about))
    _same(Graph().parse(tmp_path / "r9lab-vocabulary.jsonld"), ttl)
