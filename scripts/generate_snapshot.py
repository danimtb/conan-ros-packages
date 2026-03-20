#!/usr/bin/env python3
"""Build rosdistro_snapshot.yaml from workspace distribution.yaml (see --help)."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from conan_ros_tools import (
    discover_transitive_closure,
    fetch_package_xml_depends,
    git_url_to_raw_package_xml_url,
    load_supported_package_names,
    resolve_workspace_dir,
)


class _SnapshotDumper(yaml.SafeDumper):
    pass


def _snapshot_represent_str(dumper, data: str):
    if re.fullmatch(r"\d+\.\d+", data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return yaml.SafeDumper.represent_str(dumper, data)


_SnapshotDumper.add_representer(str, _snapshot_represent_str)


def load_distribution_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be a mapping")
    return data


def _upstream_version_from_release_version(debian_version: str) -> str:
    s = str(debian_version).strip()
    if not s:
        return s
    m = re.match(r"^(.+)-(\d+)$", s)
    if m:
        return m.group(1)
    return s


def _package_names_from_release(release: dict, repo_key: str) -> list[str]:
    raw = release.get("packages")
    if raw is None:
        return [repo_key]
    if isinstance(raw, list):
        return [p for p in raw if isinstance(p, str) and p.strip()]
    if isinstance(raw, dict):
        return sorted(raw.keys())
    return []


def _debian_version_for_package(version_field, package_name: str) -> str | None:
    if isinstance(version_field, dict):
        v = version_field.get(package_name)
        return str(v).strip() if v is not None else None
    if isinstance(version_field, str):
        return version_field.strip() or None
    if version_field is None:
        return None
    return str(version_field).strip() or None


def snapshot_from_distribution_dict(dist: dict) -> dict[str, dict]:
    repos = dist.get("repositories")
    if not isinstance(repos, dict):
        return {}

    out: dict[str, dict] = {}
    duplicates: list[tuple[str, str, str]] = []

    for repo_key, repo_data in repos.items():
        if not isinstance(repo_data, dict):
            continue
        release = repo_data.get("release")
        if not isinstance(release, dict):
            continue
        url = release.get("url")
        if not url or not isinstance(url, str):
            continue
        tags = release.get("tags")
        if not isinstance(tags, dict):
            continue
        tag_tmpl = tags.get("release")
        if not tag_tmpl or not isinstance(tag_tmpl, str):
            continue
        if "{package}" not in tag_tmpl or "{version}" not in tag_tmpl:
            continue

        version_field = release.get("version")
        pkg_names = _package_names_from_release(release, repo_key)
        if not pkg_names:
            continue

        for pkg in pkg_names:
            deb = _debian_version_for_package(version_field, pkg)
            if not deb:
                continue
            tag = tag_tmpl.replace("{package}", pkg).replace("{version}", deb)
            upstream = _upstream_version_from_release_version(deb)
            entry = {"tag": tag, "url": url.strip(), "version": upstream}
            if pkg in out:
                duplicates.append((pkg, out[pkg]["url"], url))
            out[pkg] = entry

    for pkg, old_u, new_u in duplicates:
        if old_u != new_u:
            print(
                f"Warning: package {pkg!r} appears in multiple release repos "
                f"({old_u!r} vs {new_u!r}); keeping last"
            )

    return dict(sorted(out.items()))


def enrich_snapshot_package_xml_depends(snapshot: dict[str, dict], *, skip_fetch: bool) -> None:
    if skip_fetch:
        return
    for name in sorted(snapshot.keys()):
        entry = snapshot[name]
        if isinstance(entry.get("package_xml_depends"), dict):
            continue
        url = entry.get("url")
        tag = entry.get("tag")
        if not url or not tag:
            continue
        raw = git_url_to_raw_package_xml_url(str(url), str(tag))
        if not raw:
            print(f"Warning: {name}: skip package.xml (non-GitHub release url)")
            continue
        try:
            deps = fetch_package_xml_depends(raw)
        except RuntimeError as e:
            print(f"Warning: {name}: {e}")
            continue
        entry["package_xml_depends"] = deps


def dump_snapshot_yaml(snapshot: dict, path: Path, header_lines: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as out:
        if header_lines:
            for line in header_lines:
                out.write(line.rstrip("\n") + "\n")
        yaml.dump(
            snapshot,
            out,
            default_flow_style=False,
            sort_keys=True,
            allow_unicode=True,
            Dumper=_SnapshotDumper,
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--work-dir",
        default="kilted",
        metavar="REL_PATH",
        help="Workspace under repo root (default: kilted): distribution.yaml, supported-packages.json, output",
    )
    p.add_argument(
        "--all-packages",
        action="store_true",
        help="Snapshot every released package (ignore supported-packages.json)",
    )
    args = p.parse_args()

    ws = resolve_workspace_dir(args.work_dir)
    dist_path = ws / "distribution.yaml"
    supported_path = ws / "supported-packages.json"
    out_path = ws / "rosdistro_snapshot.yaml"

    if not dist_path.exists():
        raise SystemExit(
            f"Missing {dist_path}. Add REP-143 distribution.yaml (e.g. from rosdistro kilted/)."
        )
    dist = load_distribution_yaml(dist_path)

    full = snapshot_from_distribution_dict(dist)
    if not full:
        raise SystemExit("No released packages parsed from distribution (check file format)")

    if args.all_packages:
        snapshot = full
    else:
        if not supported_path.exists():
            raise SystemExit(f"Missing {supported_path}. Use --all-packages or add the file.")
        try:
            seeds = load_supported_package_names(supported_path)
        except (OSError, ValueError) as e:
            raise SystemExit(f"{supported_path}: {e}") from e
        closure = discover_transitive_closure(seeds, full, require_github_archive=False)
        if not closure:
            raise SystemExit("No packages in transitive closure (check seeds and warnings above)")
        snapshot = {name: full[name] for name in sorted(closure)}

    enrich_snapshot_package_xml_depends(snapshot, skip_fetch=False)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [
        "# rosdistro_snapshot.yaml — Conan-focused snapshot + package.xml deps",
        f"# Generated at {ts} UTC",
        f"# Source: {dist_path}",
        f"# Packages: {len(snapshot)}",
    ]
    dump_snapshot_yaml(snapshot, out_path, header_lines=header)
    print(f"Wrote {out_path} ({len(snapshot)} packages)")


if __name__ == "__main__":
    main()
