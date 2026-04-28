# SPDX-License-Identifier: MIT
"""Graph serialization utilities for the Factorio Recipe Graph library.

Functions for exporting :class:`~factorio_recipe_graph.models.RecipeGraph`
to plain dicts and JSON strings suitable for visualization, plus their
inverses for round-tripping ``graph → dict/JSON → graph``.

Serialized format
-----------------
The top-level dict has the shape::

    {
        "target_item": { "name": "…", "item_type": "item", "is_primitive": false },
        "target_rate": 10.0,
        "config": { "belt_name": "…", "inserter_name": "…", … },
        "root_node_id": "abc123",
        "nodes": {
            "<node_id>": {
                "node_id": "…",
                "kind": "recipe",
                "label": "…",
                "rate": 10.0,
                "machine_count": 3.0,
                "children": ["id1", "id2"],
                "recipe": { … } | null,
                "machine": { … } | null,
                "transport": { … } | null
            },
            …
        },
        "edges": [
            {
                "source_id": "…",
                "target_id": "…",
                "item": { "name": "…", "item_type": "item", "is_primitive": true },
                "rate": 5.0
            },
            …
        ]
    }

Typical usage::

    from factorio_recipe_graph.serializers import (
        graph_from_dict, graph_from_json,
        graph_to_dict, graph_to_json,
    )

    d = graph_to_dict(graph)
    json_str = graph_to_json(graph, indent=2)

    # Round-trip
    restored = graph_from_dict(d)
    restored = graph_from_json(json_str)
"""

from __future__ import annotations

import json
from typing import Any

