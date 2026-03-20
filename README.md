# conan-ros

Tools under `scripts/` read a REP-143 `distribution.yaml` and produce Conan-oriented metadata for a **workspace** directory per ROS distro (e.g. `kilted/`): snapshot YAML, per-package `conandata.yml`, and `packages-build-order.json`.

## Commands

From the **repository root**:

```bash
# Snapshot (fetches package.xml from GitHub for dependency closure)
# Default: only supported-packages.json + transitive ROS deps present in the distribution
python scripts/generate_snapshot.py --work-dir kilted

# Every released package in the distribution (no supported-packages.json)
python scripts/generate_snapshot.py --all-packages

# Generate conandata + packages-build-order.json
python scripts/generate_recipes.py

# Same, then run conan create for each recipe in order
python scripts/generate_recipes.py --build
```

Use `--work-dir foxy` (or any other folder under the repo) for another ROS release; paths must be **relative to the repo root**.

`--work-dir` must be a path relative to the repository root (not absolute).


## Workspace layout

At the repository root, the workspace folder (e.g. `kilted/`) holds inputs and generated artifacts:

**Inputs**

- `distribution.yaml` — rosdistro distribution file in the workspace
- `supported-packages.json` — seed package names; `generate_snapshot.py` includes these plus transitive ROS dependencies (unless `--all-packages`). Same file drives `generate_recipes.py`.

**Generated**

- `rosdistro_snapshot.yaml`
- `packages-build-order.json`
- `recipes/<package>/` — Conan recipes and generated `conandata.yml`
