# SPDX-License-Identifier: MIT
"""Sanity-check script for raw Factorio data loading.

Run with:
    uv run python examples/inspect_raw_data.py
"""

from __future__ import annotations

from factorio_recipe_graph.raw_data import (
    Entities,
    ItemStack,
    Recipe,
    load_entities,
    load_factorio_data,
    load_recipes,
)


def _fmt_item_list(items: tuple[ItemStack, ...]) -> str:
    """Format a tuple of ItemStack objects as a readable string."""
    parts: list[str] = []
    for item in items:
        suffix = f" ({item.type})" if item.type != "item" else ""
        parts.append(f"{item.amount:g}x {item.name}{suffix}")
    return ", ".join(parts) if parts else "(none)"


def _print_recipe(recipe: Recipe) -> None:
    print(f"\nRecipe: {recipe.name}")
    print(f"  Category:    {recipe.category}")
    print(f"  Energy:      {recipe.energy}s")
    print(f"  Ingredients: {_fmt_item_list(recipe.ingredients)}")
    print(f"  Results:     {_fmt_item_list(recipe.results)}")


def _print_entities_summary(entities: Entities) -> None:
    print(f"  machines:        {len(entities.machines)}")
    print(f"  belts:           {len(entities.belts)}")
    print(f"  inserters:       {len(entities.inserters)}")
    print(f"  poles:           {len(entities.poles)}")
    print(f"  pipes:           {len(entities.pipes)}")
    print(f"  pipes_to_ground: {len(entities.pipes_to_ground)}")
    print(f"  pumps:           {len(entities.pumps)}")


def main() -> None:
    # Load all data via the convenience loader
    data = load_factorio_data()
    recipes = data.recipes
    entities = data.entities

    # ------------------------------------------------------------------
    # Recipes summary
    # ------------------------------------------------------------------
    print(f"Loaded {len(recipes)} recipes.")

    categories: dict[str, int] = {}
    for recipe in recipes.values():
        categories[recipe.category] = categories.get(recipe.category, 0) + 1

    print("\nRecipe categories:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # ------------------------------------------------------------------
    # Sample recipes
    # ------------------------------------------------------------------
    sample_recipe_names = [
        "electronic-circuit",
        "copper-cable",
        "advanced-circuit",
        "automation-science-pack",
        "utility-science-pack",
    ]
    print("\n--- Sample Recipes ---")
    for name in sample_recipe_names:
        if name in recipes:
            _print_recipe(recipes[name])
        else:
            print(f"\nRecipe '{name}' not found.")

    # ------------------------------------------------------------------
    # Entities summary
    # ------------------------------------------------------------------
    print("\n--- Entities ---")
    _print_entities_summary(entities)

    # Detailed look at a specific machine
    am3_name = "assembling-machine-3"
    if am3_name in entities.machines:
        am3 = entities.machines[am3_name]
        print(f"\n--- {am3_name} ---")
        print(f"  Crafting Speed:      {am3.crafting_speed}")
        print(f"  Module Slots:        {am3.module_slots}")
        print(f"  Crafting Categories: {', '.join(am3.crafting_categories)}")
    else:
        print(f"\n{am3_name} not found in machines.")

    # Also verify the individual loaders work the same way
    recipes2 = load_recipes()
    entities2 = load_entities()
    assert len(recipes2) == len(recipes), "load_recipes() count mismatch"
    assert len(entities2.machines) == len(entities.machines), "load_entities() machines mismatch"
    print("\nOK: individual load_recipes() / load_entities() loaders verified.")


if __name__ == "__main__":
    main()
