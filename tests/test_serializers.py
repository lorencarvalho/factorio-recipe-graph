# SPDX-License-Identifier: MIT
"""Round-trip and snapshot tests for ``factorio_recipe_graph.serializers``."""

from __future__ import annotations

import json

import pytest

from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import (
    Edge,
    GraphConfig,
    GraphNode,
    Ingredient,
    Item,
    ItemType,
    Machine,
    NodeKind,
    Product,
    Recipe,
    RecipeGraph,
    TransportComponent,
    TransportKind,
)
from factorio_recipe_graph.serializers import (
    graph_from_dict,
    graph_from_json,
    graph_to_dict,
    graph_to_json,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_graph() -> RecipeGraph:
    """Construct a minimal hand-crafted graph with known values."""
    iron_ore = Item(name="iron-ore", item_type=ItemType.ITEM, is_primitive=True)
    iron_plate = Item(name="iron-plate", item_type=ItemType.ITEM, is_primitive=False)

    recipe = Recipe(
        name="iron-plate",
        category="smelting",
        energy=3.2,
        ingredients=(Ingredient(item=iron_ore, amount=1.0),),
        results=(Product(item=iron_plate, amount=1.0),),
    )
    machine = Machine(
        name="stone-furnace",
        crafting_speed=1.0,
        size=2,
        module_slots=0,
        crafting_categories=("smelting",),
    )

    primitive_node = GraphNode(
        node_id="node_primitive",
        kind=NodeKind.PRIMITIVE_INPUT,
        label="iron-ore",
        rate=5.0,
    )
    recipe_node = GraphNode(
        node_id="node_recipe",
        kind=NodeKind.RECIPE,
        label="iron-plate",
        rate=5.0,
        recipe=recipe,
        machine=machine,
        machine_count=16.0,
        children=("node_primitive",),
    )
    edge = Edge(
        source_id="node_primitive",
        target_id="node_recipe",
        item=iron_ore,
        rate=5.0,
    )
    config = GraphConfig(
        belt_name="transport-belt",
        inserter_name="fast-inserter",
        assembler_name="assembling-machine-2",
        target_rate=5.0,
    )
    return RecipeGraph(
        target_item=iron_plate,
        target_rate=5.0,
        config=config,
        nodes={"node_primitive": primitive_node, "node_recipe": recipe_node},
        edges=(edge,),
        root_node_id="node_recipe",
    )


@pytest.fixture()
def electronic_circuit_graph() -> RecipeGraph:
    """Build a real graph for electronic-circuit from base_recipes.json."""
    builder = GraphBuilder.from_base_recipes()
    return builder.build("electronic-circuit", rate=10.0)


# ---------------------------------------------------------------------------
# graph_to_dict / graph_from_dict round-trip
# ---------------------------------------------------------------------------


class TestGraphToDict:
    """Tests for graph_to_dict output structure."""

    def test_top_level_keys(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        assert set(d.keys()) == {
            "target_item",
            "target_rate",
            "config",
            "root_node_id",
            "nodes",
            "edges",
        }

    def test_target_item_fields(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        ti = d["target_item"]
        assert ti["name"] == "iron-plate"
        assert ti["item_type"] == "item"
        assert ti["is_primitive"] is False

    def test_config_fields(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        cfg = d["config"]
        assert cfg["belt_name"] == "transport-belt"
        assert cfg["inserter_name"] == "fast-inserter"
        assert cfg["assembler_name"] == "assembling-machine-2"
        assert cfg["target_rate"] == 5.0

    def test_node_count(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        assert len(d["nodes"]) == 2

    def test_recipe_node_fields(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        node = d["nodes"]["node_recipe"]
        assert node["node_id"] == "node_recipe"
        assert node["kind"] == "recipe"
        assert node["label"] == "iron-plate"
        assert node["rate"] == 5.0
        assert node["machine_count"] == 16.0
        assert node["children"] == ["node_primitive"]
        assert node["recipe"] is not None
        assert node["recipe"]["name"] == "iron-plate"
        assert node["machine"] is not None
        assert node["machine"]["name"] == "stone-furnace"
        assert node["transport"] is None

    def test_primitive_node_fields(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        node = d["nodes"]["node_primitive"]
        assert node["kind"] == "primitive_input"
        assert node["recipe"] is None
        assert node["machine"] is None

    def test_edge_fields(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        assert len(d["edges"]) == 1
        e = d["edges"][0]
        assert e["source_id"] == "node_primitive"
        assert e["target_id"] == "node_recipe"
        assert e["item"]["name"] == "iron-ore"
        assert e["item"]["is_primitive"] is True
        assert e["rate"] == 5.0

    def test_json_serializable(self, simple_graph: RecipeGraph) -> None:
        """The dict must be directly serializable with json.dumps."""
        d = graph_to_dict(simple_graph)
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
        assert len(json_str) > 10


class TestRoundTripDict:
    """Round-trip: graph → dict → graph preserves all data."""

    def test_simple_graph_round_trip(self, simple_graph: RecipeGraph) -> None:
        d = graph_to_dict(simple_graph)
        restored = graph_from_dict(d)

        assert restored.target_item == simple_graph.target_item
        assert restored.target_rate == simple_graph.target_rate
        assert restored.config == simple_graph.config
        assert restored.root_node_id == simple_graph.root_node_id
        assert set(restored.nodes.keys()) == set(simple_graph.nodes.keys())
        assert len(restored.edges) == len(simple_graph.edges)

        # Verify each node
        for nid, orig_node in simple_graph.nodes.items():
            rest_node = restored.nodes[nid]
            assert rest_node.node_id == orig_node.node_id
            assert rest_node.kind == orig_node.kind
            assert rest_node.label == orig_node.label
            assert rest_node.rate == orig_node.rate
            assert rest_node.machine_count == orig_node.machine_count
            assert rest_node.children == orig_node.children
            assert rest_node.recipe == orig_node.recipe
            assert rest_node.machine == orig_node.machine
            assert rest_node.transport == orig_node.transport

        # Verify each edge
        for orig_edge, rest_edge in zip(simple_graph.edges, restored.edges, strict=True):
            assert rest_edge.source_id == orig_edge.source_id
            assert rest_edge.target_id == orig_edge.target_id
            assert rest_edge.item == orig_edge.item
            assert rest_edge.rate == orig_edge.rate

    def test_electronic_circuit_round_trip(self, electronic_circuit_graph: RecipeGraph) -> None:
        """Round-trip a real graph built from base_recipes.json."""
        d = graph_to_dict(electronic_circuit_graph)
        restored = graph_from_dict(d)

        assert restored.target_item == electronic_circuit_graph.target_item
        assert restored.target_rate == electronic_circuit_graph.target_rate
        assert restored.config == electronic_circuit_graph.config
        assert restored.root_node_id == electronic_circuit_graph.root_node_id
        assert set(restored.nodes.keys()) == set(electronic_circuit_graph.nodes.keys())
        assert len(restored.edges) == len(electronic_circuit_graph.edges)

        # Spot-check root node
        orig_root = electronic_circuit_graph.nodes[electronic_circuit_graph.root_node_id]
        rest_root = restored.nodes[restored.root_node_id]
        assert rest_root.label == orig_root.label
        assert rest_root.rate == orig_root.rate
        assert rest_root.recipe == orig_root.recipe
        assert rest_root.machine == orig_root.machine


# ---------------------------------------------------------------------------
# graph_to_json / graph_from_json round-trip
# ---------------------------------------------------------------------------


class TestRoundTripJson:
    """Round-trip: graph → JSON string → graph preserves all data."""

    def test_simple_graph_json_round_trip(self, simple_graph: RecipeGraph) -> None:
        json_str = graph_to_json(simple_graph, indent=2)
        assert isinstance(json_str, str)

        restored = graph_from_json(json_str)
        assert restored.target_item == simple_graph.target_item
        assert restored.target_rate == simple_graph.target_rate
        assert restored.root_node_id == simple_graph.root_node_id
        assert set(restored.nodes.keys()) == set(simple_graph.nodes.keys())
        assert len(restored.edges) == len(simple_graph.edges)

    def test_compact_json(self, simple_graph: RecipeGraph) -> None:
        compact = graph_to_json(simple_graph)
        pretty = graph_to_json(simple_graph, indent=2)
        # Compact should be shorter (no whitespace)
        assert len(compact) < len(pretty)

    def test_electronic_circuit_json_round_trip(
        self, electronic_circuit_graph: RecipeGraph
    ) -> None:
        json_str = graph_to_json(electronic_circuit_graph)
        restored = graph_from_json(json_str)

        assert restored.target_rate == electronic_circuit_graph.target_rate
        assert set(restored.nodes.keys()) == set(electronic_circuit_graph.nodes.keys())


# ---------------------------------------------------------------------------
# Snapshot-style tests – verify expected structure for known recipes
# ---------------------------------------------------------------------------


class TestSnapshotElectronicCircuit:
    """Verify key properties of a serialized electronic-circuit graph."""

    def test_root_node_label(self, electronic_circuit_graph: RecipeGraph) -> None:
        d = graph_to_dict(electronic_circuit_graph)
        root = d["nodes"][d["root_node_id"]]
        assert root["label"] == "electronic-circuit"
        assert root["kind"] == "recipe"

    def test_has_primitive_nodes(self, electronic_circuit_graph: RecipeGraph) -> None:
        d = graph_to_dict(electronic_circuit_graph)
        primitive_nodes = [n for n in d["nodes"].values() if n["kind"] == "primitive_input"]
        assert len(primitive_nodes) >= 1
        primitive_labels = {n["label"] for n in primitive_nodes}
        # Electronic circuit depends on iron-ore and copper-ore
        assert len(primitive_labels) > 0

    def test_edges_reference_valid_nodes(self, electronic_circuit_graph: RecipeGraph) -> None:
        d = graph_to_dict(electronic_circuit_graph)
        node_ids = set(d["nodes"].keys())
        for edge in d["edges"]:
            assert edge["source_id"] in node_ids, f"Edge source {edge['source_id']} not in nodes"
            assert edge["target_id"] in node_ids, f"Edge target {edge['target_id']} not in nodes"

    def test_all_rates_non_negative(self, electronic_circuit_graph: RecipeGraph) -> None:
        d = graph_to_dict(electronic_circuit_graph)
        for nid, node in d["nodes"].items():
            assert node["rate"] >= 0, f"Node {nid} has negative rate"
            assert node["machine_count"] >= 0, f"Node {nid} has negative machine_count"
        for edge in d["edges"]:
            assert edge["rate"] >= 0, (
                f"Edge {edge['source_id']}→{edge['target_id']} has negative rate"
            )

    def test_recipe_nodes_have_recipe_and_machine(
        self, electronic_circuit_graph: RecipeGraph
    ) -> None:
        d = graph_to_dict(electronic_circuit_graph)
        for node in d["nodes"].values():
            if node["kind"] == "recipe":
                assert node["recipe"] is not None
                assert node["machine"] is not None


# ---------------------------------------------------------------------------
# Transport node serialization
# ---------------------------------------------------------------------------


class TestTransportNodeSerialization:
    """Verify transport nodes serialize/deserialize correctly."""

    def test_transport_node_round_trip(self) -> None:
        belt = TransportComponent(
            name="fast-transport-belt",
            kind=TransportKind.BELT,
            throughput=30.0,
            tier=2,
        )
        iron_plate = Item(name="iron-plate", item_type=ItemType.ITEM)
        node = GraphNode(
            node_id="transport_node",
            kind=NodeKind.TRANSPORT,
            label="belt: iron-plate",
            rate=15.0,
            transport=belt,
        )
        config = GraphConfig(target_rate=15.0)
        graph = RecipeGraph(
            target_item=iron_plate,
            target_rate=15.0,
            config=config,
            nodes={"transport_node": node},
            edges=(),
            root_node_id="transport_node",
        )

        d = graph_to_dict(graph)
        tn = d["nodes"]["transport_node"]
        assert tn["transport"] is not None
        assert tn["transport"]["name"] == "fast-transport-belt"
        assert tn["transport"]["kind"] == "belt"
        assert tn["transport"]["throughput"] == 30.0
        assert tn["transport"]["tier"] == 2

        restored = graph_from_dict(d)
        rn = restored.nodes["transport_node"]
        assert rn.transport is not None
        assert rn.transport == belt
