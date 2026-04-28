# SPDX-License-Identifier: MIT
"""Domain models for the Factorio Recipe Graph library.

Immutable, typed dataclasses for ``Item``, ``Recipe``, ``Machine``,
``TransportComponent``, ``GraphNode``, ``Edge``, and related configuration
objects.

All models are **frozen** (immutable after creation) and use ``__slots__``
for memory efficiency.  Where possible, collections are stored as tuples
so the data structures remain hashable and safe to share across threads.

Design invariants
-----------------
* Every ``Recipe`` has at least one ingredient and at least one result.
* ``Machine.crafting_speed`` must be positive.
* ``TransportComponent.throughput`` must be positive.
* ``GraphNode`` ids are unique within a single graph.
* ``Edge`` always references valid source / target node ids.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, unique

# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


@unique
class ItemType(Enum):
    """Whether an item is a solid item or a fluid."""

    ITEM = "item"
    FLUID = "fluid"


@dataclass(frozen=True, slots=True)
class Item:
    """A Factorio item or fluid.

    Attributes:
        name: Internal Factorio name (e.g. ``"iron-plate"``).
        item_type: Whether this is a solid item or a fluid.
        is_primitive: ``True`` when the item is a raw/primitive input
            that should *not* be further decomposed (e.g. iron ore).
    """

    name: str
    item_type: ItemType = ItemType.ITEM
    is_primitive: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Item.name must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Ingredient:
    """A required input for a recipe.

    Attributes:
        item: The item being consumed.
        amount: Quantity consumed per craft (must be > 0).
    """

    item: Item
    amount: float

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(
                f"Ingredient amount must be positive, got {self.amount} for {self.item.name!r}"
            )


@dataclass(frozen=True, slots=True)
class Product:
    """A result produced by a recipe.

    Attributes:
        item: The item being produced.
        amount: Quantity produced per craft (must be > 0).
    """

    item: Item
    amount: float

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError(
                f"Product amount must be positive, got {self.amount} for {self.item.name!r}"
            )


# ---------------------------------------------------------------------------
# Recipes & Machines
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Recipe:
    """A Factorio crafting recipe.

    Invariants:
        * Must have at least one ingredient.
        * Must have at least one result.
        * ``energy`` (crafting time in seconds at speed 1.0) must be positive.

    Attributes:
        name: Internal recipe name (e.g. ``"electronic-circuit"``).
        category: Crafting category determining which machines can execute
            this recipe (e.g. ``"crafting"``, ``"smelting"``).
        energy: Base crafting time in seconds (at crafting speed 1.0).
        ingredients: Tuple of required :class:`Ingredient` entries.
        results: Tuple of :class:`Product` entries.
    """

    name: str
    category: str
    energy: float
    ingredients: tuple[Ingredient, ...]
    results: tuple[Product, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Recipe.name must be a non-empty string")
        if self.energy <= 0:
            raise ValueError(f"Recipe.energy must be positive, got {self.energy} for {self.name!r}")
        if not self.ingredients:
            raise ValueError(f"Recipe {self.name!r} must have at least one ingredient")
        if not self.results:
            raise ValueError(f"Recipe {self.name!r} must have at least one result")


@dataclass(frozen=True, slots=True)
class Machine:
    """A crafting machine (assembler, furnace, chemical plant, etc.).

    Invariants:
        * ``crafting_speed`` must be positive.
        * ``module_slots`` must be non-negative.
        * ``crafting_categories`` must not be empty.

    Attributes:
        name: Internal machine name (e.g. ``"assembling-machine-2"``).
        crafting_speed: Multiplier applied to recipe energy.
        size: Tile footprint side length (square machines).
        module_slots: Number of module slots available.
        crafting_categories: Tuple of recipe categories this machine supports.
    """

    name: str
    crafting_speed: float
    size: int
    module_slots: int
    crafting_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Machine.name must be a non-empty string")
        if self.crafting_speed <= 0:
            raise ValueError(f"Machine.crafting_speed must be positive, got {self.crafting_speed}")
        if self.module_slots < 0:
            raise ValueError(f"Machine.module_slots must be non-negative, got {self.module_slots}")
        if not self.crafting_categories:
            raise ValueError(f"Machine {self.name!r} must support at least one crafting category")

    def can_craft(self, recipe: Recipe) -> bool:
        """Return ``True`` if this machine supports *recipe*'s category."""
        return recipe.category in self.crafting_categories


# ---------------------------------------------------------------------------
# Transport components (belts, inserters, etc.)
# ---------------------------------------------------------------------------


@unique
class TransportKind(Enum):
    """Classification of logistics / transport components."""

    BELT = "belt"
    INSERTER = "inserter"
    PIPE = "pipe"
    PUMP = "pump"
    POLE = "pole"


