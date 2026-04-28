# Development & Testing

## Tooling

The project is managed with [uv](https://docs.astral.sh/uv/). The commands below assume you've run `uv sync --dev` once to set up the environment.

| Command | Purpose |
|---|---|
| `uv run ruff check` | Lint check (pyflakes, pycodestyle, isort, pyupgrade, bugbear, comprehensions) |
| `uv run ruff format` | Auto-format the codebase |
| `uv run ruff format --check` | Verify formatting without rewriting |
| `uv run ty check` | Static type check |
| `uv run pytest` | Run the test suite |

CI runs `ruff check`, `ruff format --check`, `ty check`, and `pytest` on every push and pull request — see `.github/workflows/ci.yml`. All four have to pass before a PR can merge.

## Project layout

```
factorio-recipe-graph/
├── src/factorio_recipe_graph/   # Library package
│   ├── models.py                # Domain dataclasses
│   ├── raw_data.py              # Raw JSON loaders
│   ├── schemas.py               # Validated base_recipes.json schemas
│   ├── rates.py                 # Pure rate math + transport tables
│   ├── graph.py                 # GraphBuilder
│   ├── serializers.py           # JSON / dict round-trip
│   └── data/                    # Bundled JSON datasets
├── tests/                       # pytest suite
├── scripts/build_base_recipes.py  # Regenerate base_recipes.json
├── examples/                    # Standalone usage examples
└── docs/                        # mkdocs site
```

## Running the docs locally

```bash
uv run mkdocs serve
```

Then open <http://127.0.0.1:8000>.

## Adding a new recipe

The recipe set is driven by `src/factorio_recipe_graph/data/recipes.json` (and `entities.json` for any new machine). After editing those, regenerate the normalized dataset:

```bash
uv run python scripts/build_base_recipes.py
uv run pytest tests/test_base_recipes.py
```

The test file has assertions for several specific recipes — extend them when you add a new one that consumers will rely on.
