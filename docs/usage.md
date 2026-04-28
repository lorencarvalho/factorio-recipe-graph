# Usage Guide

This page walks through the full workflow: configuring the builder, constructing graphs, inspecting results, computing transport requirements, and exporting data.

---

## 1. Creating a GraphBuilder

`GraphBuilder` loads recipe data from `base_recipes.json` and exposes a `.build()` method.

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import GraphConfig

# Default configuration (assembling-machine-2, transport-belt, fast-inserter)
builder = GraphBuilder.from_base_recipes()

# Or provide a custom config at creation time
config = GraphConfig(
    assembler_name="assembling-machine-3",  # prefer AM3
    belt_name="fast-transport-belt",
    inserter_name="fast-inserter",
    target_rate=5.0,                        # default rate when not specified in build()
)
builder = GraphBuilder.from_base_recipes(config=config)
```

### GraphConfig options

| Parameter | Default | Description |
|---|---|---|
| `assembler_name` | `"assembling-machine-2"` | Preferred assembler. Falls back to the first compatible machine if this one can't craft the recipe. |
| `belt_name` | `"transport-belt"` | Belt tier for transport calculations. |
| `inserter_name` | `"fast-inserter"` | Inserter type for transport calculations. |
| `target_rate` | `1.0` | Default items/second when `rate` is omitted from `build()`. |

---

## 2. Building a graph

```python
# Build with explicit rate
graph = builder.build("electronic-circuit", rate=10.0)

# Build with the config's default target_rate
graph = builder.build("electronic-circuit")

# Override config for one build
custom_cfg = GraphConfig(assembler_name="assembling-machine-1", target_rate=2.0)
graph = builder.build("iron-gear-wheel", config=custom_cfg)
```

### Machine selection

The builder picks machines in this order:

1. If `GraphConfig.assembler_name` can craft the recipe's category, use it.
2. Otherwise, use the first machine in the recipe's `allowed_machines` list.

For example, `"electronic-circuit"` has category `"electronics"`, which `assembling-machine-1` does not support. So even if you request AM1, the builder falls back to AM2 or AM3.

Smelting recipes always use furnaces; chemistry recipes always use chemical plants. Your `assembler_name` setting doesn't apply there.

---

## 3. Inspecting the RecipeGraph

A `RecipeGraph` contains:

| Attribute | Type | Description |
|---|---|---|
| `target_item` | `Item` | The item the graph was built for |
| `target_rate` | `float` | Desired output in items/second |
| `config` | `GraphConfig` | Configuration used during build |
| `root_node_id` | `str` | ID of the top-level output node |
| `nodes` | `dict[str, GraphNode]` | All nodes keyed by ID |
| `edges` | `tuple[Edge, ...]` | All directed edges |

### Traversing nodes

```python
graph = builder.build("electronic-circuit", rate=10.0)

# Get the root node
root = graph.nodes[graph.root_node_id]
print(root.label)          # "electronic-circuit"
print(root.rate)           # 10.0
print(root.machine.name)   # "assembling-machine-2"
print(root.machine_count)  # 7

# Get child nodes (ingredients)
children = graph.children_of(graph.root_node_id)
for child in children:
    print(f"  {child.label}: {child.rate}/s")
```

### Node kinds

```python
from factorio_recipe_graph.models import NodeKind

for node in graph.nodes.values():
    if node.kind == NodeKind.RECIPE:
        print(f"RECIPE: {node.label} — {node.machine_count}× {node.machine.name}")
    elif node.kind == NodeKind.PRIMITIVE_INPUT:
        print(f"RAW:    {node.label} — {node.rate}/s needed")
```

### Inspecting edges

Edges represent item flows from a producer to a consumer:

```python
# All edges feeding into the root node
for edge in graph.edges_to(graph.root_node_id):
    print(f"  {edge.item.name}: {edge.rate:.2f}/s")

# All edges leaving a specific node
for edge in graph.edges_from(some_node_id):
    print(f"  → {edge.item.name}: {edge.rate:.2f}/s")
```

### Walking the full tree

```python
def print_tree(graph, node_id, indent=0):
    node = graph.nodes[node_id]
    prefix = "  " * indent
    if node.kind == NodeKind.RECIPE:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s "
              f"({node.machine_count}× {node.machine.name})")
    else:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s [raw]")
    for child_id in node.children:
        print_tree(graph, child_id, indent + 1)

print_tree(graph, graph.root_node_id)
```

Output:

```
electronic-circuit: 10.00/s (7× assembling-machine-2)
  iron-plate: 10.00/s (16× electric-furnace)
    iron-ore: 10.00/s [raw]
  copper-cable: 30.00/s (10× assembling-machine-2)
    copper-plate: 15.00/s (24× electric-furnace)
      copper-ore: 15.00/s [raw]
```

---

## 4. Collecting raw resource totals

```python
from factorio_recipe_graph.models import NodeKind

def raw_resource_totals(graph):
    """Sum all primitive input rates."""
    totals = {}
    for node in graph.nodes.values():
        if node.kind == NodeKind.PRIMITIVE_INPUT:
            totals[node.label] = totals.get(node.label, 0.0) + node.rate
    return totals

