# Worked Examples

Each section below is a complete, runnable snippet. They assume you've installed the package (see [Installation](installation.md)) and are working from the repo root.

## 1. Electronic circuit at 10 items/second

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import NodeKind

builder = GraphBuilder.from_base_recipes()
graph = builder.build("electronic-circuit", rate=10.0)

def print_tree(g, node_id, indent=0):
    node = g.nodes[node_id]
    prefix = "  " * indent
    if node.kind == NodeKind.RECIPE:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s "
              f"({node.machine_count}× {node.machine.name})")
    else:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s [raw]")
    for child_id in node.children:
        print_tree(g, child_id, indent + 1)

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

## 2. Switching to a faster assembler

`GraphConfig.assembler_name` picks the preferred machine. The builder falls back to a different machine when the preferred one can't handle a recipe's category — smelting, for example, always uses furnaces.

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import GraphConfig

config = GraphConfig(assembler_name="assembling-machine-3")
builder = GraphBuilder.from_base_recipes(config=config)

graph = builder.build("advanced-circuit", rate=5.0)
root = graph.nodes[graph.root_node_id]
print(f"{root.label}: {root.machine_count} × {root.machine.name}")
# advanced-circuit: 5 × assembling-machine-3
```

## 3. Raw resource totals for a science pack

Useful for sizing a mining setup.

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import NodeKind

builder = GraphBuilder.from_base_recipes()
graph = builder.build("automation-science-pack", rate=1.0)

totals = {}
for node in graph.nodes.values():
    if node.kind == NodeKind.PRIMITIVE_INPUT:
        totals[node.label] = totals.get(node.label, 0.0) + node.rate

for resource, rate in sorted(totals.items()):
    print(f"  {resource}: {rate:.2f}/s")
```

## 4. Belt sizing for a target throughput

Compares two belt tiers for the same demand.

```python
from factorio_recipe_graph.rates import belts_required, load_belt_table

belts = load_belt_table()

# 75 iron-plate/s on basic transport belts
n = belts_required(75.0, belts["transport-belt"].throughput)
print(f"transport-belt: {n} belts")  # 5

# Same demand on express belts
n = belts_required(75.0, belts["express-transport-belt"].throughput)
print(f"express-transport-belt: {n} belts")  # 2
```

## 5. Standalone rate math (no graph)

```python
from factorio_recipe_graph.rates import (
    crafts_per_second,
    machines_required,
    machines_required_exact,
    ingredient_demand,
)

# Iron gear: energy=0.5s, AM2 speed=0.75, output=1 per craft
cps = crafts_per_second(0.75, 0.5)              # 1.5 crafts/s/machine
mc  = machines_required(10.0, 0.75, 0.5, 1.0)   # 7 (ceiling)
me  = machines_required_exact(10.0, 0.75, 0.5, 1.0)  # 6.667 (exact)

# Iron-plate demand for those gears (2 plates per gear)
demand = ingredient_demand(me, 0.75, 0.5, ingredient_amount=2.0)
print(f"iron-plate demand: {demand:.2f}/s")  # 20.00/s
```

The exact (fractional) machine count is what feeds downstream demand math, so you don't end up over-provisioning.

## 6. Round-trip through JSON

Serialization is lossless: every node, edge, recipe, machine, and config field survives the round-trip exactly.

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.serializers import graph_to_json, graph_from_json

builder = GraphBuilder.from_base_recipes()
graph = builder.build("processing-unit", rate=2.0)

json_str = graph_to_json(graph, indent=2)
restored = graph_from_json(json_str)

assert restored.target_rate == graph.target_rate
assert set(restored.nodes) == set(graph.nodes)
assert len(restored.edges) == len(graph.edges)
```
