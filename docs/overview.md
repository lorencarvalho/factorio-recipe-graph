# Overview

The library answers one question:

> *"If I want to produce **N** items per second of **X**, how many machines, furnaces, and raw resources do I need, all the way down?"*

Given a target item, it walks the ingredient tree until every leaf is a raw resource (ore, coal, water, crude oil), and annotates each step with machine type and count, items/second throughput, raw resource totals, and belt/inserter counts at the chosen tier.

## Architecture

Six modules, each with a single concern:

```
factorio_recipe_graph/
├── models.py         # Immutable domain objects (Item, Recipe, Machine, GraphNode, Edge, …)
├── raw_data.py       # Load recipes.json & entities.json into structured Python objects
├── schemas.py        # Validated schemas for base_recipes.json
├── rates.py          # Pure math: crafts/s, machines required, ingredient demand, belt/inserter tables
├── graph.py          # GraphBuilder — recursive dependency resolver
├── serializers.py    # Serialize / deserialize RecipeGraph ↔ dict / JSON
└── data/
    ├── recipes.json        # Raw recipe definitions extracted from Factorio
    ├── entities.json       # Machine, belt, inserter, pipe, pole specs
    └── base_recipes.json   # Generated normalized recipe + machine metadata
```

### Data flow

```
recipes.json + entities.json
        │
        ▼
  build_base_recipes.py          (offline, one-time generation)
        │
        ▼
  base_recipes.json              (normalized, validated)
        │
        ▼
  GraphBuilder.from_base_recipes()
        │
        ▼
  builder.build("item", rate=N)  (recursive resolution)
        │
        ▼
  RecipeGraph                    (immutable graph of nodes + edges)
        │
        ▼
  graph_to_dict() / graph_to_json()  (export for visualization)
```

## Items and primitives

Every ingredient is an `Item`, either a solid item or a fluid. Items that are never produced by any recipe (`iron-ore`, `copper-ore`, `water`, `crude-oil`, and so on) are *primitives*. The graph builder stops recursing when it hits one.

## Recipes and machines

A `Recipe` turns ingredients into products. Each recipe has a category (`crafting`, `smelting`, `chemistry`, `electronics`, etc.) that determines which machines can run it. A `Machine` has a crafting speed multiplier; the actual crafting time is:

```
actual_time = recipe_energy / machine_crafting_speed
```

## The graph

A `RecipeGraph` is a directed acyclic graph:

- Recipe nodes represent a group of machines producing one item.
- Primitive input nodes are leaves (raw resources).
- Edges carry items at a computed rate (items/second).
- The root node is the target item.

## Rate math

| Quantity | Formula |
|---|---|
| Crafts per second (1 machine) | `crafting_speed / recipe_energy` |
| Output per second (1 machine) | `crafts/s × output_amount` |
| Machines required | `⌈desired_rate / output_per_machine⌉` |
| Ingredient demand | `machines_exact × crafts/s × ingredient_amount` |

Two machine counts are reported per recipe: an exact (fractional) count used for downstream demand math to avoid over-provisioning, and a ceiling count for how many machines you actually build.

## Properties worth knowing

- **Immutable.** Models are frozen dataclasses with tuple-typed collections, so graphs are safe to share across threads.
- **Validated on construction.** `__post_init__` enforces every invariant, so you get a clear error immediately rather than silent corruption later.
- **Memoized.** Within a single `build()`, subgraphs are cached by `(item, rate)` so shared dependencies (copper cable, iron gear wheel) are only computed once.
- Rate math in `rates.py` is pure. Data loading is separate from graph construction; serialization is independent of both.
- The data pipeline is idempotent — `build_base_recipes.py` produces byte-identical output for the same inputs, and a test fails if it doesn't.
