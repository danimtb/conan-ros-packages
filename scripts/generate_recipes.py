#!/usr/bin/env python3
"""Generate conandata.yml and packages-build-order.json from snapshot + supported-packages (see --help)."""

from __future__ import annotations

import argparse
import heapq
import json
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import yaml

from conan_ros_tools import (
    discover_transitive_closure,
    fetch_package_xml_depends,
    git_url_to_archive_url,
    git_url_to_raw_package_xml_url,
    load_supported_package_names,
    resolve_workspace_dir,
)


def _version_key_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')


_ConandataDumper = yaml.SafeDumper
_ConandataDumper.add_representer(str, _version_key_representer)


def load_snapshot_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("snapshot root must be a mapping")
    return data


def write_conandata_yml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out:
        yaml.dump(
            data,
            out,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            Dumper=_ConandataDumper,
        )


def conan_refs_for_rosdistro_names(
    dep_names: Iterable[str],
    snapshot: dict,
) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for dep in sorted(set(dep_names)):
        entry = snapshot.get(dep)
        if not entry:
            continue
        ver = entry.get("version")
        if ver is None:
            continue
        ref = f"{dep}/{ver}"
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def conan_requires_from_package_xml_depends(
    package_xml_depends: dict[str, list[str]],
    snapshot: dict,
) -> tuple[list[str], list[str]]:
    # REP-140: most ROS packages use build_depend / build_export_depend, not <depend>.
    host_keys = (
        "build_depend",
        "build_export_depend",
        "depend",
        "exec_depend",
    )
    tool_keys = ("buildtool_depend", "buildtool_export_depend")
    run_names: list[str] = []
    for k in host_keys:
        run_names.extend(package_xml_depends.get(k, []))
    tool_names: list[str] = []
    for k in tool_keys:
        tool_names.extend(package_xml_depends.get(k, []))
    return (
        conan_refs_for_rosdistro_names(run_names, snapshot),
        conan_refs_for_rosdistro_names(tool_names, snapshot),
    )


def resolve_package_xml_depends_for_package(
    name: str,
    entry: dict,
    url: str,
    tag: str,
    *,
    fetch: bool = True,
) -> dict[str, list[str]] | None:
    raw = entry.get("package_xml_depends")
    if isinstance(raw, dict):
        return raw
    if raw is not None:
        print(f"Warning: {name} invalid package_xml_depends, ignoring")
    if not fetch:
        return None
    raw_pkg = git_url_to_raw_package_xml_url(url, tag)
    if not raw_pkg:
        print(f"Warning: {name} could not derive raw package.xml URL from {url!r}")
        return None
    try:
        return fetch_package_xml_depends(raw_pkg)
    except RuntimeError as e:
        print(f"Warning: {name} package.xml: {e}")
        return None


def conan_ref_pkg_name(ref: str) -> str:
    if "/" not in ref:
        return ref
    return ref.split("/", 1)[0]


def topological_build_order(packages: set[str], deps: dict[str, set[str]]) -> list[str]:
    in_degree = {p: len(deps.get(p, set())) for p in packages}
    successors: dict[str, list[str]] = defaultdict(list)
    for p in packages:
        for d in deps.get(p, set()):
            successors[d].append(p)
    for d in successors:
        successors[d].sort()

    heap = [p for p in packages if in_degree[p] == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        n = heapq.heappop(heap)
        order.append(n)
        for s in successors.get(n, []):
            in_degree[s] -= 1
            if in_degree[s] == 0:
                heapq.heappush(heap, s)
    if len(order) != len(packages):
        raise SystemExit("Cycle in dependencies among supported packages")
    return order


def internal_edges_from_conan_refs(
    written: set[str],
    closure: set[str],
    refs_by_pkg: dict[str, list[str]],
) -> dict[str, set[str]]:
    deps: dict[str, set[str]] = {p: set() for p in written}
    errors: list[str] = []
    for p, refs in refs_by_pkg.items():
        if p not in written:
            continue
        for ref in refs:
            dep = conan_ref_pkg_name(ref)
            if dep not in closure:
                continue
            if dep not in written:
                errors.append(
                    f"{p} depends on {dep!r} (in transitive closure) but it was not generated"
                )
                continue
            if dep != p:
                deps[p].add(dep)
    if errors:
        raise SystemExit("Cannot order build:\n" + "\n".join(errors))
    return deps


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--work-dir",
        default="kilted",
        metavar="REL_PATH",
        help="Workspace under repo root (default: kilted)",
    )
    p.add_argument(
        "--build",
        action="store_true",
        help="Run conan create for each recipe in build order",
    )
    args = p.parse_args()

    ws = resolve_workspace_dir(args.work_dir)
    supported_path = ws / "supported-packages.json"
    snapshot_path = ws / "rosdistro_snapshot.yaml"
    order_path = ws / "packages-build-order.json"
    recipes_dir = ws / "recipes"

    if not supported_path.exists():
        raise SystemExit(f"Missing {supported_path}")
    if not snapshot_path.exists():
        raise SystemExit(
            f"Missing {snapshot_path}. Run: python scripts/generate_snapshot.py --work-dir {args.work_dir}"
        )

    try:
        snapshot = load_snapshot_yaml(snapshot_path)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{snapshot_path}: {e}") from e
    try:
        seeds = load_supported_package_names(supported_path)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{supported_path}: {e}") from e

    closure = discover_transitive_closure(
        seeds, snapshot, skip_fetch=False, require_github_archive=True
    )
    if not closure:
        raise SystemExit("No packages to generate (all seeds invalid or skipped)")

    added = sorted(closure - set(seeds))
    if added:
        print("Transitive closure (not in supported-packages.json): " + ", ".join(added))

    refs_by_pkg: dict[str, list[str]] = {}
    written: set[str] = set()

    for name in sorted(closure):
        entry = snapshot.get(name)
        if not entry:
            print(f"Warning: {name} not found in snapshot, skipping")
            continue
        tag, url = entry.get("tag"), entry.get("url")
        version = entry.get("version")
        if not tag or not url:
            print(f"Warning: {name} missing tag or url in snapshot, skipping")
            continue
        archive_url = git_url_to_archive_url(url, tag)
        if not archive_url:
            print(f"Warning: {name} has non-GitHub url {url!r}, skipping")
            continue

        pxml = resolve_package_xml_depends_for_package(name, entry, url, tag)
        ver = str(version) if version else "0.0.0"
        conandata: dict = {"sources": {ver: {"url": archive_url}}}
        req: list[str] = []
        tool: list[str] = []
        if pxml:
            req, tool = conan_requires_from_package_xml_depends(pxml, snapshot)
            if req:
                conandata["requires"] = {ver: req}
            if tool:
                conandata["tool_requires"] = {ver: tool}
        refs_by_pkg[name] = [*req, *tool]
        written.add(name)

        cpath = recipes_dir / name / "conandata.yml"
        cpath.parent.mkdir(parents=True, exist_ok=True)
        write_conandata_yml(cpath, conandata)
        print(f"Wrote {cpath}")

    edges = internal_edges_from_conan_refs(written, closure, refs_by_pkg)
    build_order = topological_build_order(written, edges)
    with open(order_path, "w", encoding="utf-8") as out:
        json.dump({"build-order": build_order}, out, indent=4)
        out.write("\n")
    print(f"Wrote {order_path}")

    if args.build:
        for name in build_order:
            cmd = ["conan", "create", str(recipes_dir / name)]
            print(f"Running: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=ws, check=True)


if __name__ == "__main__":
    main()
