# SPDX-License-Identifier: MIT
"""Rate calculation tests for representative recipes (gears, electronic circuits)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from factorio_recipe_graph.rates import (
    compute_recipe_rates,
    ingredient_demand,
    load_belt_table,
    load_inserter_table,
    machines_required,
    machines_required_exact,
    output_rate_per_machine,
)

BASE_RECIPES_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "factorio_recipe_graph"
    / "data"
    / "base_recipes.json"
)


@pytest.fixture(scope="module")
def base_recipes() -> dict[str, Any]:
    assert BASE_RECIPES_PATH.exists(), f"base_recipes.json not found at {BASE_RECIPES_PATH}"
    with BASE_RECIPES_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict)
    return data


def _machine_speed(entry: dict[str, Any], machine_name: str) -> float:
    machines = entry["allowed_machines"]
    assert isinstance(machines, list)
    for m in machines:
        if m["name"] == machine_name:
            return float(m["crafting_speed"])
    raise KeyError(f"Machine {machine_name!r} not found in allowed_machines")


def _output_amount(entry: dict[str, Any]) -> float:
    # In our generated dataset the primary output is entry["item"].
    item = entry["item"]
    for res in entry["results"]:
        if res["name"] == item:
            return float(res["amount"])
    raise KeyError(f"No result matching primary item {item!r}")


def test_iron_gear_wheel_rates(base_recipes: dict[str, Any]) -> None:
    entry = base_recipes["iron-gear-wheel"]
    assert isinstance(entry, dict)

    desired_rate = 10.0  # gears / s
    machine = "assembling-machine-2"
    speed = _machine_speed(entry, machine)
    energy = float(entry["energy"])
    out_amt = _output_amount(entry)

    # sanity: per-machine throughput
    assert output_rate_per_machine(speed, energy, out_amt) == pytest.approx(1.5)

    # machines needed for 10 gears/s @ 1.5 gear/s per machine => ceil(6.666...) == 7
    assert machines_required(desired_rate, speed, energy, out_amt) == 7

    # exact machines should give exact crafts/s == desired output crafts/s
    exact_machines = machines_required_exact(desired_rate, speed, energy, out_amt)
    assert exact_machines == pytest.approx(desired_rate / 1.5)

    # recipe consumes 2 iron-plate per craft; 1 craft produces 1 gear
    # so iron-plate demand = 2 * 10 = 20 iron-plate / s
    assert ingredient_demand(exact_machines, speed, energy, ingredient_amount=2.0) == pytest.approx(
        20.0
    )

    # high-level helper should match too
    rr = compute_recipe_rates(
        recipe_name="iron-gear-wheel",
        desired_rate=desired_rate,
        crafting_speed=speed,
        recipe_energy=energy,
        output_amount=out_amt,
        ingredients=entry["ingredients"],
    )
    assert rr.machines_required == 7
    ing = {i.name: i.rate for i in rr.ingredient_rates}
    assert ing["iron-plate"] == pytest.approx(20.0)


def test_electronic_circuit_rates(base_recipes: dict[str, Any]) -> None:
    entry = base_recipes["electronic-circuit"]
    assert isinstance(entry, dict)

    desired_rate = 10.0  # circuits / s
    machine = "assembling-machine-2"
    speed = _machine_speed(entry, machine)
    energy = float(entry["energy"])
    out_amt = _output_amount(entry)

    assert machines_required(desired_rate, speed, energy, out_amt) == 7

    rr = compute_recipe_rates(
        recipe_name="electronic-circuit",
        desired_rate=desired_rate,
        crafting_speed=speed,
        recipe_energy=energy,
        output_amount=out_amt,
        ingredients=entry["ingredients"],
    )

    ing = {i.name: i.rate for i in rr.ingredient_rates}
    # 10 crafts/s => 10 iron-plate/s and 30 copper-cable/s
    assert ing["iron-plate"] == pytest.approx(10.0)
    assert ing["copper-cable"] == pytest.approx(30.0)


def test_transport_throughput_tables() -> None:
    belts = load_belt_table()
    inserters = load_inserter_table()

    assert belts["transport-belt"].throughput == pytest.approx(15.0)
    assert belts["fast-transport-belt"].throughput == pytest.approx(30.0)

    assert inserters["inserter"].throughput == pytest.approx(0.83)
    assert inserters["fast-inserter"].throughput == pytest.approx(2.31)