from .models import (
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

# ---------------------------------------------------------------------------
# Serialize helpers
# ---------------------------------------------------------------------------


def _item_to_dict(item: Item) -> dict[str, Any]:
    """Serialize an :class:`Item` to a plain dict."""
    return {
        "name": item.name,
        "item_type": item.item_type.value,
        "is_primitive": item.is_primitive,
    }


def _ingredient_to_dict(ingredient: Ingredient) -> dict[str, Any]:
    """Serialize an :class:`Ingredient` to a plain dict."""
    return {
        "item": _item_to_dict(ingredient.item),
        "amount": ingredient.amount,
    }


def _product_to_dict(product: Product) -> dict[str, Any]:
    """Serialize a :class:`Product` to a plain dict."""
    return {
        "item": _item_to_dict(product.item),
        "amount": product.amount,
    }


def _recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    """Serialize a :class:`Recipe` to a plain dict."""
    return {
        "name": recipe.name,
        "category": recipe.category,
        "energy": recipe.energy,
        "ingredients": [_ingredient_to_dict(i) for i in recipe.ingredients],
        "results": [_product_to_dict(p) for p in recipe.results],
    }


def _machine_to_dict(machine: Machine) -> dict[str, Any]:
    """Serialize a :class:`Machine` to a plain dict."""
    return {
        "name": machine.name,
        "crafting_speed": machine.crafting_speed,
        "size": machine.size,
        "module_slots": machine.module_slots,
        "crafting_categories": list(machine.crafting_categories),
    }


def _transport_to_dict(transport: TransportComponent) -> dict[str, Any]:
    """Serialize a :class:`TransportComponent` to a plain dict."""
    return {
        "name": transport.name,
        "kind": transport.kind.value,
        "throughput": transport.throughput,
        "tier": transport.tier,
    }


def _config_to_dict(config: GraphConfig) -> dict[str, Any]:
    """Serialize a :class:`GraphConfig` to a plain dict."""
    return {
        "belt_name": config.belt_name,
        "inserter_name": config.inserter_name,
        "assembler_name": config.assembler_name,
        "target_rate": config.target_rate,
    }


def _node_to_dict(node: GraphNode) -> dict[str, Any]:
    """Serialize a :class:`GraphNode` to a plain dict."""
    return {
        "node_id": node.node_id,
        "kind": node.kind.value,
        "label": node.label,
        "rate": node.rate,
        "machine_count": node.machine_count,
        "children": list(node.children),
        "recipe": _recipe_to_dict(node.recipe) if node.recipe is not None else None,
        "machine": _machine_to_dict(node.machine) if node.machine is not None else None,
        "transport": (_transport_to_dict(node.transport) if node.transport is not None else None),
    }


def _edge_to_dict(edge: Edge) -> dict[str, Any]:
    """Serialize an :class:`Edge` to a plain dict."""
    return {
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "item": _item_to_dict(edge.item),
        "rate": edge.rate,
    }


# ---------------------------------------------------------------------------
# Deserialize helpers
# ---------------------------------------------------------------------------


def _item_from_dict(d: dict[str, Any]) -> Item:
    """Deserialize a dict into an :class:`Item`."""
    return Item(
        name=d["name"],
        item_type=ItemType(d["item_type"]),
        is_primitive=d["is_primitive"],
    )


def _ingredient_from_dict(d: dict[str, Any]) -> Ingredient:
    """Deserialize a dict into an :class:`Ingredient`."""
    return Ingredient(
        item=_item_from_dict(d["item"]),
        amount=d["amount"],
    )


def _product_from_dict(d: dict[str, Any]) -> Product:
    """Deserialize a dict into a :class:`Product`."""
    return Product(
        item=_item_from_dict(d["item"]),
        amount=d["amount"],
    )


def _recipe_from_dict(d: dict[str, Any]) -> Recipe:
    """Deserialize a dict into a :class:`Recipe`."""
    return Recipe(
        name=d["name"],
        category=d["category"],
        energy=d["energy"],
        ingredients=tuple(_ingredient_from_dict(i) for i in d["ingredients"]),
        results=tuple(_product_from_dict(p) for p in d["results"]),
    )


def _machine_from_dict(d: dict[str, Any]) -> Machine:
    """Deserialize a dict into a :class:`Machine`."""
    return Machine(
        name=d["name"],
        crafting_speed=d["crafting_speed"],
        size=d["size"],
        module_slots=d["module_slots"],
        crafting_categories=tuple(d["crafting_categories"]),
    )


def _transport_from_dict(d: dict[str, Any]) -> TransportComponent:
    """Deserialize a dict into a :class:`TransportComponent`."""
    return TransportComponent(
        name=d["name"],
        kind=TransportKind(d["kind"]),
        throughput=d["throughput"],
        tier=d["tier"],
    )


def _config_from_dict(d: dict[str, Any]) -> GraphConfig:
    """Deserialize a dict into a :class:`GraphConfig`."""
    return GraphConfig(
        belt_name=d["belt_name"],
        inserter_name=d["inserter_name"],
        assembler_name=d["assembler_name"],
        target_rate=d["target_rate"],
    )


def _node_from_dict(d: dict[str, Any]) -> GraphNode:
    """Deserialize a dict into a :class:`GraphNode`."""
    return GraphNode(
        node_id=d["node_id"],
        kind=NodeKind(d["kind"]),
        label=d["label"],
        rate=d["rate"],
        machine_count=d["machine_count"],
        children=tuple(d["children"]),
        recipe=_recipe_from_dict(d["recipe"]) if d["recipe"] is not None else None,
        machine=_machine_from_dict(d["machine"]) if d["machine"] is not None else None,
        transport=(_transport_from_dict(d["transport"]) if d["transport"] is not None else None),
    )


def _edge_from_dict(d: dict[str, Any]) -> Edge:
    """Deserialize a dict into an :class:`Edge`."""
    return Edge(
        source_id=d["source_id"],
        target_id=d["target_id"],
        item=_item_from_dict(d["item"]),
        rate=d["rate"],
    )


# ---------------------------------------------------------------------------
# Public API – graph ↔ dict
# ---------------------------------------------------------------------------


def graph_to_dict(graph: RecipeGraph) -> dict[str, Any]:
    """Serialize a :class:`RecipeGraph` to a plain dict.

    The returned dict is JSON-serializable (all values are primitives,
    lists, or nested dicts).

    Args:
        graph: The recipe graph to serialize.

    Returns:
        A dict suitable for ``json.dumps`` or visualization consumption.
    """
    return {
        "target_item": _item_to_dict(graph.target_item),
        "target_rate": graph.target_rate,
        "config": _config_to_dict(graph.config),
        "root_node_id": graph.root_node_id,
        "nodes": {node_id: _node_to_dict(node) for node_id, node in graph.nodes.items()},
        "edges": [_edge_to_dict(e) for e in graph.edges],
    }


def graph_from_dict(d: dict[str, Any]) -> RecipeGraph:
    """Deserialize a plain dict into a :class:`RecipeGraph`.

    This is the inverse of :func:`graph_to_dict`.

    Args:
        d: A dict previously produced by :func:`graph_to_dict`.

    Returns:
        A reconstructed :class:`RecipeGraph`.

    Raises:
        KeyError: If required keys are missing.
        ValueError: If model invariants are violated.
    """
    nodes = {node_id: _node_from_dict(node_dict) for node_id, node_dict in d["nodes"].items()}
    edges = tuple(_edge_from_dict(e) for e in d["edges"])
    return RecipeGraph(
        target_item=_item_from_dict(d["target_item"]),
        target_rate=d["target_rate"],
        config=_config_from_dict(d["config"]),
        nodes=nodes,
        edges=edges,
        root_node_id=d["root_node_id"],
    )


# ---------------------------------------------------------------------------
# Public API – graph ↔ JSON string
# ---------------------------------------------------------------------------


def graph_to_json(graph: RecipeGraph, *, indent: int | None = None) -> str:
    """Serialize a :class:`RecipeGraph` to a JSON string.

    Args:
        graph: The recipe graph to serialize.
        indent: JSON indentation level (``None`` for compact output).

    Returns:
        A JSON string representation of the graph.
    """
    return json.dumps(graph_to_dict(graph), indent=indent)


def graph_from_json(json_str: str) -> RecipeGraph:
    """Deserialize a JSON string into a :class:`RecipeGraph`.

    This is the inverse of :func:`graph_to_json`.

    Args:
        json_str: A JSON string previously produced by :func:`graph_to_json`.

    Returns:
        A reconstructed :class:`RecipeGraph`.

    Raises:
        json.JSONDecodeError: If the string is not valid JSON.
        KeyError: If required keys are missing.
        ValueError: If model invariants are violated.
    """
    return graph_from_dict(json.loads(json_str))