@dataclass(frozen=True, slots=True)
class TransportComponent:
    """A logistics / transport entity with throughput characteristics.

    This is a unified model for belts, inserters, pipes, and other
    transport infrastructure.  Downstream code (rates, graph builder)
    uses :attr:`throughput` to decide how many units are needed.

    Invariants:
        * ``throughput`` must be positive.

    Attributes:
        name: Internal entity name (e.g. ``"fast-transport-belt"``).
        kind: :class:`TransportKind` classification.
        throughput: Maximum items (or fluid units) per second.
        tier: Optional human-readable tier label (e.g. ``1``, ``2``, ``3``).
    """

    name: str
    kind: TransportKind
    throughput: float
    tier: int = 1

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TransportComponent.name must be a non-empty string")
        if self.throughput <= 0:
            raise ValueError(
                f"TransportComponent.throughput must be positive, got {self.throughput}"
            )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphConfig:
    """User-supplied configuration for graph construction.

    Attributes:
        belt_name: Name of the belt tier to assume (e.g. ``"transport-belt"``).
        inserter_name: Name of the inserter to assume (e.g. ``"fast-inserter"``).
        assembler_name: Preferred assembler name (e.g. ``"assembling-machine-2"``).
            The graph builder may override this when the assembler cannot handle
            a recipe's category.
        target_rate: Desired output rate in **items per second**.
    """

    belt_name: str = "transport-belt"
    inserter_name: str = "fast-inserter"
    assembler_name: str = "assembling-machine-2"
    target_rate: float = 1.0

    def __post_init__(self) -> None:
        if self.target_rate <= 0:
            raise ValueError(f"GraphConfig.target_rate must be positive, got {self.target_rate}")


# ---------------------------------------------------------------------------
# Graph nodes & edges
# ---------------------------------------------------------------------------


def _make_node_id() -> str:
    """Generate a short, unique node identifier."""
    return uuid.uuid4().hex[:12]


@unique
class NodeKind(Enum):
    """Classification for graph nodes."""

    RECIPE = "recipe"
    """A recipe-processing step (one or more machines crafting the same recipe)."""

    PRIMITIVE_INPUT = "primitive_input"
    """A raw / primitive resource that is *not* further decomposed."""

    TRANSPORT = "transport"
    """A logistics component (belt segment, inserter, pipe, etc.)."""


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the recipe dependency graph.

    Invariants:
        * ``node_id`` is unique within a single graph.
        * ``machine_count`` (if set) must be ≥ 0.
        * ``rate`` must be non-negative.

    Attributes:
        node_id: Unique identifier within the graph.
        kind: Node classification.
        label: Human-readable label (e.g. item / recipe name).
        rate: Throughput at this node in items-per-second.
        recipe: The recipe being executed (only for ``RECIPE`` nodes).
        machine: The machine executing the recipe (only for ``RECIPE`` nodes).
        machine_count: Number of parallel machines required.
        transport: The transport component (only for ``TRANSPORT`` nodes).
        children: Tuple of child node IDs (dependency direction: child → this).
    """

    node_id: str = field(default_factory=_make_node_id)
    kind: NodeKind = NodeKind.RECIPE
    label: str = ""
    rate: float = 0.0
    recipe: Recipe | None = None
    machine: Machine | None = None
    machine_count: float = 0.0
    transport: TransportComponent | None = None
    children: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.rate < 0:
            raise ValueError(f"GraphNode.rate must be non-negative, got {self.rate}")
        if self.machine_count < 0:
            raise ValueError(
                f"GraphNode.machine_count must be non-negative, got {self.machine_count}"
            )


@dataclass(frozen=True, slots=True)
class Edge:
    """A directed edge in the recipe dependency graph.

    An edge represents a flow of items/fluids from a *source* node
    (producer) to a *target* node (consumer).

    Invariants:
        * ``source_id`` and ``target_id`` must be non-empty.
        * ``item`` must be a valid :class:`Item`.
        * ``rate`` must be non-negative.

    Attributes:
        source_id: ID of the producing :class:`GraphNode`.
        target_id: ID of the consuming :class:`GraphNode`.
        item: The item flowing along this edge.
        rate: Flow rate in items-per-second.
    """

    source_id: str
    target_id: str
    item: Item
    rate: float = 0.0

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("Edge.source_id must be a non-empty string")
        if not self.target_id:
            raise ValueError("Edge.target_id must be a non-empty string")
        if self.rate < 0:
            raise ValueError(f"Edge.rate must be non-negative, got {self.rate}")


@dataclass(frozen=True, slots=True)
class RecipeGraph:
    """An immutable recipe dependency graph.

    This is the top-level container produced by the graph builder.

    Attributes:
        target_item: The item the graph was built for.
        target_rate: Desired output rate in items-per-second.
        config: The :class:`GraphConfig` used during construction.
        nodes: Mapping of ``node_id → GraphNode``.
        edges: Tuple of all :class:`Edge` instances.
        root_node_id: The ID of the top-level output node.
    """

    target_item: Item
    target_rate: float
    config: GraphConfig
    nodes: dict[str, GraphNode]
    edges: tuple[Edge, ...]
    root_node_id: str

    def __post_init__(self) -> None:
        if self.root_node_id not in self.nodes:
            raise ValueError(f"root_node_id {self.root_node_id!r} not found in nodes")

    # -- convenience helpers ------------------------------------------------

    def get_node(self, node_id: str) -> GraphNode:
        """Look up a node by ID, raising ``KeyError`` if missing."""
        return self.nodes[node_id]

    def children_of(self, node_id: str) -> tuple[GraphNode, ...]:
        """Return the child :class:`GraphNode` instances of *node_id*."""
        parent = self.nodes[node_id]
        return tuple(self.nodes[cid] for cid in parent.children if cid in self.nodes)

    def edges_from(self, node_id: str) -> tuple[Edge, ...]:
        """Return all edges whose source is *node_id*."""
        return tuple(e for e in self.edges if e.source_id == node_id)

    def edges_to(self, node_id: str) -> tuple[Edge, ...]:
        """Return all edges whose target is *node_id*."""
        return tuple(e for e in self.edges if e.target_id == node_id)
