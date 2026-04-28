# SPDX-License-Identifier: MIT
"""Raw Factorio data loading utilities.

Loads ``recipes.json`` and ``entities.json`` into structured Python objects
(frozen dataclasses).  By default the helpers read the bundled copies under
``src/factorio_recipe_graph/data/``; pass an explicit ``Path`` to load from
elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

JsonDict = dict[str, Any]

# ---------------------------------------------------------------------------
# Models (structured, immutable objects)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ItemStack:
    """An ingredient or result entry in a recipe."""

    name: str
    amount: float
    type: Literal["item", "fluid"] = "item"


@dataclass(frozen=True, slots=True)
class Recipe:
    """A Factorio recipe definition."""

    name: str
    category: str
    energy: float
    ingredients: tuple[ItemStack, ...]
    results: tuple[ItemStack, ...]


@dataclass(frozen=True, slots=True)
class FluidConnection:
    type: Literal["input", "output"]
    dx: int
    dy: int
    dir: int


@dataclass(frozen=True, slots=True)
class Machine:
    name: str
    crafting_speed: float
    size: int
    module_slots: int
    crafting_categories: tuple[str, ...]
    fluid_connections: tuple[FluidConnection, ...] = ()


@dataclass(frozen=True, slots=True)
class Belt:
    name: str
    speed: float
    throughput: float
    underground_distance: int


@dataclass(frozen=True, slots=True)
class Inserter:
    name: str
    throughput: float
    reach: int
    stack_bonus: int


@dataclass(frozen=True, slots=True)
class Pole:
    name: str
    supply_area: float
    wire_distance: float
    size: int


@dataclass(frozen=True, slots=True)
class Pipe:
    name: str
    size: int
    capacity: float


@dataclass(frozen=True, slots=True)
class PipeToGround:
    name: str
    size: int
    capacity: float
    underground_distance: int


@dataclass(frozen=True, slots=True)
class Pump:
    name: str
    size: int
    throughput: float


@dataclass(frozen=True, slots=True)
class Entities:
    """All entity groups loaded from ``entities.json``."""

    machines: dict[str, Machine]
    belts: dict[str, Belt]
    inserters: dict[str, Inserter]
    poles: dict[str, Pole]
    pipes: dict[str, Pipe]
    pipes_to_ground: dict[str, PipeToGround]
    pumps: dict[str, Pump]


@dataclass(frozen=True, slots=True)
class FactorioRawData:
    """Top-level container returned by :func:`load_factorio_data`."""

    recipes: dict[str, Recipe]
    entities: Entities


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def _package_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def _default_data_path(filename: str) -> Path:
    """Locate *filename* in the bundled ``data/`` dir."""
    pkg_path = _package_data_dir() / filename
    if not pkg_path.exists():
        raise FileNotFoundError(f"Bundled data file {filename!r} not found at {pkg_path}")
    return pkg_path


def _load_json(path: Path) -> JsonDict:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object in {path}, got {type(data).__name__}")
    return data


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_item_stack(raw: JsonDict) -> ItemStack:
    name = str(raw["name"])
    amount = float(raw["amount"])
    item_type = raw.get("type", "item")
    if item_type not in ("item", "fluid"):
        raise ValueError(f"Invalid item-stack type {item_type!r} for {name!r}")
    return ItemStack(name=name, amount=amount, type=item_type)


def _parse_recipe(name: str, raw: JsonDict) -> Recipe:
    return Recipe(
        name=name,
        category=str(raw.get("category", "crafting")),
        energy=float(raw.get("energy", 0.5)),
        ingredients=tuple(_parse_item_stack(x) for x in raw.get("ingredients", [])),
        results=tuple(_parse_item_stack(x) for x in raw.get("results", [])),
    )


def _parse_fluid_connections(
    raw_list: list[JsonDict] | None,
) -> tuple[FluidConnection, ...]:
    if not raw_list:
        return ()
    return tuple(
        FluidConnection(type=r["type"], dx=int(r["dx"]), dy=int(r["dy"]), dir=int(r["dir"]))
        for r in raw_list
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_recipes(path: Path | None = None) -> dict[str, Recipe]:
    """Load ``recipes.json`` into a ``{name: Recipe}`` mapping."""
    resolved = path or _default_data_path("recipes.json")
    raw = _load_json(resolved)
    return {name: _parse_recipe(name, entry) for name, entry in raw.items()}


def load_entities(path: Path | None = None) -> Entities:
    """Load ``entities.json`` into an :class:`Entities` container."""
    resolved = path or _default_data_path("entities.json")
    raw = _load_json(resolved)

    machines = {
        n: Machine(
            name=n,
            crafting_speed=float(e["crafting_speed"]),
            size=int(e["size"]),
            module_slots=int(e["module_slots"]),
            crafting_categories=tuple(e.get("crafting_categories", [])),
            fluid_connections=_parse_fluid_connections(e.get("fluid_connections")),
        )
        for n, e in raw.get("machines", {}).items()
    }

    belts = {
        n: Belt(
            name=n,
            speed=float(e["speed"]),
            throughput=float(e["throughput"]),
            underground_distance=int(e["underground_distance"]),
        )
        for n, e in raw.get("belts", {}).items()
    }

    inserters = {
        n: Inserter(
            name=n,
            throughput=float(e["throughput"]),
            reach=int(e["reach"]),
            stack_bonus=int(e["stack_bonus"]),
        )
        for n, e in raw.get("inserters", {}).items()
    }

    poles = {
        n: Pole(
            name=n,
            supply_area=float(e["supply_area"]),
            wire_distance=float(e["wire_distance"]),
            size=int(e["size"]),
        )
        for n, e in raw.get("poles", {}).items()
    }

    pipes = {
        n: Pipe(name=n, size=int(e["size"]), capacity=float(e["capacity"]))
        for n, e in raw.get("pipes", {}).items()
    }

    pipes_to_ground = {
        n: PipeToGround(
            name=n,
            size=int(e["size"]),
            capacity=float(e["capacity"]),
            underground_distance=int(e["underground_distance"]),
        )
        for n, e in raw.get("pipes_to_ground", {}).items()
    }

    pumps = {
        n: Pump(name=n, size=int(e["size"]), throughput=float(e["throughput"]))
        for n, e in raw.get("pumps", {}).items()
    }

    return Entities(
        machines=machines,
        belts=belts,
        inserters=inserters,
        poles=poles,
        pipes=pipes,
        pipes_to_ground=pipes_to_ground,
        pumps=pumps,
    )


def load_factorio_data(
    recipes_path: Path | None = None,
    entities_path: Path | None = None,
) -> FactorioRawData:
    """Convenience loader returning *all* raw Factorio data."""
    return FactorioRawData(
        recipes=load_recipes(recipes_path),
        entities=load_entities(entities_path),
    )
