"""Shared helpers for generate_snapshot.py and generate_recipes.py (workspace, closure, package.xml)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

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
    """Parse supported-packages.json: seed names and optional per-package options (e.g. test_package)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    raw_list = data.get("supported-packages")
    if not raw_list:
        raise ValueError("no non-empty 'supported-packages' list")
    seen: set[str] = set()
    names: list[str] = []
    test_package_by_name: dict[str, dict] = {}
    for i, item in enumerate(raw_list):
        if isinstance(item, str):
            name = item.strip()
            if not name:
                raise ValueError(f"supported-packages[{i}]: empty string")
        elif isinstance(item, dict):
            raw_name = item.get("name")
            if not isinstance(raw_name, str) or not raw_name.strip():
                raise ValueError(f"supported-packages[{i}]: object needs non-empty string 'name'")
            name = raw_name.strip()
            tp = item.get("test_package")
            if tp is not None:
                if not isinstance(tp, dict):
                    raise ValueError(f"supported-packages[{i}] ({name!r}): 'test_package' must be an object")
                test_package_by_name[name] = tp
        else:
            raise ValueError(
                f"supported-packages[{i}]: expected string or object, got {type(item).__name__}"
            )
        if name in seen:
            print(f"Warning: duplicate entry {name!r} in supported-packages.json, skipping")
            continue
        seen.add(name)
        names.append(name)
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
