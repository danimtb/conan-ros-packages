"""Shared helpers for generate_snapshot.py and generate_recipes.py (workspace, closure, package.xml)."""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

import yaml

_PACKAGE_XML_DEPEND_TAGS = frozenset(
    {
        "build_depend",
        "build_export_depend",
        "buildtool_depend",
        "buildtool_export_depend",
        "exec_depend",
        "test_depend",
        "doc_depend",
        "depend",
        "group_depend",
    }
)


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_workspace_dir(work_dir: str) -> Path:
    root = repository_root()
    p = Path(work_dir)
    if p.is_absolute():
        raise SystemExit("--work-dir must be relative to the repository root (not an absolute path)")
    out = (root / p).resolve()
    try:
        out.relative_to(root.resolve())
    except ValueError:
        raise SystemExit(f"--work-dir {work_dir!r} resolves outside the repository") from None
    return out


def _github_owner_repo(git_url: str) -> tuple[str, str] | None:
    base = git_url.rstrip("/").removesuffix(".git")
    if "github.com/" not in base:
        return None
    _, tail = base.split("github.com/", 1)
    parts = tail.strip("/").split("/")
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def git_url_to_raw_package_xml_url(git_url: str, tag: str) -> str | None:
    parsed = _github_owner_repo(git_url)
    if not parsed:
        return None
    owner, repo = parsed
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{tag}/package.xml"


def git_url_to_archive_url(git_url: str, tag: str) -> str | None:
    if "github.com" not in git_url:
        return None
    base = git_url.rstrip("/").removesuffix(".git")
    encoded_tag = quote(tag, safe="")
    return f"{base}/archive/refs/tags/{encoded_tag}.tar.gz"


