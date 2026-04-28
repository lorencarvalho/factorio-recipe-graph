# Factorio Recipe Graph

A Python library for building dependency graphs of Factorio recipes. Pick a target item and a rate; the builder works backwards through the ingredient tree until everything bottoms out at raw resources, and tells you how many machines you need at each step.

```python
from factorio_recipe_graph.graph import GraphBuilder

builder = GraphBuilder.from_base_recipes()
graph = builder.build("electronic-circuit", rate=10.0)

root = graph.nodes[graph.root_node_id]
print(f"{root.label}: {root.machine_count} × {root.machine.name}")
# electronic-circuit: 7 × assembling-machine-2
```

Where to go from here:

- [Installation and quick start](installation.md) to set up and build your first graph.
- [Usage guide](usage.md) for configuration, traversal, and transport math.
- [Worked examples](examples.md) for end-to-end recipes.
- [API reference](api.md) for the full public surface, generated from docstrings.
- [Data pipeline](data_pipeline.md) if you need to regenerate the bundled dataset.
