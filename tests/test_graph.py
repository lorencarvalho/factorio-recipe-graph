# SPDX-License-Identifier: MIT
"""Minimal tests for the GraphBuilder surface.

This file exercises the public surface of the GraphBuilder by constructing a
small graph for a couple of trivial recipes. The heavy-lifting is in test_rates
and tests of the model classes.
"""

from __future__ import annotations

from factorio_recipe_graph.graph import GraphBuilder


def test_build_basic_graph() -> None:
    builder = GraphBuilder.from_base_recipes()
    g = builder.build("electronic-circuit", rate=1.0)
    # Basic sanity checks on the produced graph structure
    assert isinstance(g, object)
    assert g.root_node_id is not None
    assert len(g.nodes) >= 1
    assert len(g.edges) >= 0
