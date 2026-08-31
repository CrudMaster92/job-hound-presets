#!/usr/bin/env python3
"""Validate the Job Hound preset catalog and every referenced manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:  # Full schema validation runs in CI after requirements are installed.
    Draft202012Validator = None
    FormatChecker = None

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "jobhound-preset-v1.schema.json"
CATALOG_PATH = ROOT / "catalog.json"
FORBIDDEN_HEADERS = {"authorization", "cookie", "proxy-authorization"}


def canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, parsed.query, ""))


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: {exc}") from exc


def validate_manifest(path: Path, validator) -> dict:
    manifest = load_json(path)
    if validator is not None:
        errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.absolute_path))
        if errors:
            details = "; ".join(f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}" for error in errors)
            raise ValueError(f"{path.relative_to(ROOT)}: {details}")
    required = {"format", "version", "id", "name", "description", "tags", "companies"}
    if set(manifest) != required or manifest.get("format") != "jobhound-preset" or manifest.get("version") != 1:
        raise ValueError(f"{path.relative_to(ROOT)}: invalid top-level preset contract")
    if not isinstance(manifest.get("companies"), list) or not manifest["companies"]:
        raise ValueError(f"{path.relative_to(ROOT)}: companies must be a non-empty array")

    keys: set[str] = set()
    urls: set[str] = set()
    for company in manifest["companies"]:
        key = company["key"]
        company_url = canonical_url(company["careers_url"])
        recipe = company["recipe"]
        request_host = (urlsplit(recipe["request"]["url"]).hostname or "").casefold()
        allowed_hosts = {host.casefold().rstrip(".") for host in recipe["allowed_hosts"]}
        headers = {name.casefold() for name in recipe["request"]["headers"]}
        if key in keys:
            raise ValueError(f"{path.relative_to(ROOT)}: duplicate company key {key!r}")
        if company_url in urls:
            raise ValueError(f"{path.relative_to(ROOT)}: duplicate careers URL {company_url!r}")
        if company_url != canonical_url(recipe["careers_url"]):
            raise ValueError(f"{path.relative_to(ROOT)}: {key} recipe careers_url does not match company")
        if request_host not in allowed_hosts:
            raise ValueError(f"{path.relative_to(ROOT)}: {key} request host is not in allowed_hosts")
        if headers & FORBIDDEN_HEADERS:
            raise ValueError(f"{path.relative_to(ROOT)}: {key} contains a credential-bearing header")
        keys.add(key)
        urls.add(company_url)
    return manifest


def main() -> int:
    schema = load_json(SCHEMA_PATH)
    if Draft202012Validator is not None:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    else:
        validator = None
    catalog = load_json(CATALOG_PATH)
    if catalog.get("format") != "jobhound-preset-catalog" or catalog.get("catalog_version") != 1:
        raise ValueError("catalog.json: unsupported catalog format or version")
    if catalog.get("preset_format") != "jobhound-preset" or catalog.get("preset_version") != 1:
        raise ValueError("catalog.json: unsupported preset contract")

    seen: set[str] = set()
    referenced: set[Path] = set()
    for entry in catalog.get("presets", []):
        preset_id = entry.get("id")
        if not preset_id or preset_id in seen:
            raise ValueError(f"catalog.json: missing or duplicate preset id {preset_id!r}")
        path = (ROOT / entry["path"]).resolve()
        if ROOT.resolve() not in path.parents or path.suffix != ".json":
            raise ValueError(f"catalog.json: unsafe preset path {entry['path']!r}")
        manifest = validate_manifest(path, validator)
        expected = {key: manifest[key] for key in ("id", "name", "description", "tags")}
        actual = {key: entry.get(key) for key in expected}
        if actual != expected or entry.get("company_count") != len(manifest["companies"]):
            raise ValueError(f"catalog.json: metadata drift for {preset_id!r}")
        if path.stem != preset_id or manifest["id"] != preset_id:
            raise ValueError(f"catalog.json: id, filename, and manifest id must match for {preset_id!r}")
        seen.add(preset_id)
        referenced.add(path)

    disk_presets = set((ROOT / "presets").glob("*.json"))
    if disk_presets != referenced:
        missing = sorted(str(path.relative_to(ROOT)) for path in disk_presets ^ referenced)
        raise ValueError(f"catalog.json: unlisted or missing preset files: {', '.join(missing)}")
    mode = "schema + contract" if validator is not None else "contract (install requirements-dev.txt for schema checks)"
    print(f"Validated {len(referenced)} preset(s) against Job Hound preset version 1: {mode}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
