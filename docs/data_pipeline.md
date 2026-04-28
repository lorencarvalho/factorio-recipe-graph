# Data Pipeline

The library ships with a curated `base_recipes.json` derived from raw Factorio data. This page explains how that file is produced and how to regenerate it when the upstream data changes.

## Source files

Two raw JSON files live under `src/factorio_recipe_graph/data/`:

| File | Contents |
|---|---|
| `recipes.json` | Raw recipe definitions extracted from Factorio (name, category, energy, ingredients, results) |
| `entities.json` | Machine, belt, inserter, pipe, pump, and pole specs (crafting speeds, throughput, sizes, supported categories) |

Both files are committed to the repository. They came out of the game's prototype data, and updating them is a manual step whenever a new game version ships.

## Generated output

`base_recipes.json` is *derived* from the two raw files by `scripts/build_base_recipes.py`. Per recipe, it contains:

- `item` — primary result name
- `category` — crafting category (e.g. `crafting`, `smelting`, `chemistry`, `electronics`)
- `energy` — base crafting time in seconds at speed 1.0
- `ingredients` — list of `{name, amount, type}`
- `results` — list of `{name, amount, type}`
- `allowed_machines` — list of `{name, crafting_speed, module_slots, size}` matched by crafting category
- `is_primitive` — `true` when the primary result is a raw / undecomposable input (ore, water, crude oil, etc.)

## Regenerating

```bash
uv run python scripts/build_base_recipes.py
```

This rewrites `src/factorio_recipe_graph/data/base_recipes.json` in place. The script is idempotent — running it twice yields byte-identical output:

```bash
uv run python scripts/build_base_recipes.py --output /tmp/run1.json
uv run python scripts/build_base_recipes.py --output /tmp/run2.json
diff /tmp/run1.json /tmp/run2.json   # no differences
```

A test (`tests/test_base_recipes.py::test_generation_idempotent`) enforces that guarantee.

### Custom output path

```bash
uv run python scripts/build_base_recipes.py --output /path/to/output.json
```

## How primitives are determined

The script computes the set of items that are never produced as the result of any recipe, then unions that with an explicit `ALWAYS_PRIMITIVE` allowlist (`iron-ore`, `copper-ore`, `stone`, `coal`, `water`, `crude-oil`, `uranium-ore`). Any item in the resulting set has its recipe entry flagged `is_primitive: true`, which tells `GraphBuilder` to stop recursing at that node.

## Loading raw data directly

To work with the raw data instead of the normalized `base_recipes.json`, use `factorio_recipe_graph.raw_data`:

```python
from factorio_recipe_graph.raw_data import load_factorio_data

data = load_factorio_data()
print(len(data.recipes))
print(data.entities.machines["assembling-machine-2"].crafting_speed)
```
