# factorio-recipe-graph

A Python library that answers the question:

> *"If I want to produce **N** items per second of **X**, exactly how many
> machines, furnaces, and raw resources do I need — all the way down?"*

Given a target item and desired production rate, it resolves the full
ingredient tree to primitive (raw) inputs, annotating each step with
machine counts, throughput rates, and transport requirements.

```python
from factorio_recipe_graph.graph import GraphBuilder

builder = GraphBuilder.from_base_recipes()
graph = builder.build("electronic-circuit", rate=10.0)

root = graph.nodes[graph.root_node_id]
print(f"{root.label}: {root.machine_count} × {root.machine.name}")
# electronic-circuit: 7 × assembling-machine-2
```

## Installation

```bash
git clone https://github.com/lorencarvalho/factorio-recipe-graph
cd factorio-recipe-graph
uv sync --dev
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

## What you get

- **Recursive dependency resolution** down to raw resources (`iron-ore`,
  `copper-ore`, `crude-oil`, etc.) — no hand-rolled chains needed.
- **Exact rate math** for machine counts, ingredient demand, and belt /
  inserter throughput, with both ceiling (machines to build) and exact
  (fractional, for downstream demand) outputs.
- **Memoized subgraphs** so shared dependencies (e.g. copper cable
  feeding multiple recipes) are computed once per build.
- **Lossless JSON serialization** for downstream visualization tooling.
- **Curated dataset** covering 45+ vanilla Factorio recipes shipped under
  `src/factorio_recipe_graph/data/`.

See the [docs](docs/README.md) for the full API, worked examples, and the
data-pipeline regeneration workflow.

## Data pipeline

The bundled `base_recipes.json` is generated from raw `recipes.json` and
`entities.json` exports. To regenerate it:

```bash
uv run python scripts/build_base_recipes.py
```

The script is idempotent — running it multiple times produces byte-identical
output. See [docs/data_pipeline.md](docs/data_pipeline.md) for details.

## Development

```bash
uv run ruff check          # lint
uv run ruff format --check # formatting
uv run ty check            # types
uv run pytest              # tests
```

CI runs all four on every push and pull request.

## Limitations

- Vanilla base game only — no mods, no Space Age expansion mechanics.
- No modules, beacons, or productivity bonuses. Rate math assumes raw
  machine speed.
- No bot or train logistics. Transport calculations cover belts,
  inserters, pipes, and pumps only.
- No quality tiers.

## Contributing

`ruff check`, `ruff format --check`, `ty check`, and `pytest` must all
pass before merge.

## License

MIT — see [LICENSE](LICENSE).