graph = builder.build("advanced-circuit", rate=5.0)
for resource, rate in sorted(raw_resource_totals(graph).items()):
    print(f"  {resource}: {rate:.2f}/s")
```

Output:

```
  coal: 5.00/s
  copper-ore: 25.00/s
  iron-ore: 10.00/s
  petroleum-gas: 100.00/s
```

---

## 5. Transport calculations

The `rates` module provides belt and inserter throughput tables plus helpers:

```python
from factorio_recipe_graph.rates import (
    load_belt_table,
    load_inserter_table,
    belts_required,
    inserters_required,
)

belts = load_belt_table()
inserters = load_inserter_table()

# How many transport belts for 20 iron plates/s?
n_belts = belts_required(20.0, belts["transport-belt"].throughput)
print(f"Transport belts needed: {n_belts}")  # 2

# How many fast inserters for 20 items/s?
n_ins = inserters_required(20.0, inserters["fast-inserter"].throughput)
print(f"Fast inserters needed: {n_ins}")  # 9
```

### Available belt tiers

| Belt | Throughput (items/s) | Underground distance |
|---|---|---|
| `transport-belt` | 15.0 | 5 tiles |
| `fast-transport-belt` | 30.0 | 7 tiles |
| `express-transport-belt` | 45.0 | 9 tiles |
| `turbo-transport-belt` | 60.0 | 11 tiles |

### Available inserters

| Inserter | Throughput (items/s) | Stack bonus |
|---|---|---|
| `inserter` | 0.83 | 0 |
| `long-handed-inserter` | 1.20 | 0 |
| `fast-inserter` | 2.31 | 0 |
| `bulk-inserter` | 2.31 | 0 |
| `stack-inserter` | 7.06 | 4 |

---

## 6. Standalone rate math

The rate functions work without building a full graph:

```python
from factorio_recipe_graph.rates import (
    crafts_per_second,
    output_rate_per_machine,
    machines_required,
    machines_required_exact,
    ingredient_demand,
    compute_recipe_rates,
)

# Iron gear wheel: energy=0.5s, AM2 speed=0.75, produces 1 per craft
cps = crafts_per_second(0.75, 0.5)          # 1.5 crafts/s
opm = output_rate_per_machine(0.75, 0.5, 1) # 1.5 items/s
mc  = machines_required(10.0, 0.75, 0.5, 1) # 7 machines
me  = machines_required_exact(10.0, 0.75, 0.5, 1)  # 6.667 machines

# Ingredient demand: iron-plate (2 per craft) across 6.667 exact machines
iron_demand = ingredient_demand(me, 0.75, 0.5, 2.0)  # 20.0/s
```

### Full recipe rate breakdown

```python
import json
from pathlib import Path

# Load a recipe entry
path = Path("src/factorio_recipe_graph/data/base_recipes.json")
recipes = json.loads(path.read_text())
entry = recipes["electronic-circuit"]

rr = compute_recipe_rates(
    recipe_name="electronic-circuit",
    desired_rate=10.0,
    crafting_speed=0.75,   # AM2
    recipe_energy=0.5,
    output_amount=1.0,
    ingredients=entry["ingredients"],
)

print(f"Machines (ceil):  {rr.machines_required}")     # 7
print(f"Machines (exact): {rr.machines_exact:.3f}")     # 6.667
print(f"Crafts/s/machine: {rr.crafts_per_second:.2f}") # 1.50
for ir in rr.ingredient_rates:
    print(f"  {ir.name}: {ir.rate:.2f}/s ({ir.amount_per_craft} per craft)")
```

Output:

```
Machines (ceil):  7
Machines (exact): 6.667
Crafts/s/machine: 1.50
  iron-plate: 10.00/s (1.0 per craft)
  copper-cable: 30.00/s (3.0 per craft)
```

---

## 7. Serialization

### Export to JSON

```python
from factorio_recipe_graph.serializers import graph_to_json, graph_to_dict

# Pretty-printed JSON string
json_str = graph_to_json(graph, indent=2)
with open("output.json", "w") as f:
    f.write(json_str)

# Or get a plain dict (for further processing, visualization, etc.)
d = graph_to_dict(graph)
print(d["root_node_id"])
print(len(d["nodes"]), "nodes")
print(len(d["edges"]), "edges")
```

### Restore from JSON

```python
from factorio_recipe_graph.serializers import graph_from_json, graph_from_dict

# From a JSON string
restored = graph_from_json(json_str)
assert restored.target_rate == graph.target_rate

# From a dict
restored = graph_from_dict(d)
```

Round-trips are lossless. Every node, edge, recipe, machine, and config field is preserved exactly.

---

## 8. Loading raw Factorio data

For exploration or custom analysis, load the raw data directly:

```python
from factorio_recipe_graph.raw_data import load_factorio_data

data = load_factorio_data()

# Explore recipes
ec = data.recipes["electronic-circuit"]
print(ec.category, ec.energy, ec.ingredients)

# Explore machines
am2 = data.entities.machines["assembling-machine-2"]
print(am2.crafting_speed, am2.crafting_categories)

# Explore belts, inserters, pipes, poles, pumps
for belt_name, belt in data.entities.belts.items():
    print(f"{belt_name}: {belt.throughput} items/s")
```

---
