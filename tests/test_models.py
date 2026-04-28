# SPDX-License-Identifier: MIT
"""Tests for domain models in factorio_recipe_graph.models"""

import pytest

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
)


def test_item_validation():
    # basic item
    i = Item(name="iron-ore")
    assert i.name == "iron-ore"
    assert i.item_type == ItemType.ITEM
    assert i.is_primitive is False

    # explicit fluid and primitive flag
    i2 = Item(name="water", item_type=ItemType.FLUID, is_primitive=True)
    assert i2.item_type == ItemType.FLUID
    assert i2.is_primitive

    # invalid: empty name should raise
    with pytest.raises(ValueError):
        Item(name="", item_type=ItemType.ITEM)


def test_ingredient_and_product_validation():
    base_item = Item(name="iron-ore")
    ing = Ingredient(item=base_item, amount=2.5)
    assert ing.item is base_item
    assert ing.amount == 2.5

    prod_item = Item(name="iron-plate")
    prod = Product(item=prod_item, amount=1)
    assert prod.item is prod_item
    assert prod.amount == 1

    with pytest.raises(ValueError):
        Ingredient(item=base_item, amount=0)
    with pytest.raises(ValueError):
        Product(item=prod_item, amount=0)


def test_recipe_validation():
    ing = (Ingredient(item=Item("iron-ore"), amount=1.0),)
    res = (Product(item=Item("iron-plate"), amount=1.0),)
    rec = Recipe(name="iron-plate", category="smelting", energy=3.0, ingredients=ing, results=res)
    assert rec.name == "iron-plate"
    assert rec.category == "smelting"
    assert rec.energy == 3.0
    assert len(rec.ingredients) == 1
    assert len(rec.results) == 1


def test_machine_and_capability():
    mach = Machine(
        name="assembling-machine-2",
        crafting_speed=0.75,
        size=3,
        module_slots=2,
        crafting_categories=("crafting", "electronics"),
    )

    rec = Recipe(
        name="dummy",
        category="crafting",
        energy=0.5,
        ingredients=(Ingredient(Item("iron-plate"), 1.0),),
        results=(Product(Item("iron-plate"), 1.0),),
    )

    assert mach.can_craft(rec)


def test_graph_node_and_graph_edge():
    rec = Recipe(
        name="dummy",
        category="crafting",
        energy=0.5,
        ingredients=(Ingredient(Item("ing"), 1.0),),
        results=(Product(Item("out"), 1.0),),
    )
    mach = Machine(
        name="assembling-machine-2",
        crafting_speed=0.75,
        size=3,
        module_slots=2,
        crafting_categories=("crafting",),
    )
    node = GraphNode(
        node_id="node-1",
        kind=NodeKind.RECIPE,
        label="dummy",
        rate=1.0,
        recipe=rec,
        machine=mach,
        machine_count=1,
        children=("child-1",),
    )
    edge = Edge(source_id=node.node_id, target_id="child-1", item=Item("ing"), rate=1.0)

    graph = RecipeGraph(
        target_item=Item("dummy"),
        target_rate=1.0,
        config=GraphConfig(),
        nodes={node.node_id: node},
        edges=(edge,),
        root_node_id=node.node_id,
    )

    # Access helpers
    assert graph.get_node(node.node_id) is node
    assert graph.children_of(node.node_id) == ()
    edges_from_list = graph.edges_from(node.node_id)
    assert edges_from_list == (edge,)
    edges_to_list = graph.edges_to(node.node_id)
    assert edges_to_list == ()
