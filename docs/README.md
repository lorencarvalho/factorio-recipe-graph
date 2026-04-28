# Factorio Recipe Graph — Documentation

A Python library for building hierarchical recipe dependency graphs for [Factorio](https://factorio.com). Give it a target item and a desired rate (items/second), and it walks the ingredient tree down to raw inputs, computing machine counts, throughput, and transport requirements at every step.

---

## Table of Contents

| Document | What it covers |
|---|---|
| [Overview](overview.md) | Architecture and data model |
| [Installation & Quick Start](installation.md) | Install the library and build your first graph |
| [Usage Guide](usage.md) | Building graphs, configuring machines, inspecting results |
| [Worked Examples](examples.md) | End-to-end examples: science packs, advanced circuits, rate math |
| [Data Pipeline](data_pipeline.md) | How `base_recipes.json` is generated and extended |
| [Development & Testing](development.md) | Linting, type-checking, testing, contributing |

---

## At a glance

```python
from factorio_recipe_graph.graph import GraphBuilder
from factorio_recipe_graph.models import GraphConfig

builder = GraphBuilder.from_base_recipes()
graph = builder.build("electronic-circuit", rate=10.0)

root = graph.nodes[graph.root_node_id]
print(f"{root.label}: {root.machine_count} × {root.machine.name}")
# electronic-circuit: 7 × assembling-machine-2
```

## License

MIT
