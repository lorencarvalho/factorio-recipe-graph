# Installation & Quick Start

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (recommended), or any PEP 517 compatible installer

## Installation

```bash
# Clone the repository
git clone https://github.com/lorencarvalho/factorio-recipe-graph
cd factorio-recipe-graph

# Install with uv (recommended — handles venv + deps automatically)
uv sync --dev
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Verify the install

```bash
# Run the test suite
uv run pytest
```

## Your first graph

```python
from factorio_recipe_graph.graph import GraphBuilder

# Load recipe data and create the builder
builder = GraphBuilder.from_base_recipes()

# Build a dependency graph: 10 electronic circuits per second
graph = builder.build("electronic-circuit", rate=10.0)

# Inspect the root node
root = graph.nodes[graph.root_node_id]
print(f"Item:     {root.label}")
print(f"Rate:     {root.rate} items/s")
print(f"Machine:  {root.machine.name}")
print(f"Count:    {root.machine_count}")
```

Output:

```
Item:     electronic-circuit
Rate:     10.0 items/s
Machine:  assembling-machine-2
Count:    7
```

### Walk the full tree

```python
def print_tree(graph, node_id, indent=0):
    node = graph.nodes[node_id]
    prefix = "  " * indent
    if node.machine:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s "
              f"({node.machine_count}× {node.machine.name})")
    else:
        print(f"{prefix}{node.label}: {node.rate:.2f}/s [raw resource]")
    for child_id in node.children:
        print_tree(graph, child_id, indent + 1)

print_tree(graph, graph.root_node_id)
```

Output:

```
electronic-circuit: 10.00/s (7× assembling-machine-2)
  iron-plate: 10.00/s (16× electric-furnace)
    iron-ore: 10.00/s [raw resource]
  copper-cable: 30.00/s (10× assembling-machine-2)
    copper-plate: 15.00/s (24× electric-furnace)
      copper-ore: 15.00/s [raw resource]
```

### Export to JSON

```python
from factorio_recipe_graph.serializers import graph_to_json

json_str = graph_to_json(graph, indent=2)
print(json_str[:200], "...")

# Save to file
with open("electronic-circuit-graph.json", "w") as f:
    f.write(json_str)
```

That's a complete dependency graph with machine counts and throughput rates. For configuration options, see the [Usage Guide](usage.md), and for more involved scenarios see the [Examples](examples.md).
