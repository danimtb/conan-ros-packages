#!/usr/bin/env python3
"""Shared rosdistro access for the generators, parameterised by ROS distro.

Everything distro-specific lives under `<repo>/<distro>/`:

    distro.yaml         input: snapshot, roots, and non-ROS dependency map
    packages.lock.yaml  resolved closure, generated and committed
    extra/              hand-written recipes copied into the index
    recipes/            local-recipes-index, generated and committed

Adding a distro is adding a directory. Nothing here knows about kilted.

Requires PyYAML:  pip install pyyaml
"""

from __future__ import annotations

import gzip
import io
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import yaml
except ImportError as exc:  # pragma: no cover - the generators cannot run without it
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
DATA_DIR = REPO_ROOT

DISTRO_YAML = "distro.yaml"
LOCK_YAML = "packages.lock.yaml"

ROSDISTRO_ARCHIVE = "https://github.com/ros/rosdistro/archive/refs/tags/{tag}.tar.gz"

DEPEND_TAGS = {
    "depend",
    "build_depend",
    "build_export_depend",
    "exec_depend",
    "buildtool_depend",
    "buildtool_export_depend",
}

REQUIRED_KEYS = ("rosdistro_tag", "cache_url", "conan_user")


class DistroError(Exception):
    """A distro is not configured, or its configuration is incomplete."""


@dataclass
class DistroConfig:
    """Everything the generators need to know about one ROS distro."""

    name: str
    root: Path
    rosdistro_tag: str
    cache_url: str
    conan_user: str
    packages: list[str]

    @classmethod
    def load(cls, name: str, data_dir: Path = DATA_DIR) -> "DistroConfig":
        root = data_dir / name
        if not root.is_dir():
            raise DistroError(
                f"No configuration for distro '{name}' at {root}.\n"
                f"Known distros: {', '.join(known_distros(data_dir)) or '(none)'}.\n"
                f"To add one, create that directory with {DISTRO_YAML}."
            )
        distro = _read_yaml(root / DISTRO_YAML)
        missing = [key for key in REQUIRED_KEYS if not distro.get(key)]
        if missing:
            raise DistroError(
                f"{root / DISTRO_YAML} is missing: {', '.join(missing)}"
            )
        packages = distro.get("packages") or []
        if not isinstance(packages, list) or not packages:
            raise DistroError(f"{root / DISTRO_YAML} must declare a non-empty packages list")
        if any(not isinstance(package, str) or not package.strip() for package in packages):
            raise DistroError(f"{root / DISTRO_YAML} contains an invalid package name")
        if len(packages) != len(set(packages)):
            raise DistroError(f"{root / DISTRO_YAML} contains duplicate package names")
        return cls(
            name=name,
            root=root,
            rosdistro_tag=distro["rosdistro_tag"],
            cache_url=distro["cache_url"],
            conan_user=distro["conan_user"],
            packages=packages,
        )

    @property
    def rosdistro_url(self) -> str:
        return ROSDISTRO_ARCHIVE.format(tag=self.rosdistro_tag)

    @property
    def rosdep_map_path(self) -> Path:
        return self.root / DISTRO_YAML

    @property
    def lock_path(self) -> Path:
        return self.root / LOCK_YAML

    @property
    def index_root(self) -> Path:
        """local-recipes-index root: this distro directory contains `recipes/`."""
        return self.root

    @property
    def extra_dir(self) -> Path:
        return self.root / "extra"


def known_distros(data_dir: Path = DATA_DIR) -> list:
    if not data_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in data_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / DISTRO_YAML).is_file()
    )


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        raise DistroError(f"Missing {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ros-conan-catalog/1.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _distribution_yaml(tarball: bytes, distro: str) -> dict:
    suffix = f"/{distro}/distribution.yaml"
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.name.endswith(suffix)), None)
        if member is None:
            raise DistroError(f"{distro}/distribution.yaml not found in the rosdistro tarball")
        return yaml.safe_load(tar.extractfile(member))


def distribution_index(tarball: bytes, distro: str) -> dict:
    """Package name -> release repo, version and tag template, from the pinned tag."""
    index = {}
    for repo_name, repo in (_distribution_yaml(tarball, distro).get("repositories") or {}).items():
        release = repo.get("release") or {}
        url = release.get("url")
        version = release.get("version")
        tag = (release.get("tags") or {}).get("release")
        if not (url and version and tag):
            continue
        for package in release.get("packages") or [repo_name]:
            index[package] = {"repo": url, "version": version, "tag": tag}
    return index


def distribution_names(tarball: bytes, distro: str) -> set:
    """Every package name the pinned distribution lists, released or not."""
    names: set = set()
    for repo in (_distribution_yaml(tarball, distro).get("repositories") or {}).values():
        release = repo.get("release") or {}
        packages = release.get("packages")
        if packages:
            names.update(packages)
            continue
        # Single-package repo: last path component of the release url, or skip.
        url = release.get("url") or ""
        if not url:
            continue
        repo_name = url.rstrip("/").rsplit("/", 1)[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        if repo_name.endswith("-release"):
            repo_name = repo_name[: -len("-release")]
        names.add(repo_name)
    return names


def package_xml_map(cache_gz: bytes) -> dict:
    cache = yaml.safe_load(gzip.decompress(cache_gz))
    release_package_xmls = cache.get("release_package_xmls") or {}
    if not release_package_xmls:
        raise DistroError("rosdistro cache has no release_package_xmls")
    return release_package_xmls


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def direct_depends(package_xml: str) -> set:
    root = ET.fromstring(package_xml)
    deps: set = set()
    for child in list(root):
        if _local_name(child.tag) not in DEPEND_TAGS:
            continue
        name = (child.text or "").strip()
        if name:
            deps.add(name)
    return deps


def closure(seeds, xmls: dict, keep=None, skip=None) -> set:
    """Every package reachable from `seeds` through package.xml dependencies.

    `keep` limits the walk to names the distribution knows about; `skip` prunes
    packages the distribution policy leaves out, along with everything only they
    would have pulled in.
    """
    skip = skip or {}
    seen: set = set()
    stack = list(seeds)
    while stack:
        package = stack.pop()
        if package in seen or package in skip:
            continue
        seen.add(package)
        xml = xmls.get(package)
        if not xml:
            continue
        for dep in direct_depends(xml):
            if keep is None or dep in keep or dep in xmls:
                stack.append(dep)
    return seen
