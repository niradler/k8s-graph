import tempfile
from pathlib import Path

import networkx as nx
import pytest

from k8s_graph.export import (
    aggregate_isolated_nodes,
    export_all,
    export_html,
    export_json,
    export_png,
    load_json,
)


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    graph = nx.DiGraph()

    graph.add_node(
        "Deployment:default:nginx",
        kind="Deployment",
        name="nginx",
        namespace="default",
    )

    graph.add_node(
        "Pod:default:nginx-abc",
        kind="Pod",
        name="nginx-abc",
        namespace="default",
    )

    graph.add_node(
        "Secret:default:secret1",
        kind="Secret",
        name="secret1",
        namespace="default",
    )

    graph.add_node(
        "Secret:default:secret2",
        kind="Secret",
        name="secret2",
        namespace="default",
    )

    graph.add_edge(
        "Deployment:default:nginx",
        "Pod:default:nginx-abc",
        relationship_type="owned",
        details="Deployment owns Pod",
    )

    return graph


def test_aggregate_isolated_nodes(sample_graph):
    """Test aggregating isolated nodes."""
    agg_graph, isolated_by_kind = aggregate_isolated_nodes(sample_graph)

    assert agg_graph.number_of_nodes() == 3

    assert "Deployment:default:nginx" in agg_graph.nodes
    assert "Pod:default:nginx-abc" in agg_graph.nodes

    assert "Secret:default:secret1" not in agg_graph.nodes
    assert "Secret:default:secret2" not in agg_graph.nodes

    assert "Secret" in isolated_by_kind
    assert len(isolated_by_kind["Secret"]) == 2

    has_hanging_secret = any("Hanging_Secret" in node_id for node_id in agg_graph.nodes)
    assert has_hanging_secret


def test_export_json(sample_graph):
    """Test JSON export and load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.json"

        result = export_json(sample_graph, filepath)
        assert result is True
        assert filepath.exists()

        loaded_graph = load_json(filepath)
        assert loaded_graph.number_of_nodes() == sample_graph.number_of_nodes()
        assert loaded_graph.number_of_edges() == sample_graph.number_of_edges()

        for node_id in sample_graph.nodes():
            assert node_id in loaded_graph.nodes()
            assert loaded_graph.nodes[node_id]["kind"] == sample_graph.nodes[node_id]["kind"]


def test_export_png(sample_graph):
    """Test PNG export."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.png"

        result = export_png(sample_graph, filepath, title="Test Graph")
        assert result is True
        assert filepath.exists()

        file_size = filepath.stat().st_size
        assert file_size > 0


def test_export_png_without_aggregation(sample_graph):
    """Test PNG export without aggregation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.png"

        result = export_png(sample_graph, filepath, aggregate=False)
        assert result is True
        assert filepath.exists()


def test_export_html(sample_graph):
    """Test HTML export."""
    pytest.importorskip("pyvis")

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.html"

        result = export_html(sample_graph, filepath, title="Test Graph")
        assert result is True
        assert filepath.exists()

        content = filepath.read_text()
        assert "Test Graph" in content or len(content) > 0


def test_export_html_without_pyvis(sample_graph, monkeypatch):
    """Test HTML export when pyvis is not available."""
    import k8s_graph.export as export_module

    monkeypatch.setattr(export_module, "_has_pyvis", False)

    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "test.html"
        result = export_html(sample_graph, filepath)
        assert result is False


def test_export_all(sample_graph):
    """Test exporting to all formats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        results = export_all(
            sample_graph, tmpdir, "test_graph", title="Test Graph", formats=["json", "png"]
        )

        assert "json" in results
        assert "png" in results
        assert results["json"] is True
        assert results["png"] is True

        assert (Path(tmpdir) / "test_graph.json").exists()
        assert (Path(tmpdir) / "test_graph.png").exists()


def test_export_all_default_formats(sample_graph):
    """Test export_all with default formats."""
    pytest.importorskip("pyvis")

    with tempfile.TemporaryDirectory() as tmpdir:
        results = export_all(sample_graph, tmpdir, "test_graph")

        assert "json" in results
        assert "png" in results
        assert "html" in results


def test_load_json_nonexistent_file():
    """Test loading from nonexistent file."""
    with pytest.raises(FileNotFoundError):
        load_json("nonexistent.json")
