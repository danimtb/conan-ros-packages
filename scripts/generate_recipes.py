#!/usr/bin/env python3
"""Generate Conan recipes from repo-root templates/ (by package.xml build_type), conandata.yml, and packages-build-order.json (see --help).

supported-packages.yaml lists seed package names (strings only; YAML comments allowed).
Optional supported-packages-tests.yaml (same directory) maps package names to test_package specs under
``test-packages``; a test_package/ is generated only when the name appears in both files.
All other recipes (including transitive deps) have no test_package.

test_package types (templates under repo templates/test_package/<type>/):
  python — fields: script (required), path (optional, default src/example.py). Template conanfile + written script file.
  cmake — fields: cmake (required), path (optional, default CMakeLists.txt), files (optional). Template conanfile + CMakeLists body from JSON.
  run — field: command (required). Template conanfile with embedded command literal.
"""

from __future__ import annotations

import argparse
import heapq
import json
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import yaml

from conan_ros_tools import (
    discover_transitive_closure,
    fetch_package_xml_depends_and_export,
    git_url_to_archive_url,
    git_url_to_raw_package_xml_url,
    load_supported_packages,
    repository_root,
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
    require_keys = (
        "build_depend",
        "build_export_depend",
        "depend",
        "exec_depend",
        "build",
        "buildtool_depend",
        "buildtool_export_depend",
    )
    tool_require_keys = () #("buildtool_depend", "buildtool_export_depend")
    run_names: list[str] = []
    for k in require_keys:
        run_names.extend(package_xml_depends.get(k, []))
    tool_names: list[str] = []
    for k in tool_require_keys:
        tool_names.extend(package_xml_depends.get(k, []))
    return (
        conan_refs_for_rosdistro_names(run_names, snapshot),
        conan_refs_for_rosdistro_names(tool_names, snapshot),
    )


def _snake_to_pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_") if part)


def _entry_has_build_type(entry: dict) -> bool:
    exp = entry.get("package_xml_export")
    if not isinstance(exp, dict):
        return False
    bt = exp.get("build_type")
    return isinstance(bt, str) and bool(bt.strip())


def ensure_package_xml_fields(
    name: str,
    entry: dict,
    url: str,
    tag: str,
    *,
    fetch: bool,
) -> None:
    has_deps = isinstance(entry.get("package_xml_depends"), dict)
    has_bt = _entry_has_build_type(entry)
    if has_deps and has_bt:
        return
    if not fetch:
        return
    raw_pkg = git_url_to_raw_package_xml_url(url, tag)
    if not raw_pkg:
        print(f"Warning: {name} could not derive raw package.xml URL from {url!r}")
        return
    try:
        deps, export_meta = fetch_package_xml_depends_and_export(raw_pkg)
    except RuntimeError as e:
        print(f"Warning: {name} package.xml: {e}")
        return
    if not has_deps:
        entry["package_xml_depends"] = deps
    if not has_bt and export_meta:
        entry["package_xml_export"] = export_meta


def resolve_package_xml_depends_for_package(
    name: str,
    entry: dict,
    url: str,
    tag: str,
    *,
    fetch: bool = True,
) -> dict[str, list[str]] | None:
    raw = entry.get("package_xml_depends")
    if raw is not None and not isinstance(raw, dict):
        print(f"Warning: {name} invalid package_xml_depends, ignoring")
        raw = None
    ensure_package_xml_fields(name, entry, url, tag, fetch=fetch)
    out = entry.get("package_xml_depends")
    return out if isinstance(out, dict) else None


def build_type_for_package(
    name: str,
    entry: dict,
    url: str,
    tag: str,
    *,
    fetch: bool,
) -> str | None:
    ensure_package_xml_fields(name, entry, url, tag, fetch=fetch)
    exp = entry.get("package_xml_export")
    if not isinstance(exp, dict):
        return None
    bt = exp.get("build_type")
    if not isinstance(bt, str):
        return None
    s = bt.strip()
    return s or None


def copy_template_tree(
    template_root: Path,
    dest_root: Path,
    *,
    package_name: str,
    extra_substitutions: dict[str, str] | None = None,
) -> None:
    subs = {
        "{{package_name}}": package_name,
        "{{recipe_class}}": _snake_to_pascal(package_name) + "Recipe",
        "{{test_recipe_class}}": _snake_to_pascal(package_name) + "TestConan",
    }
    if extra_substitutions:
        subs.update(extra_substitutions)
    for path in sorted(template_root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(template_root)
        if rel.parts and rel.parts[0] == "__pycache__":
            continue
        out_path = dest_root / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            shutil.copy2(path, out_path)
            continue
        if "{{" in text:
            for key, val in subs.items():
                text = text.replace(key, val)
        out_path.write_text(text, encoding="utf-8", newline="\n")


def _validate_relative_under_test_package(rel: str, *, field: str) -> Path:
    p = Path(rel)
    if p.is_absolute():
        raise SystemExit(f"test_package {field} must be relative, not {rel!r}")
    if ".." in p.parts:
        raise SystemExit(f"test_package {field} must not contain '..': {rel!r}")
    return p


def _write_test_package_python(
    recipe_dir: Path, package_name: str, spec: dict, *, templates_root: Path
) -> None:
    script = spec.get("script")
    if not isinstance(script, str):
        raise SystemExit(
            f"{package_name}: test_package type 'python' requires a string 'script' field "
            "(file contents executed under PyEnv in test_package/)"
        )
    raw_path = spec.get("path", "src/example.py")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit(f"{package_name}: test_package 'path' must be a non-empty string")
    rel = _validate_relative_under_test_package(raw_path.strip(), field="path")
    tp = recipe_dir / "test_package"
    tpl = templates_root / "test_package" / "python"
    if not tpl.is_dir():
        raise SystemExit(f"missing template directory {tpl}")
    copy_template_tree(
        tpl,
        tp,
        package_name=package_name,
        extra_substitutions={"{{script_relpath}}": rel.as_posix()},
    )
    script_path = tp / rel
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8", newline="\n")


def _write_test_package_cmake(
    recipe_dir: Path, package_name: str, spec: dict, *, templates_root: Path
) -> None:
    cmake_body = spec.get("cmake")
    if not isinstance(cmake_body, str):
        raise SystemExit(
            f"{package_name}: test_package type 'cmake' requires a string 'cmake' field "
            "(contents written under test_package/, like python 'script')"
        )
    raw_path = spec.get("path", "CMakeLists.txt")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit(f"{package_name}: test_package 'path' must be a non-empty string")
    rel = _validate_relative_under_test_package(raw_path.strip(), field="path")
    tp = recipe_dir / "test_package"
    tpl = templates_root / "test_package" / "cmake"
    if not tpl.is_dir():
        raise SystemExit(f"missing template directory {tpl}")
    copy_template_tree(
        tpl,
        tp,
        package_name=package_name,
        extra_substitutions={"{{cmake}}": cmake_body},
    )
    default_cmake = tp / "CMakeLists.txt"
    if rel != Path("CMakeLists.txt"):
        dest = tp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(default_cmake), str(dest))

    extra = spec.get("files")
    if extra is not None:
        if not isinstance(extra, dict):
            raise SystemExit(f"{package_name}: test_package 'files' must be an object (path -> contents)")
        for rel_s, body in sorted(extra.items()):
            if not isinstance(rel_s, str) or not rel_s.strip():
                raise SystemExit(f"{package_name}: test_package files keys must be non-empty strings")
            if not isinstance(body, str):
                raise SystemExit(f"{package_name}: test_package files[{rel_s!r}] must be a string")
            fpath = _validate_relative_under_test_package(rel_s.strip(), field=f"files[{rel_s!r}]")
            out = tp / fpath
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body, encoding="utf-8", newline="\n")


