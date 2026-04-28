# SPDX-License-Identifier: MIT
"""Data schemas and validators for base_recipes.json entries.

Dataclass-based schemas for recipe and entity entries loaded from
``base_recipes.json``, plus validation utilities that produce clear,
actionable error messages.

The schemas mirror the JSON structure produced by ``scripts/build_base_recipes.py``
and provide:

* **Type-safe representations** – frozen dataclasses with precise field types.
* **Validation on construction** – ``__post_init__`` checks enforce invariants.
* **Bulk validation** – :func:`validate_base_recipes` validates an entire
  ``base_recipes.json`` mapping and collects all errors.
* **Loading helper** – :func:`load_and_validate_base_recipes` reads the JSON
  file, parses it into schema objects, and returns the validated mapping.

Typical usage::

    from factorio_recipe_graph.schemas import load_and_validate_base_recipes

    recipes = load_and_validate_base_recipes()
    ec = recipes["electronic-circuit"]
    print(ec.item, ec.energy, ec.ingredients)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Schema dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IngredientEntry:
    """A single ingredient in a recipe.

    Attributes:
        name: Internal Factorio item/fluid name (e.g. ``"iron-plate"``).
        amount: Quantity consumed per craft (must be > 0).
        type: ``"item"`` or ``"fluid"``.
    """

    name: str
    amount: float
    type: Literal["item", "fluid"]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("IngredientEntry.name must be a non-empty string")
        if self.amount <= 0:
            raise ValueError(
                f"IngredientEntry.amount must be positive, got {self.amount} for {self.name!r}"
            )
        if self.type not in ("item", "fluid"):
            raise ValueError(
                f"IngredientEntry.type must be 'item' or 'fluid', got {self.type!r} "
                f"for {self.name!r}"
            )


@dataclass(frozen=True, slots=True)
class ResultEntry:
    """A single result produced by a recipe.

    Attributes:
        name: Internal Factorio item/fluid name (e.g. ``"electronic-circuit"``).
        amount: Quantity produced per craft (must be > 0).
        type: ``"item"`` or ``"fluid"``.
    """

    name: str
    amount: float
    type: Literal["item", "fluid"]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ResultEntry.name must be a non-empty string")
        if self.amount <= 0:
            raise ValueError(
                f"ResultEntry.amount must be positive, got {self.amount} for {self.name!r}"
            )
        if self.type not in ("item", "fluid"):
            raise ValueError(
                f"ResultEntry.type must be 'item' or 'fluid', got {self.type!r} for {self.name!r}"
            )


@dataclass(frozen=True, slots=True)
class MachineEntry:
    """A machine that can execute a recipe.

    Attributes:
        name: Internal Factorio machine name (e.g. ``"assembling-machine-2"``).
        crafting_speed: Speed multiplier (must be > 0).
        module_slots: Number of module slots (must be ≥ 0).
        size: Tile footprint side length (must be > 0).
    """

    name: str
    crafting_speed: float
    module_slots: int
    size: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("MachineEntry.name must be a non-empty string")
        if self.crafting_speed <= 0:
            raise ValueError(
                f"MachineEntry.crafting_speed must be positive, got {self.crafting_speed} "
                f"for {self.name!r}"
            )
        if self.module_slots < 0:
            raise ValueError(
                f"MachineEntry.module_slots must be non-negative, got {self.module_slots} "
                f"for {self.name!r}"
            )
        if self.size <= 0:
            raise ValueError(
                f"MachineEntry.size must be positive, got {self.size} for {self.name!r}"
            )


@dataclass(frozen=True, slots=True)
class BaseRecipeEntry:
    """A fully normalized recipe entry from ``base_recipes.json``.

    This is the primary schema object: one per recipe in the dataset.

    Invariants:
        * ``item`` must be non-empty.
        * ``category`` must be non-empty.
        * ``energy`` must be positive.
        * At least one ingredient.
        * At least one result.
        * At least one allowed machine.

    Attributes:
        item: The primary output item name (used as the recipe key).
        category: Crafting category (e.g. ``"crafting"``, ``"smelting"``).
        energy: Base crafting time in seconds at speed 1.0.
        ingredients: Tuple of :class:`IngredientEntry` objects.
        results: Tuple of :class:`ResultEntry` objects.
        allowed_machines: Tuple of :class:`MachineEntry` objects.
        is_primitive: Whether this recipe's output is a primitive resource.
    """

    item: str
    category: str
    energy: float
    ingredients: tuple[IngredientEntry, ...]
    results: tuple[ResultEntry, ...]
    allowed_machines: tuple[MachineEntry, ...]
    is_primitive: bool

    def __post_init__(self) -> None:
        if not self.item:
            raise ValueError("BaseRecipeEntry.item must be a non-empty string")
        if not self.category:
            raise ValueError(
                f"BaseRecipeEntry.category must be a non-empty string for recipe {self.item!r}"
            )
        if self.energy <= 0:
            raise ValueError(
                f"BaseRecipeEntry.energy must be positive, got {self.energy} "
                f"for recipe {self.item!r}"
            )
        if not self.ingredients:
            raise ValueError(
                f"BaseRecipeEntry must have at least one ingredient for recipe {self.item!r}"
            )
        if not self.results:
            raise ValueError(
                f"BaseRecipeEntry must have at least one result for recipe {self.item!r}"
            )
        if not self.allowed_machines:
            raise ValueError(
                f"BaseRecipeEntry must have at least one allowed machine for recipe {self.item!r}"
            )
        if not isinstance(self.is_primitive, bool):
            raise ValueError(
                f"BaseRecipeEntry.is_primitive must be a bool, got "
                f"{type(self.is_primitive).__name__} for recipe {self.item!r}"
            )


# ---------------------------------------------------------------------------
# Parsing helpers – convert raw dicts → schema objects
# ---------------------------------------------------------------------------


class SchemaValidationError(Exception):
    """Raised when one or more entries fail schema validation.

    Attributes:
        errors: Mapping of ``{recipe_name: error_message}``.
    """

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = errors
        summary = "; ".join(f"{k}: {v}" for k, v in list(errors.items())[:5])
        count = len(errors)
        if count > 5:
            summary += f" ... and {count - 5} more"
        super().__init__(f"{count} validation error(s): {summary}")


def _parse_ingredient(raw: dict[str, Any]) -> IngredientEntry:
    """Parse a raw ingredient dict into an :class:`IngredientEntry`."""
    return IngredientEntry(
        name=str(raw["name"]),
        amount=float(raw["amount"]),
        type=raw["type"],
    )


def _parse_result(raw: dict[str, Any]) -> ResultEntry:
    """Parse a raw result dict into a :class:`ResultEntry`."""
    return ResultEntry(
        name=str(raw["name"]),
        amount=float(raw["amount"]),
        type=raw["type"],
    )


def _parse_machine(raw: dict[str, Any]) -> MachineEntry:
    """Parse a raw machine dict into a :class:`MachineEntry`."""
    return MachineEntry(
        name=str(raw["name"]),
        crafting_speed=float(raw["crafting_speed"]),
        module_slots=int(raw["module_slots"]),
        size=int(raw["size"]),
    )


def parse_base_recipe_entry(name: str, raw: dict[str, Any]) -> BaseRecipeEntry:
    """Parse a single raw JSON dict into a :class:`BaseRecipeEntry`.

    Args:
        name: The recipe key (used for error context).
        raw: The raw JSON dict for this recipe.

    Returns:
        A validated :class:`BaseRecipeEntry`.

    Raises:
        KeyError: If a required field is missing from *raw*.
        ValueError: If a field value violates its invariant.
    """
    return BaseRecipeEntry(
        item=str(raw["item"]),
        category=str(raw["category"]),
        energy=float(raw["energy"]),
        ingredients=tuple(_parse_ingredient(i) for i in raw["ingredients"]),
        results=tuple(_parse_result(r) for r in raw["results"]),
        allowed_machines=tuple(_parse_machine(m) for m in raw["allowed_machines"]),
        is_primitive=bool(raw["is_primitive"]),
    )


# ---------------------------------------------------------------------------
# Bulk validation
# ---------------------------------------------------------------------------


def validate_base_recipes(
    data: dict[str, Any],
) -> dict[str, BaseRecipeEntry]:
    """Validate an entire ``base_recipes.json`` mapping.

    Parses every entry and collects errors. If any entry fails, raises
    :class:`SchemaValidationError` with all accumulated errors.

    Args:
        data: The raw top-level dict loaded from ``base_recipes.json``.

    Returns:
        A ``{name: BaseRecipeEntry}`` mapping of validated entries.

    Raises:
        SchemaValidationError: If one or more entries fail validation.
    """
    validated: dict[str, BaseRecipeEntry] = {}
    errors: dict[str, str] = {}

    for name, raw in data.items():
        try:
            entry = parse_base_recipe_entry(name, raw)
            # Extra consistency check: the recipe key should match ``item``
            if entry.item != name:
                raise ValueError(f"Recipe key {name!r} does not match entry.item {entry.item!r}")
            validated[name] = entry
        except (KeyError, ValueError, TypeError) as exc:
            errors[name] = str(exc)

    if errors:
        raise SchemaValidationError(errors)

    return validated


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------


def _default_base_recipes_path() -> Path:
    """Locate ``base_recipes.json`` in the bundled data directory."""
    return Path(__file__).resolve().parent / "data" / "base_recipes.json"


def load_and_validate_base_recipes(
    path: Path | None = None,
) -> dict[str, BaseRecipeEntry]:
    """Load and validate ``base_recipes.json``.

    Args:
        path: Optional explicit path. Falls back to the bundled data file.

    Returns:
        A ``{name: BaseRecipeEntry}`` mapping of validated entries.

    Raises:
        FileNotFoundError: If the JSON file cannot be found.
        SchemaValidationError: If one or more entries fail validation.
    """
    resolved = path or _default_base_recipes_path()
    if not resolved.exists():
        raise FileNotFoundError(f"base_recipes.json not found at {resolved}")

    with resolved.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object, got {type(data).__name__}")

    return validate_base_recipes(data)
