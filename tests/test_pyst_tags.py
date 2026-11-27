"""Local staging must reject mismatched release assets before it contacts PyST."""

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from rdflib import Graph

SCRIPT = Path(__file__).parent / "pyst" / "stage_tags.py"


@pytest.mark.parametrize(
    ("graph_version", "mapping_version", "tag_digest", "message"),
    [
        ("0.1.0", "0.1.0", "0" * 64, "SHA-256 mismatch for tags.tsv"),
        ("0.1.0", "0.1.1", None, "SSSOM mapping_set_version disagrees"),
        ("0.1.1", "0.1.0", None, "vocabulary scheme version disagrees"),
    ],
)
def test_stage_rejects_mixed_release_assets(
    tmp_path: Path, graph_version: str, mapping_version: str, tag_digest: str | None, message: str
) -> None:
    graph = tmp_path / "graph.ttl"
    graph.write_text(
        f"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://w3id.org/r9lab/vocabulary/materials/> a skos:ConceptScheme ;
    owl:versionInfo "{graph_version}" .
""",
        encoding="utf-8",
    )
    tags = tmp_path / "tags.tsv"
    tags.write_text(
        f"""#mapping_set_version: {mapping_version}
#curie_map:
#  r9lab-tag: https://w3id.org/r9lab/vocabulary/tags/
subject_id\tsubject_label\tpredicate_id\tobject_id\tobject_label\tmapping_justification\treviewer_id
""",
        encoding="utf-8",
    )
    source_manifest = tmp_path / "release.json"
    source_manifest.write_text(
        json.dumps(
            {
                "version": "0.1.0",
                "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
                "tags_sha256": tag_digest or hashlib.sha256(tags.read_bytes()).hexdigest(),
                "tags_url": "https://example.org/releases/v0.1.0/r9lab-tags.sssom.tsv",
            }
        ),
        encoding="utf-8",
    )
    staged = tmp_path / "staged.json"
    result = subprocess.run(  # noqa: S603 -- fixed repository script and fixture paths
        [sys.executable, SCRIPT, "stage", graph, tags, source_manifest, staged, "--url", "http://127.0.0.1:1"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert message in result.stderr
    assert not staged.exists()


@pytest.mark.parametrize(
    "edits",
    [
        {"tags_sha256": "2" * 64},
        {"graph_sha256": "2" * 64},
        {"tags_url": "https://example.com/releases/v0.1.0/r9lab-tags.sssom.tsv"},
        {"version": "0.1.1", "tags_url": "https://example.org/releases/v0.1.1/r9lab-tags.sssom.tsv"},
        {"endpoint": "http://127.0.0.1:2"},
    ],
)
def test_activate_rejects_edited_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, edits: dict[str, str]
) -> None:
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    adapter = importlib.import_module("stage_tags")
    graph = Graph()
    monkeypatch.setattr(adapter, "read_back", lambda _base: graph)
    monkeypatch.setattr(adapter, "read_associations", lambda _base: (graph, [], []))
    endpoint = "http://127.0.0.1:1"
    metadata = {
        "version": "0.1.0",
        "tags_url": "https://example.org/releases/v0.1.0/r9lab-tags.sssom.tsv",
        "graph_sha256": "0" * 64,
        "tags_sha256": "1" * 64,
    }
    manifest = metadata | {
        "endpoint": endpoint,
        "correspondences": [],
        "association_count": 0,
        "snapshot_fingerprint": adapter.fingerprint(graph, graph, adapter.Release.parse(metadata), endpoint),
    }
    staged = tmp_path / "staged.json"
    active = tmp_path / "active.json"
    staged.write_text(json.dumps(manifest), encoding="utf-8")
    adapter.activate_snapshot(staged, active)
    original = active.read_bytes()
    staged.write_text(json.dumps(manifest | edits), encoding="utf-8")
    with pytest.raises(adapter.StageError, match="snapshot endpoint no longer matches"):
        adapter.activate_snapshot(staged, active)
    assert active.read_bytes() == original
