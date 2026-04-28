# SPDX-License-Identifier: MIT
"""Throughput and rate calculations for Factorio recipe graphs.

Functions and dataclasses that convert a desired output rate into per-recipe
crafting rates, accounting for machine speed, recipe energy, and output
counts.  Also provides belt and inserter throughput lookup tables sourced
from ``entities.json``.

Core concepts
-------------
* **Crafts per second** – how many times a recipe completes each second in
  one machine: ``crafting_speed / recipe_energy``.
* **Output per second per machine** – crafts/s multiplied by the recipe's
  output amount for the target product.
* **Required machines** – ``ceil(desired_rate / output_per_machine_per_s)``
  gives the minimum number of parallel machines.
* **Ingredient demand** – for each ingredient, the *actual* crafts/s
  (``machine_count × crafts_per_s``) multiplied by the ingredient amount.

Typical usage::

    from factorio_recipe_graph.rates import (
        crafts_per_second,
        output_rate_per_machine,
        machines_required,
        ingredient_demand,
        load_belt_table,
        load_inserter_table,
    )
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pure rate helpers
# ---------------------------------------------------------------------------


def crafts_per_second(crafting_speed: float, recipe_energy: float) -> float:
    """Return how many recipe crafts one machine completes per second.

    Args:
        crafting_speed: Machine's crafting speed multiplier (e.g. 0.75).
        recipe_energy: Recipe's base crafting time in seconds at speed 1.0.

    Returns:
        Crafts per second (always positive).

    Raises:
        ValueError: If either argument is not positive.
    """
    if crafting_speed <= 0:
        raise ValueError(f"crafting_speed must be positive, got {crafting_speed}")
    if recipe_energy <= 0:
        raise ValueError(f"recipe_energy must be positive, got {recipe_energy}")
    return crafting_speed / recipe_energy


def output_rate_per_machine(
    crafting_speed: float,
    recipe_energy: float,
    output_amount: float,
) -> float:
    """Return items produced per second by a single machine.

    Args:
        crafting_speed: Machine's crafting speed multiplier.
        recipe_energy: Recipe's base crafting time in seconds at speed 1.0.
        output_amount: How many items are produced per craft.

    Returns:
        Items per second from one machine.

    Raises:
        ValueError: If any argument is not positive.
    """
    if output_amount <= 0:
        raise ValueError(f"output_amount must be positive, got {output_amount}")
    return crafts_per_second(crafting_speed, recipe_energy) * output_amount


def machines_required(
    desired_rate: float,
    crafting_speed: float,
    recipe_energy: float,
    output_amount: float,
) -> int:
    """Return the minimum number of parallel machines for *desired_rate*.

    The result is always ``≥ 1`` (you need at least one machine even for
    very low rates) and is rounded up via ``math.ceil``.

    Args:
        desired_rate: Target items per second.
        crafting_speed: Machine's crafting speed multiplier.
        recipe_energy: Recipe's base crafting time in seconds at speed 1.0.
        output_amount: How many items produced per craft.

    Returns:
        Integer count of machines (≥ 1).

    Raises:
        ValueError: If any argument is not positive.
    """
    if desired_rate <= 0:
        raise ValueError(f"desired_rate must be positive, got {desired_rate}")
    per_machine = output_rate_per_machine(crafting_speed, recipe_energy, output_amount)
    return max(1, math.ceil(desired_rate / per_machine))


def machines_required_exact(
    desired_rate: float,
    crafting_speed: float,
    recipe_energy: float,
    output_amount: float,
) -> float:
    """Return the fractional number of machines for *desired_rate*.

    Unlike :func:`machines_required` this does **not** round up, which is
    useful for computing exact ingredient demand without over-provisioning.

    Args:
        desired_rate: Target items per second.
        crafting_speed: Machine's crafting speed multiplier.
        recipe_energy: Recipe's base crafting time in seconds at speed 1.0.
        output_amount: How many items produced per craft.

    Returns:
        Fractional machine count (always > 0).

    Raises:
        ValueError: If any argument is not positive.
    """
    if desired_rate <= 0:
        raise ValueError(f"desired_rate must be positive, got {desired_rate}")
    per_machine = output_rate_per_machine(crafting_speed, recipe_energy, output_amount)
    return desired_rate / per_machine


def ingredient_demand(
    machine_count: int | float,
    crafting_speed: float,
    recipe_energy: float,
    ingredient_amount: float,
) -> float:
    """Return items per second consumed for one ingredient.

    The demand equals the *actual* crafts per second across all machines
    multiplied by the ingredient's per-craft consumption.

    Args:
        machine_count: Number of parallel machines (may be fractional).
        crafting_speed: Machine's crafting speed multiplier.
        recipe_energy: Recipe's base crafting time in seconds at speed 1.0.
        ingredient_amount: Quantity consumed per craft.

    Returns:
        Items per second of this ingredient.

    Raises:
        ValueError: If any argument is not positive.
    """
    if machine_count <= 0:
        raise ValueError(f"machine_count must be positive, got {machine_count}")
    if ingredient_amount <= 0:
        raise ValueError(f"ingredient_amount must be positive, got {ingredient_amount}")
    cps = crafts_per_second(crafting_speed, recipe_energy)
    return machine_count * cps * ingredient_amount


# ---------------------------------------------------------------------------
# High-level recipe rate calculation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IngredientRate:
    """The demand for a single ingredient at a given production target.

    Attributes:
        name: Ingredient item name.
        item_type: ``"item"`` or ``"fluid"``.
        amount_per_craft: Quantity consumed per recipe craft.
        rate: Items (or fluid units) per second consumed.
    """

    name: str
    item_type: str
    amount_per_craft: float
    rate: float


@dataclass(frozen=True, slots=True)
class RecipeRateResult:
    """Complete rate breakdown for a recipe at a desired output rate.

    Attributes:
        recipe_name: The recipe being analysed.
        desired_rate: Target output items per second.
        crafting_speed: Machine crafting speed used.
        recipe_energy: Recipe base crafting time.
        output_amount: Items produced per craft.
        crafts_per_second: Crafts per second per machine.
        output_per_machine: Items per second per machine.
        machines_required: Minimum integer machines needed.
        machines_exact: Fractional machines needed (no rounding).
        ingredient_rates: Per-ingredient demand breakdown.
    """

    recipe_name: str
    desired_rate: float
    crafting_speed: float
    recipe_energy: float
    output_amount: float
    crafts_per_second: float
    output_per_machine: float
    machines_required: int
    machines_exact: float
    ingredient_rates: tuple[IngredientRate, ...]


def compute_recipe_rates(
    recipe_name: str,
    desired_rate: float,
    crafting_speed: float,
    recipe_energy: float,
    output_amount: float,
    ingredients: list[dict[str, Any]],
) -> RecipeRateResult:
    """Compute a full rate breakdown for a single recipe.

    This is the primary high-level entry point for rate calculations.

    Args:
        recipe_name: Human-readable recipe identifier.
        desired_rate: Target items per second.
        crafting_speed: Machine crafting speed multiplier.
        recipe_energy: Base crafting time in seconds.
        output_amount: Items produced per craft.
        ingredients: Sequence of dicts with keys ``name``, ``amount``, ``type``.

    Returns:
        A :class:`RecipeRateResult` with all derived values.
    """
    cps = crafts_per_second(crafting_speed, recipe_energy)
    opm = output_rate_per_machine(crafting_speed, recipe_energy, output_amount)
    mc = machines_required(desired_rate, crafting_speed, recipe_energy, output_amount)
    me = machines_required_exact(desired_rate, crafting_speed, recipe_energy, output_amount)

    ing_rates: list[IngredientRate] = []
    for ing in ingredients:
        ing_name = str(ing["name"])
        ing_amount = float(ing["amount"])
        ing_type = str(ing["type"])
        rate = ingredient_demand(me, crafting_speed, recipe_energy, ing_amount)
        ing_rates.append(
            IngredientRate(
                name=ing_name,
                item_type=ing_type,
                amount_per_craft=ing_amount,
                rate=rate,
            )
        )

    return RecipeRateResult(
        recipe_name=recipe_name,
        desired_rate=desired_rate,
        crafting_speed=crafting_speed,
        recipe_energy=recipe_energy,
        output_amount=output_amount,
        crafts_per_second=cps,
        output_per_machine=opm,
        machines_required=mc,
        machines_exact=me,
        ingredient_rates=tuple(ing_rates),
    )


# ---------------------------------------------------------------------------
# Transport throughput tables
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BeltThroughput:
    """Throughput characteristics for a belt tier.

    Attributes:
        name: Internal entity name (e.g. ``"transport-belt"``).
        speed: Raw belt speed value from ``entities.json``.
        throughput: Items per second (one lane = throughput/2).
        underground_distance: Max underground belt distance in tiles.
    """

    name: str
    speed: float
    throughput: float
    underground_distance: int


@dataclass(frozen=True, slots=True)
class InserterThroughput:
    """Throughput characteristics for an inserter type.

    Attributes:
        name: Internal entity name (e.g. ``"fast-inserter"``).
        throughput: Items per second (base, no stack bonus research).
        reach: Tile reach distance.
        stack_bonus: Base stack bonus (0 for non-stack inserters).
    """

    name: str
    throughput: float
    reach: int
    stack_bonus: int


def _default_entities_path() -> Path:
    """Locate ``entities.json`` in the bundled data directory."""
    return Path(__file__).resolve().parent / "data" / "entities.json"


def _load_entities(path: Path | None = None) -> dict[str, Any]:
    """Load entities.json and return the raw dict."""
    resolved = path or _default_entities_path()
    if not resolved.exists():
        raise FileNotFoundError(f"entities.json not found at {resolved}")
    with resolved.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def load_belt_table(path: Path | None = None) -> dict[str, BeltThroughput]:
    """Load belt throughput data from ``entities.json``.

    Args:
        path: Optional explicit path to ``entities.json``.

    Returns:
        ``{belt_name: BeltThroughput}`` mapping.
    """
    data = _load_entities(path)
    belts_raw: dict[str, Any] = data.get("belts", {})
    result: dict[str, BeltThroughput] = {}
    for name, info in belts_raw.items():
        result[name] = BeltThroughput(
            name=name,
            speed=float(info["speed"]),
            throughput=float(info["throughput"]),
            underground_distance=int(info["underground_distance"]),
        )
    return result


def load_inserter_table(path: Path | None = None) -> dict[str, InserterThroughput]:
    """Load inserter throughput data from ``entities.json``.

    Args:
        path: Optional explicit path to ``entities.json``.

    Returns:
        ``{inserter_name: InserterThroughput}`` mapping.
    """
    data = _load_entities(path)
    inserters_raw: dict[str, Any] = data.get("inserters", {})
    result: dict[str, InserterThroughput] = {}
    for name, info in inserters_raw.items():
        result[name] = InserterThroughput(
            name=name,
            throughput=float(info["throughput"]),
            reach=int(info["reach"]),
            stack_bonus=int(info["stack_bonus"]),
        )
    return result


def belts_required(item_rate: float, belt_throughput: float) -> int:
    """Return number of belts needed to carry *item_rate* items/s.

    Args:
        item_rate: Items per second that must be transported.
        belt_throughput: Items per second capacity of one belt.

    Returns:
        Integer belt count (≥ 1).

    Raises:
        ValueError: If either argument is not positive.
    """
    if item_rate <= 0:
        raise ValueError(f"item_rate must be positive, got {item_rate}")
    if belt_throughput <= 0:
        raise ValueError(f"belt_throughput must be positive, got {belt_throughput}")
    return max(1, math.ceil(item_rate / belt_throughput))


def inserters_required(item_rate: float, inserter_throughput: float) -> int:
    """Return number of inserters needed to move *item_rate* items/s.

    Args:
        item_rate: Items per second that must be moved.
        inserter_throughput: Items per second capacity of one inserter.

    Returns:
        Integer inserter count (≥ 1).

    Raises:
        ValueError: If either argument is not positive.
    """
    if item_rate <= 0:
        raise ValueError(f"item_rate must be positive, got {item_rate}")
    if inserter_throughput <= 0:
        raise ValueError(f"inserter_throughput must be positive, got {inserter_throughput}")
    return max(1, math.ceil(item_rate / inserter_throughput))