def _xml_local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _parse_package_xml_depends_and_export(root: ET.Element) -> tuple[dict[str, list[str]], dict[str, str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    export_kv: dict[str, str] = {}
    for el in root:
        kind = _xml_local_name(el.tag)
        if kind in _PACKAGE_XML_DEPEND_TAGS:
            text = (el.text or "").strip()
            if text:
                buckets[kind].append(text)
        elif kind == "export":
            for child in el:
                ck = _xml_local_name(child.tag)
                ct = (child.text or "").strip()
                if ct:
                    export_kv[ck] = ct
    deps = {k: sorted(set(v)) for k, v in sorted(buckets.items()) if v}
    export_out = dict(sorted(export_kv.items())) if export_kv else {}
    return deps, export_out


def fetch_package_xml_depends_and_export(
    raw_url: str, timeout: float = 30.0
) -> tuple[dict[str, list[str]], dict[str, str]]:
    req = urllib.request.Request(
        raw_url,
        headers={"User-Agent": "conan-ros-kilted (dependency metadata)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"failed to fetch {raw_url}: {e}") from e

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise RuntimeError(f"invalid XML from {raw_url}: {e}") from e

    return _parse_package_xml_depends_and_export(root)


def fetch_package_xml_depends(raw_url: str, timeout: float = 30.0) -> dict[str, list[str]]:
    deps, _ = fetch_package_xml_depends_and_export(raw_url, timeout)
    return deps


def ros_snapshot_dep_names_from_package_xml(
    package_xml_depends: dict[str, list[str]],
    snapshot: dict,
) -> list[str]:
    names: set[str] = set()
    for key in _PACKAGE_XML_DEPEND_TAGS:
        for n in package_xml_depends.get(key, []):
            if n in snapshot:
                names.add(n)
    return sorted(names)


def load_supported_packages(path: Path) -> tuple[list[str], dict[str, dict]]:
    """Parse supported-packages.yaml: seed names; merge test specs from supported-packages-tests.yaml when present.

    Main file: top-level ``supported-packages`` list of package name strings (comments allowed in YAML).

    Optional ``supported-packages-tests.yaml`` beside the main file: top-level ``test-packages`` mapping from
    package name to a test_package spec (type, script, command or commands, cmake, files, ...).
    A spec is applied only when that package name also appears in ``supported-packages``.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: root must be a mapping")
    raw_list = data.get("supported-packages")
    if not isinstance(raw_list, list) or not raw_list:
        raise ValueError(f"{path.name}: no non-empty 'supported-packages' list")
    seen: set[str] = set()
    names: list[str] = []
    for i, item in enumerate(raw_list):
        if not isinstance(item, str):
            raise ValueError(
                f"{path.name} supported-packages[{i}]: expected string "
                f"(put test_package under supported-packages-tests.yaml), got {type(item).__name__}"
            )
        name = item.strip()
        if not name:
            raise ValueError(f"{path.name} supported-packages[{i}]: empty string")
        if name in seen:
            print(f"Warning: duplicate entry {name!r} in {path.name}, skipping")
            continue
        seen.add(name)
        names.append(name)

    test_package_by_name: dict[str, dict] = {}
    tests_path = path.parent / "supported-packages-tests.yaml"
    if tests_path.exists():
        with open(tests_path, encoding="utf-8") as tf:
            tdata = yaml.safe_load(tf)
        if tdata is None:
            tdata = {}
        if not isinstance(tdata, dict):
            raise ValueError(f"{tests_path.name}: root must be a mapping")
        tp_map = tdata.get("test-packages")
        if tp_map is None:
            tp_map = {}
        if not isinstance(tp_map, dict):
            raise ValueError(f"{tests_path.name}: 'test-packages' must be a mapping")
        supported_set = set(names)
        for raw_key, spec in tp_map.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                raise ValueError(f"{tests_path.name}: test-packages keys must be non-empty strings")
            key = raw_key.strip()
            if key not in supported_set:
                print(
                    f"Warning: test-packages entry {key!r} not in {path.name} supported list, ignoring"
                )
                continue
            if not isinstance(spec, dict):
                raise ValueError(f"{tests_path.name} test-packages[{key!r}]: must be a mapping")
            test_package_by_name[key] = spec

    return names, test_package_by_name


def load_supported_package_names(path: Path) -> list[str]:
    names, _ = load_supported_packages(path)
    return names


def discover_transitive_closure(
    seeds: Iterable[str],
    snapshot: dict[str, dict],
    *,
    skip_fetch: bool = False,
    require_github_archive: bool = False,
) -> set[str]:
    closure: set[str] = set()
    pending: deque[str] = deque(seeds)

    while pending:
        name = pending.popleft()
        if name in closure:
            continue

        entry = snapshot.get(name)
        if not entry:
            print(f"Warning: {name} not found in rosdistro snapshot, skipping")
            continue

        tag = entry.get("tag")
        url = entry.get("url")
        if not tag or not url:
            print(f"Warning: {name} missing tag or url in snapshot, skipping")
            continue

        if require_github_archive:
            if not git_url_to_archive_url(url, tag):
                print(f"Warning: {name} has non-GitHub url {url!r}, skipping")
                continue
        else:
            if not git_url_to_raw_package_xml_url(url, tag):
                print(f"Warning: {name} could not derive raw package.xml URL from {url!r}")
                continue

        closure.add(name)

        dep_dict: dict[str, list[str]] | None = None
        raw_dep = entry.get("package_xml_depends")
        if isinstance(raw_dep, dict):
            dep_dict = raw_dep
        elif not skip_fetch:
            raw_pkg = git_url_to_raw_package_xml_url(url, tag)
            if raw_pkg:
                try:
                    dep_dict, export_meta = fetch_package_xml_depends_and_export(raw_pkg)
                    entry["package_xml_depends"] = dep_dict
                    if export_meta:
                        entry["package_xml_export"] = export_meta
                except RuntimeError as e:
                    print(f"Warning: {name}: {e}")
            else:
                print(f"Warning: {name} could not derive raw package.xml URL from {url!r}")

        if dep_dict is not None:
            for dep in ros_snapshot_dep_names_from_package_xml(dep_dict, snapshot):
                pending.append(dep)

    return closure
