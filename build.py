#!/usr/bin/env python3
"""
Generate conandata.yml for each package in build_order.json, then run conan create.

Reads build_order.json, deduces build order from the "requires" dependency graph
(topological sort), looks up each package in rosdistro_snapshot.yaml,
writes recipes/<name>/conandata.yml with a sources entry containing the archive
URL (with tag), and runs conan create on recipes/<name>.
"""

import json
import subprocess
from collections import deque
from pathlib import Path
from urllib.parse import quote

import yaml


def _version_key_representer(dumper, data):
    """Quote version-like keys so YAML does not parse them as floats."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


# Use SafeDumper and override str so version keys are quoted in output
_SafeDumper = yaml.SafeDumper
_SafeDumper.add_representer(str, _version_key_representer)


def git_url_to_archive_url(git_url: str, tag: str) -> str | None:
    """
    Convert a GitHub git URL and tag to the corresponding archive tarball URL.

    e.g. https://github.com/ros2-gbp/ament_cmake-release.git
         + tag release/kilted/ament_cmake_core/2.7.4-1
    ->  https://github.com/ros2-gbp/ament_cmake-release/archive/refs/tags/release%2Fkilted%2Fament_cmake_core%2F2.7.4-1.tar.gz
    """
    if "github.com" not in git_url:
        return None
    # Strip .git and trailing slash
    base = git_url.rstrip("/").removesuffix(".git")
    # URL-encode the tag (e.g. slashes -> %2F)
    encoded_tag = quote(tag, safe="")
    return f"{base}/archive/refs/tags/{encoded_tag}.tar.gz"


def _topological_build_order(build_order_data: dict) -> list[str]:
    """
    Return package names in build order: dependencies first.
    Uses Kahn's algorithm; only considers packages that appear in build_order_data.
    """
    packages = list(build_order_data.keys())
    in_degree = {p: 0 for p in packages}
    successors = {p: [] for p in packages}
    for p in packages:
        for r in build_order_data[p].get("requires", []):
            if r in packages:
                in_degree[p] += 1
                successors[r].append(p)
    queue = deque(p for p in packages if in_degree[p] == 0)
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for s in successors[n]:
            in_degree[s] -= 1
            if in_degree[s] == 0:
                queue.append(s)
    if len(order) != len(packages):
        raise SystemExit("Cycle in build-order dependencies")
    return order


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    build_order_path = repo_root / "build_order.json"
    snapshot_path = repo_root / "rosdistro_snapshot.yaml"
    recipes_dir = repo_root / "recipes"

    if not build_order_path.exists():
        raise SystemExit(f"Missing {build_order_path}")
    if not snapshot_path.exists():
        raise SystemExit(f"Missing {snapshot_path}")

    with open(snapshot_path, encoding="utf-8") as f:
        snapshot = yaml.safe_load(f)

    if not snapshot:
        raise SystemExit("rosdistro_snapshot.yaml is empty")

    with open(build_order_path, encoding="utf-8") as f:
        data = json.load(f)
    build_order_data = data.get("build-order", {})
    if not build_order_data:
        raise SystemExit("build_order.json has no 'build-order' entry or it is empty")
    package_names = _topological_build_order(build_order_data)

    for name in package_names:
        entry = snapshot.get(name)
        if not entry:
            print(f"Warning: {name} not found in rosdistro_snapshot.yaml, skipping")
            continue

        tag = entry.get("tag")
        url = entry.get("url")
        version = entry.get("version")

        if not tag or not url:
            print(f"Warning: {name} missing tag or url in snapshot, skipping")
            continue

        archive_url = git_url_to_archive_url(url, tag)
        if not archive_url:
            print(f"Warning: {name} has non-GitHub url {url!r}, skipping")
            continue

        recipe_dir = recipes_dir / name
        recipe_dir.mkdir(parents=True, exist_ok=True)
        conandata_path = recipe_dir / "conandata.yml"

        # Conan expects version as key (quoted in YAML to avoid float parsing)
        version_str = str(version) if version else "0.0.0"
        conandata = {
            "sources": {
                version_str: {
                    "url": archive_url,
                }
            }
        }
        with open(conandata_path, "w", encoding="utf-8") as out:
            yaml.dump(
                conandata,
                out,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                Dumper=_SafeDumper,
            )

        print(f"Wrote {conandata_path}")

        # Run conan create for this recipe
        cmd = ["conan", "create", str(recipe_dir)]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=repo_root, check=True)


if __name__ == "__main__":
    main()