def _write_test_package_run(
    recipe_dir: Path, package_name: str, spec: dict, *, templates_root: Path
) -> None:
    command = spec.get("command")
    if not isinstance(command, str) or not command.strip():
        raise SystemExit(
            f"{package_name}: test_package type 'run' requires a non-empty string 'command' "
            "(shell command run with conanrun env, e.g. a CLI installed by the package)"
        )
    tp = recipe_dir / "test_package"
    tpl = templates_root / "test_package" / "run"
    if not tpl.is_dir():
        raise SystemExit(f"missing template directory {tpl}")
    copy_template_tree(
        tpl,
        tp,
        package_name=package_name,
        extra_substitutions={"{{command_repr}}": json.dumps(command.strip())},
    )


def apply_test_package_override(
    recipe_dir: Path, package_name: str, spec: dict, *, templates_root: Path
) -> None:
    """Write test_package/ from templates/test_package/<type>/ plus supported-packages-tests.yaml fields."""
    tp = recipe_dir / "test_package"
    if tp.is_dir():
        shutil.rmtree(tp)

    kind = spec.get("type")
    if not isinstance(kind, str) or not kind.strip():
        raise SystemExit(
            f"{package_name}: test_package requires string 'type' (python, cmake, or run)"
        )
    kind_n = kind.strip().lower()
    if kind_n == "python":
        _write_test_package_python(recipe_dir, package_name, spec, templates_root=templates_root)
    elif kind_n == "cmake":
        _write_test_package_cmake(recipe_dir, package_name, spec, templates_root=templates_root)
    elif kind_n == "run":
        _write_test_package_run(recipe_dir, package_name, spec, templates_root=templates_root)
    else:
        raise SystemExit(
            f"{package_name}: unknown test_package.type {kind!r}; use python, cmake, or run"
        )
    print(f"Applied custom test_package ({kind_n}) for {package_name}")


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
    supported_path = ws / "supported-packages.yaml"
    snapshot_path = ws / "rosdistro_snapshot.yaml"
    order_path = ws / "packages-build-order.json"
    recipes_dir = ws / "recipes"
    templates_root = repository_root() / "templates"

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
        seeds, test_package_overrides = load_supported_packages(supported_path)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{supported_path}: {e}") from e

    closure = discover_transitive_closure(
        seeds, snapshot, skip_fetch=False, require_github_archive=True
    )
    if not closure:
        raise SystemExit("No packages to generate (all seeds invalid or skipped)")

    added = sorted(closure - set(seeds))
    if added:
        print("Transitive closure (not in supported-packages.yaml): " + ", ".join(added))

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

        build_type = build_type_for_package(name, entry, url, tag, fetch=True)
        if not build_type:
            raise SystemExit(
                f"{name}: missing package.xml <export><build_type> in snapshot "
                f"(and could not fetch it); add it to the snapshot or fix the release URL."
            )
        template_dir = templates_root / build_type
        if not template_dir.is_dir():
            raise SystemExit(
                f"{name}: build_type {build_type!r} has no template directory {template_dir}. "
                f"Add {template_dir}/ with conanfile.py."
            )
        dest_recipe = recipes_dir / name
        copy_template_tree(template_dir, dest_recipe, package_name=name)
        print(f"Copied template {template_dir} -> {dest_recipe}")

        tp_spec = test_package_overrides.get(name)
        if tp_spec is not None:
            apply_test_package_override(dest_recipe, name, tp_spec, templates_root=templates_root)
        else:
            stale_tp = dest_recipe / "test_package"
            if stale_tp.is_dir():
                shutil.rmtree(stale_tp)

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
