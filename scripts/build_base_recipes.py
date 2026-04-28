#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build ``base_recipes.json`` from raw Factorio data.

This script reads ``recipes.json`` and ``entities.json`` (via the
``factorio_recipe_graph.raw_data`` module) and produces a normalized
``base_recipes.json`` file containing:

* Per-recipe: name, category, energy, ingredients, results,
  allowed machines (with crafting speed & module slots), and a
  ``primitive`` flag indicating whether the *primary result* is a
  raw/undecomposable input.

Usage::

    uv run python scripts/build_base_recipes.py            # default output
    uv run python scripts/build_base_recipes.py --output /tmp/test.json

The script is **idempotent**: running it twice produces identical output
(JSON keys are sorted, floats are stable).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the project source is importable when running from repo root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from factorio_recipe_graph.raw_data import (  # noqa: E402
    Machine as RawMachine,
)
from factorio_recipe_graph.raw_data import (  # noqa: E402
    Recipe as RawRecipe,
)
from factorio_recipe_graph.raw_data import (  # noqa: E402
    load_entities,
    load_recipes,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT = _REPO_ROOT / "src" / "factorio_recipe_graph" / "data" / "base_recipes.json"

# Items that are *never* the result of any recipe are primitives.
# We compute this dynamically, but the following are always considered
# primitive regardless (e.g. raw resources that might appear as both
# ingredient *and* byproduct in edge cases).
ALWAYS_PRIMITIVE: frozenset[str] = frozenset(
    {
        "iron-ore",
        "copper-ore",
        "stone",
        "coal",
        "water",
        "crude-oil",
        "uranium-ore",
    }
)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _determine_primitives(recipes: dict[str, RawRecipe]) -> set[str]:
    """Return the set of item names that should be flagged ``primitive``.

    An item is primitive if it is referenced as an ingredient somewhere
    but is *never* produced as a result of any recipe, **or** it is in
    the ``ALWAYS_PRIMITIVE`` set.
    """
    all_ingredients: set[str] = set()
    all_results: set[str] = set()

    for recipe in recipes.values():
        for ing in recipe.ingredients:
            all_ingredients.add(ing.name)
        for res in recipe.results:
            all_results.add(res.name)

    never_crafted = all_ingredients - all_results
    return never_crafted | ALWAYS_PRIMITIVE


def _allowed_machines_for_category(
    category: str,
    machines: dict[str, RawMachine],
) -> list[dict[str, object]]:
    """Return a sorted list of machine descriptors that support *category*."""
    result: list[dict[str, object]] = []
    for machine in machines.values():
        if category in machine.crafting_categories:
            result.append(
                {
                    "name": machine.name,
                    "crafting_speed": machine.crafting_speed,
                    "module_slots": machine.module_slots,
                    "size": machine.size,
                }
            )
    # Deterministic ordering: by name
    result.sort(key=lambda m: str(m["name"]))
    return result


def build_base_recipes() -> dict[str, object]:
    """Build the normalized base-recipes dictionary.

    Returns a ``dict`` ready to be serialised as JSON.
    """
    raw_recipes = load_recipes()
    raw_entities = load_entities()
    machines = raw_entities.machines

    primitives = _determine_primitives(raw_recipes)

    out: dict[str, object] = {}

    for name in sorted(raw_recipes):
        recipe = raw_recipes[name]

        # Primary result is the first entry in results (Factorio convention).
        primary_result = recipe.results[0].name if recipe.results else name

        ingredients = [
            {
                "name": ing.name,
                "amount": ing.amount,
                "type": ing.type,
            }
            for ing in recipe.ingredients
        ]

        results = [
            {
                "name": res.name,
                "amount": res.amount,
                "type": res.type,
            }
            for res in recipe.results
        ]

        allowed_machines = _allowed_machines_for_category(recipe.category, machines)

        out[name] = {
            "item": primary_result,
            "category": recipe.category,
            "energy": recipe.energy,
            "ingredients": ingredients,
            "results": results,
            "allowed_machines": allowed_machines,
            "is_primitive": primary_result in primitives,
        }

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate base_recipes.json from raw Factorio data."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    base_recipes = build_base_recipes()

    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(base_recipes, indent=2, sort_keys=False, ensure_ascii=False)
    # Ensure trailing newline for POSIX friendliness.
    if not json_text.endswith("\n"):
        json_text += "\n"

    output_path.write_text(json_text, encoding="utf-8")

    print(f"Wrote {len(base_recipes)} recipes to {output_path}")


if __name__ == "__main__":
    main()
