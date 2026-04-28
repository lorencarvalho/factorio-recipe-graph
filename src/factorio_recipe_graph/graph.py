# SPDX-License-Identifier: MIT
"""Graph builder core for Factorio recipe dependency graphs.

``GraphBuilder`` accepts a target item, desired rate, and configuration;
recursively resolves dependencies until primitive inputs are reached;
produces a :class:`~factorio_recipe_graph.models.RecipeGraph` with node
and edge structures; and memoizes shared subgraphs to avoid recomputation
(e.g. copper cable used by multiple consumers).

Typical usage::

    from factorio_recipe_graph.graph import GraphBuilder
    from factorio_recipe_graph.models import GraphConfig

    builder = GraphBuilder.from_base_recipes()
    graph = builder.build("electronic-circuit", rate=10.0)

Design notes
------------
* Each unique ``(item_name, rate)`` pair is memoized so that identical
  subgraphs are computed only once.  Different *rates* for the same item
  will produce distinct subgraphs (since machine counts differ).
* Items not found in ``base_recipes.json`` are treated as **primitive
  inputs** (raw resources / fluids that are not further decomposed).
* The builder selects the *first* allowed machine whose crafting categories
  include the recipe's category, preferring the machine named in
  :attr:`GraphConfig.assembler_name` when it qualifies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    _make_node_id,
)
from .rates import (
    ingredient_demand,
    machines_required,
    machines_required_exact,
)
from .schemas import (
    BaseRecipeEntry,
    load_and_validate_base_recipes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item_from_entry(name: str, item_type_str: str, recipe_db: dict[str, BaseRecipeEntry]) -> Item:
    """Create an :class:`Item`, marking it primitive if it has no recipe."""
    return Item(
        name=name,
        item_type=ItemType.FLUID if item_type_str == "fluid" else ItemType.ITEM,
        is_primitive=name not in recipe_db,
    )


def _select_machine(
    entry: BaseRecipeEntry,
    preferred_name: str,
) -> tuple[str, float]:
    """Pick a machine for *entry*, preferring *preferred_name*.

    Returns ``(machine_name, crafting_speed)``.
    """
    # Try the preferred machine first
    for m in entry.allowed_machines:
        if m.name == preferred_name:
            return m.name, m.crafting_speed
    # Fall back to the first allowed machine
    m = entry.allowed_machines[0]
    return m.name, m.crafting_speed


def _machine_model(entry: BaseRecipeEntry, machine_name: str) -> Machine:
    """Build a :class:`Machine` domain model from a :class:`BaseRecipeEntry`."""
    for m in entry.allowed_machines:
        if m.name == machine_name:
            return Machine(
                name=m.name,
                crafting_speed=m.crafting_speed,
                size=m.size,
                module_slots=m.module_slots,
                crafting_categories=(entry.category,),
            )
    # Should not happen if _select_machine was called first
    raise ValueError(f"Machine {machine_name!r} not in allowed_machines for {entry.item!r}")


def _recipe_model(entry: BaseRecipeEntry, recipe_db: dict[str, BaseRecipeEntry]) -> Recipe:
    """Build a :class:`Recipe` domain model from a :class:`BaseRecipeEntry`."""
    ingredients = tuple(
        Ingredient(
            item=_item_from_entry(ing.name, ing.type, recipe_db),
            amount=ing.amount,
        )
        for ing in entry.ingredients
    )
    results = tuple(
        Product(
            item=_item_from_entry(res.name, res.type, recipe_db),
            amount=res.amount,
        )
        for res in entry.results
    )
    return Recipe(
        name=entry.item,
        category=entry.category,
        energy=entry.energy,
        ingredients=ingredients,
        results=results,
    )


def _output_amount(entry: BaseRecipeEntry) -> float:
    """Return the output amount for the primary item of *entry*."""
    for res in entry.results:
        if res.name == entry.item:
            return res.amount
    # Fallback: first result
    return entry.results[0].amount


# ---------------------------------------------------------------------------
# Memoization key
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _MemoKey:
    """Cache key combining item name and quantised rate.

    Rates are rounded to 10 decimal places to avoid floating-point
    discrepancies while still distinguishing meaningfully different rates.
    """

    item_name: str
    rate_key: float

    @classmethod
    def from_rate(cls, item_name: str, rate: float) -> _MemoKey:
        return cls(item_name=item_name, rate_key=round(rate, 10))


# ---------------------------------------------------------------------------
# Subgraph result (internal)
# ---------------------------------------------------------------------------


@dataclass
class _SubgraphResult:
    """Intermediate result returned by recursive resolution."""

    root_node_id: str
    nodes: dict[str, GraphNode]
    edges: list[Edge]


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------


class GraphBuilder:
    """Build a hierarchical recipe dependency graph for a target item.

    The builder loads recipe data from ``base_recipes.json`` and
    recursively resolves ingredient dependencies until only primitive
    inputs remain.  Shared subgraphs are memoized so that identical
    ``(item, rate)`` pairs produce the same nodes.

    Parameters
    ----------
    recipe_db:
        Mapping of ``{item_name: BaseRecipeEntry}`` (validated).
    config:
        User-supplied build configuration.
    """

    def __init__(
        self,
        recipe_db: dict[str, BaseRecipeEntry],
        config: GraphConfig | None = None,
    ) -> None:
        self._recipe_db = recipe_db
        self._config = config or GraphConfig()
        # Memoization cache: _MemoKey -> _SubgraphResult
        self._cache: dict[_MemoKey, _SubgraphResult] = {}

    # -- factory -----------------------------------------------------------

    @classmethod
    def from_base_recipes(
        cls,
        path: Path | None = None,
        config: GraphConfig | None = None,
    ) -> GraphBuilder:
        """Create a builder by loading and validating ``base_recipes.json``.

        Parameters
        ----------
        path:
            Optional explicit path to ``base_recipes.json``.
        config:
            Build configuration.  Defaults to :class:`GraphConfig` defaults.
        """
        recipe_db = load_and_validate_base_recipes(path)
        return cls(recipe_db=recipe_db, config=config)

    # -- public API --------------------------------------------------------

    def build(
        self,
        target_item: str,
        rate: float | None = None,
        config: GraphConfig | None = None,
    ) -> RecipeGraph:
        """Build and return a :class:`RecipeGraph` for *target_item*.

        Parameters
        ----------
        target_item:
            The item to produce (must exist in ``base_recipes.json``).
        rate:
            Desired output rate in items/second.  Defaults to
            ``config.target_rate``.
        config:
            Override configuration for this build.  Defaults to the
            builder-level config.

        Returns
        -------
        RecipeGraph
            Immutable graph with nodes, edges, and a root node.

        Raises
        ------
        KeyError
            If *target_item* is not found in the recipe database.
        """
        cfg = config or self._config
        desired_rate = rate if rate is not None else cfg.target_rate

        if target_item not in self._recipe_db:
            raise KeyError(
                f"Item {target_item!r} not found in recipe database. "
                f"Available items: {', '.join(sorted(self._recipe_db)[:10])}..."
            )

        # Reset memoization cache for each top-level build
        self._cache.clear()

        sub = self._resolve(target_item, desired_rate, cfg)

        target_entry = self._recipe_db[target_item]
        target_item_model = _item_from_entry(
            target_item,
            next(
                (r.type for r in target_entry.results if r.name == target_item),
                "item",
            ),
            self._recipe_db,
        )

        return RecipeGraph(
            target_item=target_item_model,
            target_rate=desired_rate,
            config=cfg,
            nodes=sub.nodes,
            edges=tuple(sub.edges),
            root_node_id=sub.root_node_id,
        )

    # -- private recursive resolver ----------------------------------------

    def _resolve(
        self,
        item_name: str,
        desired_rate: float,
        config: GraphConfig,
    ) -> _SubgraphResult:
        """Recursively resolve *item_name* at *desired_rate*.

        Returns a :class:`_SubgraphResult` containing all nodes and edges
        for this item and its transitive dependencies.
        """
        memo_key = _MemoKey.from_rate(item_name, desired_rate)
        if memo_key in self._cache:
            return self._cache[memo_key]

        # -- Primitive input (no recipe) -----------------------------------
        if item_name not in self._recipe_db:
            node = GraphNode(
                node_id=_make_node_id(),
                kind=NodeKind.PRIMITIVE_INPUT,
                label=item_name,
                rate=desired_rate,
                recipe=None,
                machine=None,
                machine_count=0.0,
                children=(),
            )
            result = _SubgraphResult(
                root_node_id=node.node_id,
                nodes={node.node_id: node},
                edges=[],
            )
            self._cache[memo_key] = result
            return result

        # -- Recipe node ---------------------------------------------------
        entry = self._recipe_db[item_name]
        machine_name, crafting_speed = _select_machine(entry, config.assembler_name)
        recipe_energy = entry.energy
        output_amount = _output_amount(entry)

        mc = machines_required(desired_rate, crafting_speed, recipe_energy, output_amount)
        me = machines_required_exact(desired_rate, crafting_speed, recipe_energy, output_amount)

        recipe_model = _recipe_model(entry, self._recipe_db)
        machine_model = _machine_model(entry, machine_name)

        # We'll collect child node IDs, all nodes, and all edges
        child_ids: list[str] = []
        all_nodes: dict[str, GraphNode] = {}
        all_edges: list[Edge] = []

        # Recursively resolve each ingredient
        for ing in entry.ingredients:
            ing_rate = ingredient_demand(me, crafting_speed, recipe_energy, ing.amount)
            child_sub = self._resolve(ing.name, ing_rate, config)

            child_ids.append(child_sub.root_node_id)
            all_nodes.update(child_sub.nodes)
            all_edges.extend(child_sub.edges)

        # Create the node for this recipe step
        node_id = _make_node_id()
        node = GraphNode(
            node_id=node_id,
            kind=NodeKind.RECIPE,
            label=item_name,
            rate=desired_rate,
            recipe=recipe_model,
            machine=machine_model,
            machine_count=mc,
            children=tuple(child_ids),
        )
        all_nodes[node_id] = node

        # Create edges from each child to this node
        for ing, child_id in zip(entry.ingredients, child_ids, strict=True):
            ing_rate = ingredient_demand(me, crafting_speed, recipe_energy, ing.amount)
            ing_item = _item_from_entry(ing.name, ing.type, self._recipe_db)
            all_edges.append(
                Edge(
                    source_id=child_id,
                    target_id=node_id,
                    item=ing_item,
                    rate=ing_rate,
                )
            )

        result = _SubgraphResult(
            root_node_id=node_id,
            nodes=all_nodes,
            edges=all_edges,
        )
        self._cache[memo_key] = result
        return result
