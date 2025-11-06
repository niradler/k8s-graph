
import networkx as nx
import pytest

from k8s_graph.persistence import (
    from_adjacency_dict,
    from_dict,
    from_edge_list,
    get_format_from_extension,
    load_graph,
    load_graph_auto,
    save_graph,
    save_graph_auto,
    to_adjacency_dict,
    to_dict,
    to_edge_list,
)


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    graph = nx.DiGraph()

    graph.add_node(
        "Pod:default:nginx",
        kind="Pod",
        name="nginx",
        namespace="default",
        phase="Running",
    )

    graph.add_node(
        "Service:default:web",
        kind="Service",
        name="web",
        namespace="default",
    )

    graph.add_edge(
        "Service:default:web",
        "Pod:default:nginx",
        relationship_type="label_selector",
        details="app=nginx",
    )

    return graph


def test_save_and_load_json(sample_graph, tmp_path):
    """Test save and load in JSON format."""
    filepath = tmp_path / "test.json"

    save_graph(sample_graph, str(filepath), format="json")
    assert filepath.exists()

    loaded = load_graph(str(filepath), format="json")
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()
    assert loaded.number_of_edges() == sample_graph.number_of_edges()
    assert loaded.has_node("Pod:default:nginx")
    assert loaded.nodes["Pod:default:nginx"]["kind"] == "Pod"


def test_save_and_load_graphml(sample_graph, tmp_path):
    """Test save and load in GraphML format."""
    filepath = tmp_path / "test.graphml"

    save_graph(sample_graph, str(filepath), format="graphml")
    assert filepath.exists()

    loaded = load_graph(str(filepath), format="graphml")
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()
    assert loaded.number_of_edges() == sample_graph.number_of_edges()


def test_save_and_load_gml(sample_graph, tmp_path):
    """Test save and load in GML format."""
    filepath = tmp_path / "test.gml"

    save_graph(sample_graph, str(filepath), format="gml")
    assert filepath.exists()

    loaded = load_graph(str(filepath), format="gml")
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()
    assert loaded.number_of_edges() == sample_graph.number_of_edges()


def test_to_dict_and_from_dict(sample_graph):
    """Test dict conversion."""
    data = to_dict(sample_graph)
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) == 2
    assert len(data["links"]) == 1

    loaded = from_dict(data)
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()
    assert loaded.number_of_edges() == sample_graph.number_of_edges()


def test_to_edge_list_and_from_edge_list(sample_graph):
    """Test edge list conversion."""
    edges = to_edge_list(sample_graph)
    assert len(edges) == 1
    assert edges[0][0] == "Service:default:web"
    assert edges[0][1] == "Pod:default:nginx"
    assert edges[0][2]["relationship_type"] == "label_selector"

    node_attrs = {
        "Service:default:web": {"kind": "Service", "name": "web", "namespace": "default"},
        "Pod:default:nginx": {"kind": "Pod", "name": "nginx", "namespace": "default"},
    }

    loaded = from_edge_list(edges, node_attrs)
    assert loaded.number_of_nodes() == 2
    assert loaded.number_of_edges() == 1
    assert loaded.nodes["Pod:default:nginx"]["kind"] == "Pod"


def test_to_adjacency_dict_and_from_adjacency_dict(sample_graph):
    """Test adjacency dict conversion."""
    adj_dict = to_adjacency_dict(sample_graph)
    assert "Service:default:web" in adj_dict
    assert "Pod:default:nginx" in adj_dict["Service:default:web"]

    loaded = from_adjacency_dict(adj_dict)
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()
    assert loaded.number_of_edges() == sample_graph.number_of_edges()


def test_get_format_from_extension():
    """Test format inference from extension."""
    assert get_format_from_extension("test.json") == "json"
    assert get_format_from_extension("test.graphml") == "graphml"
    assert get_format_from_extension("test.xml") == "graphml"
    assert get_format_from_extension("test.gml") == "gml"
    assert get_format_from_extension("test.edgelist") == "edgelist"

    with pytest.raises(ValueError):
        get_format_from_extension("test.unknown")


def test_save_and_load_auto(sample_graph, tmp_path):
    """Test auto format detection on save/load."""
    filepath = tmp_path / "test.json"

    save_graph_auto(sample_graph, str(filepath))
    assert filepath.exists()

    loaded = load_graph_auto(str(filepath))
    assert loaded.number_of_nodes() == sample_graph.number_of_nodes()


def test_load_nonexistent_file(tmp_path):
    """Test loading non-existent file."""
    filepath = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError):
        load_graph(str(filepath))


def test_invalid_format(sample_graph, tmp_path):
    """Test invalid format."""
    filepath = tmp_path / "test.json"

    with pytest.raises(ValueError):
        save_graph(sample_graph, str(filepath), format="invalid")

    save_graph(sample_graph, str(filepath), format="json")

    with pytest.raises(ValueError):
        load_graph(str(filepath), format="invalid")
