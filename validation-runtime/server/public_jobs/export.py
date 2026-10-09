"""Deterministically export the public runtime; the app remains authored source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .schema import digest, json_bytes

PUBLIC_MODULES = ("__init__", "schema", "lifecycle", "catalog", "collector", "publish", "__main__", "export", "admission")
SCRAPER_MODULES = ("__init__", "adapters", "ai_contract", "detection", "detail_cache", "detail_extraction", "facade", "http", "models", "normalize", "progress", "runtime")
CONTRIBUTION_MODULES = ("__init__", "contracts", "github", "validation", "cli", "admission")
SCHEMA_NAMES = ("jobhound-company-v1", "jobhound-monitor-v1", "jobhound-collection-v1", "jobhound-preset-v1")
EXPORT_PATHS = [*[f"server/contributions/{name}.py" for name in CONTRIBUTION_MODULES],
                *[f"server/contributions/schemas/{name}.schema.json" for name in SCHEMA_NAMES],
                "server/__init__.py", "server/external_http.py", *[f"server/public_jobs/{name}.py" for name in PUBLIC_MODULES],
                *[f"server/scrapers/{name}.py" for name in SCRAPER_MODULES], "tests/test_public_jobs_collector.py", "tests/test_public_description_extraction.py", "tests/test_scraper_detail_cache.py", "tests/test_contribution_admission.py"]


def export_runtime(source: Path, destination: Path, *, check: bool = False) -> dict:
    manifest_path = destination / "runtime-manifest.json"
    if check:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "jobhound-public-runtime" or manifest.get("version") != 1 or {entry["path"] for entry in manifest["files"]} != set(EXPORT_PATHS):
            raise ValueError("Generated runtime manifest differs from the canonical export allowlist")
        if digest(json_bytes(manifest["files"])) != manifest["runtime_revision"]:
            raise ValueError("Generated runtime revision hash is invalid")
        for entry in manifest["files"]:
            target = (destination / entry["path"]).resolve()
            if not target.is_relative_to(destination.resolve()) or digest(target.read_bytes()) != entry["sha256"]:
                raise ValueError(f"Generated runtime was edited: {entry['path']}")
            original = source / entry["path"]
            if source.resolve() != destination.resolve() and digest(original.read_bytes().replace(b"\r\n", b"\n")) != entry["sha256"]:
                raise ValueError(f"Runtime needs re-export: {entry['path']}")
        return manifest
    entries = []
    for relative in EXPORT_PATHS:
        content = (source / relative).read_bytes().replace(b"\r\n", b"\n")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        entries.append({"path": relative, "sha256": digest(content)})
    manifest = {"format": "jobhound-public-runtime", "version": 1,
                "source": "Canonical JobHound application", "files": entries}
    manifest["runtime_revision"] = digest(json_bytes(entries))
    manifest_path.write_bytes(json_bytes(manifest))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = export_runtime(args.source, args.destination, check=args.check)
    print(json.dumps({"files": len(manifest["files"]), "runtime_revision": manifest["runtime_revision"], "checked": args.check}))


if __name__ == "__main__":
    main()
