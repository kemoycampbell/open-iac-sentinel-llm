## Quick orientation

This repository provides a small utility around reading and validating YAML configuration used to control an LLM-driven infrastructure drift detection tool. The core is a single `Config` class that loads a YAML config and validates it against a simple schema file.

## Big picture (what to know)

- Primary purpose: read and validate `config.yaml` (root) against `required_schema.yaml`, provide a programmatic API to read/update/save values, and expose a few convenience properties for common sections (`llm`, `environments`, `drift_detection`).
- Major components:
  - `src/config/config.py` — main implementation (loading, validation, get/set/save, typed schema support).
  - `required_schema.yaml` — canonical schema the code validates against.
  - `config.yaml` — example/active configuration (project root).
  - `tests/config_test.py` — minimal PyTest coverage demonstrating usage.

## Key files to reference

- `src/config/config.py` — read this first. It contains:
  - `Config(config_path, required_schema_path)` constructor
  - `load()` to parse both YAMLs and validate
  - `get(path, default=None)`, `set(path, value)`, `update(path, value)`, `save()`
  - `validate_config(required_keys, config)` — supports schema types declared as strings (e.g. `"str"`) or dicts with a `type` key, and list `items` schemas.
- `required_schema.yaml` — shows accepted shape: `llm`, `watch.environments` (list), `drift_detection`, `output`.
- `config.yaml` — example of real values used by the project (LLM provider, watch paths, drift interval, log settings).

## Project-specific conventions and patterns

- Schema format: schemas use a lightweight mapping of key -> expected type. Supported type names: `str`, `int`, `float`, `bool`, `list`, `dict`. A schema entry may be a dict with `type: list` and an `items:` block describing the list element shape. Example from `required_schema.yaml`:

  watch:
    environments:
      type: list
      items:
        name: str
        paths: list

- Config paths use dot notation for `get`/`set`, e.g. `cfg.get('llm.provider')`.
- When adding new top-level keys to `config.yaml`, also update `required_schema.yaml` — otherwise `validate_config` will raise `KeyError`.
- `Config.set()` re-validates the entire config after changes. Expect `KeyError`, `TypeError`, or `ValueError` on invalid changes.

## How to run tests and quick dev commands

- Install dependencies:

  pip install -r requirements.txt

- Run tests from the repository root:

  pytest -q

- The tests show how to create temporary YAMLs using `tmp_path` and how `Config` is used; use them as small usage examples.

## Runtime / integration notes

- LLM integration is configuration-driven. `config.yaml` contains an `llm` section with keys `provider`, `model`, `endpoint`, and `api_key_env_var`. The code does not call any LLM itself — it only exposes the config. Expect external services (e.g., Ollama on `http://localhost:11434`) and an environment variable named by `api_key_env_var` when higher-level code is added.
- Logging/output: `output.log_file` points to a filesystem path (example: `/var/log/drift_detection.log`) — ensure write permissions if you run production scenarios.

## Examples (useful snippets)

- Load and inspect provider:

  from src.config.config import Config
  cfg = Config('config.yaml', 'required_schema.yaml')
  cfg.load()
  print(cfg.get('llm.provider'))

- Update a nested value and save:

  cfg.set('drift_detection.interval_seconds', 600)
  cfg.save()

## Error behaviors agents should respect

- Missing files: constructor raises `FileNotFoundError` if either YAML path doesn't exist.
- Missing required keys: `validate_config` raises `KeyError` for missing keys in the loaded config.
- Type mismatches: `TypeError` if a value doesn't match the schema type; `ValueError` if the schema contains an unknown type.

## When you edit config shape

- Always update `required_schema.yaml` in the same change commit. Tests and `Config` expect schema and config to match exactly.

## Where to look next when extending functionality

- Add higher-level logic (LLM calls, drift detection) in a new package under `src/` and follow the simple import path pattern `from src.<module> import <Class>` used in tests.
- Add tests to `tests/` using `pytest` and `tmp_path` for temporary YAML artifacts.

---

If anything here is unclear or you want the instructions expanded with CI, local debug flows, or a runnable example script, tell me which area to expand and I will iterate.
