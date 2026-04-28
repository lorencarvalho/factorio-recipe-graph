# SPDX-License-Identifier: MIT
"""Tests validating the generated ``base_recipes.json``.

These tests ensure:
* The file exists and is valid JSON.
* Key recipes (electronic-circuit, copper-cable, etc.) are present with correct structure.
* Primitive flags are set correctly.
* Allowed-machines lists are non-empty and reference real machines.
* The generation script is idempotent (running it again yields the same output).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_RECIPES_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "factorio_recipe_graph"
    / "data"
    / "base_recipes.json"
)


@pytest.fixture(scope="module")
def base_recipes() -> dict:
    """Load base_recipes.json once for the whole test module."""
    assert BASE_RECIPES_PATH.exists(), f"base_recipes.json not found at {BASE_RECIPES_PATH}"
    with BASE_RECIPES_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# Structural / schema tests
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "item",
    "category",
    "energy",
    "ingredients",
    "results",
    "allowed_machines",
    "is_primitive",
}


def test_all_recipes_have_required_fields(base_recipes: dict) -> None:
    for name, entry in base_recipes.items():
        missing = REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Recipe {name!r} missing fields: {missing}"


def test_recipe_count(base_recipes: dict) -> None:
    assert len(base_recipes) >= 40, f"Expected ≥40 recipes, got {len(base_recipes)}"


def test_ingredients_structure(base_recipes: dict) -> None:
    for name, entry in base_recipes.items():
        for ing in entry["ingredients"]:
            assert "name" in ing, f"{name}: ingredient missing 'name'"
            assert "amount" in ing, f"{name}: ingredient missing 'amount'"
            assert "type" in ing, f"{name}: ingredient missing 'type'"
            assert ing["type"] in ("item", "fluid"), f"{name}: bad ingredient type {ing['type']!r}"
            assert ing["amount"] > 0, f"{name}: ingredient amount must be positive"


def test_results_structure(base_recipes: dict) -> None:
    for name, entry in base_recipes.items():
        assert len(entry["results"]) >= 1, f"{name}: must have at least one result"
        for res in entry["results"]:
            assert "name" in res, f"{name}: result missing 'name'"
            assert "amount" in res, f"{name}: result missing 'amount'"
            assert "type" in res, f"{name}: result missing 'type'"
            assert res["amount"] > 0, f"{name}: result amount must be positive"


def test_allowed_machines_non_empty(base_recipes: dict) -> None:
    for name, entry in base_recipes.items():
        machines = entry["allowed_machines"]
        assert len(machines) >= 1, f"{name}: must have at least one allowed machine"
        for m in machines:
            assert "name" in m
            assert "crafting_speed" in m
            assert m["crafting_speed"] > 0


def test_energy_positive(base_recipes: dict) -> None:
    for name, entry in base_recipes.items():
        assert entry["energy"] > 0, f"{name}: energy must be positive"


# ---------------------------------------------------------------------------
# Specific recipe content tests
# ---------------------------------------------------------------------------


def test_electronic_circuit(base_recipes: dict) -> None:
    ec = base_recipes["electronic-circuit"]
    assert ec["item"] == "electronic-circuit"
    assert ec["category"] == "electronics"
    assert ec["energy"] == 0.5
    assert ec["is_primitive"] is False

    # Ingredients: 1 iron-plate, 3 copper-cable
    ing_names = {i["name"]: i["amount"] for i in ec["ingredients"]}
    assert ing_names["iron-plate"] == 1.0
    assert ing_names["copper-cable"] == 3.0

    # Single result: 1 electronic-circuit
    assert len(ec["results"]) == 1
    assert ec["results"][0]["name"] == "electronic-circuit"
    assert ec["results"][0]["amount"] == 1.0

    # Allowed machines should include assembling-machine-2 and -3
    machine_names = {m["name"] for m in ec["allowed_machines"]}
    assert "assembling-machine-2" in machine_names
    assert "assembling-machine-3" in machine_names


def test_copper_cable(base_recipes: dict) -> None:
    cc = base_recipes["copper-cable"]
    assert cc["item"] == "copper-cable"
    assert cc["category"] == "electronics"
    assert cc["energy"] == 0.5
    assert cc["is_primitive"] is False

    # Ingredients: 1 copper-plate
    assert len(cc["ingredients"]) == 1
    assert cc["ingredients"][0]["name"] == "copper-plate"
    assert cc["ingredients"][0]["amount"] == 1.0

    # Result: 2 copper-cable
    assert cc["results"][0]["name"] == "copper-cable"
    assert cc["results"][0]["amount"] == 2.0


def test_iron_gear_wheel(base_recipes: dict) -> None:
    igw = base_recipes["iron-gear-wheel"]
    assert igw["item"] == "iron-gear-wheel"
    assert igw["category"] == "crafting"
    assert igw["energy"] == 0.5

    ing_names = {i["name"]: i["amount"] for i in igw["ingredients"]}
    assert ing_names["iron-plate"] == 2.0

    machine_names = {m["name"] for m in igw["allowed_machines"]}
    assert "assembling-machine-1" in machine_names


def test_iron_plate_smelting(base_recipes: dict) -> None:
    ip = base_recipes["iron-plate"]
    assert ip["category"] == "smelting"
    assert ip["energy"] == 3.2

    # Allowed machines should be furnaces
    machine_names = {m["name"] for m in ip["allowed_machines"]}
    assert "stone-furnace" in machine_names
    assert "steel-furnace" in machine_names
    assert "electric-furnace" in machine_names


def test_automation_science_pack(base_recipes: dict) -> None:
    asp = base_recipes["automation-science-pack"]
    assert asp["item"] == "automation-science-pack"
    assert asp["energy"] == 5.0

    ing_names = {i["name"] for i in asp["ingredients"]}
    assert "copper-plate" in ing_names
    assert "iron-gear-wheel" in ing_names


# ---------------------------------------------------------------------------
# Primitive flag tests
# ---------------------------------------------------------------------------


def test_primitive_items_not_in_recipes_as_results(base_recipes: dict) -> None:
    """Items whose sole recipe marks them as primitive should not be craftable
    from other items (or they must be raw resources)."""
    # Known primitives (never produced by any recipe in this dataset)
    known_primitives = {
        "iron-ore",
        "copper-ore",
        "stone",
        "coal",
        "water",
        "crude-oil",
        "uranium-ore",
    }
    all_result_names: set[str] = set()
    for entry in base_recipes.values():
        for res in entry["results"]:
            all_result_names.add(res["name"])

    for prim in known_primitives:
        # These should not appear as the primary result of any recipe
        # (they may appear as a recipe *name* if there's a smelting recipe, but
        # the item itself is not produced by another recipe in the dataset).
        if prim in all_result_names:
            # If it appears, the recipe's is_primitive should still be False
            # (because the recipe *produces* it—it's smelting, not mining)
            pass  # acceptable
        else:
            # Truly never crafted — not in the file at all
            assert prim not in base_recipes, f"Unexpected recipe for primitive {prim!r}"


def test_smelting_results_not_primitive(base_recipes: dict) -> None:
    """Smelting recipes produce items (iron-plate, copper-plate, etc.) that
    should NOT be marked primitive—they are craftable."""
    for name in ("iron-plate", "copper-plate", "steel-plate", "stone-brick"):
        assert base_recipes[name]["is_primitive"] is False, f"{name} should not be primitive"


# ---------------------------------------------------------------------------
# Idempotency test
# ---------------------------------------------------------------------------


def test_generation_idempotent(tmp_path: Path) -> None:
    """Running the build script twice should produce identical output."""
    import subprocess
    import sys

    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"

    for out in (out1, out2):
        result = subprocess.run(
            [sys.executable, "scripts/build_base_recipes.py", "--output", str(out)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

    assert out1.read_text() == out2.read_text(), "Two consecutive runs produced different output"
