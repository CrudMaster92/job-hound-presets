#!/usr/bin/env python3
"""Validate authored catalog sources and build immutable public artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ROOT / "companies"
COLLECTIONS = ROOT / "collections"
SCHEMAS = ROOT / "schemas"
DIST = ROOT / "dist"
SITE = ROOT / "site"
FORBIDDEN_HEADERS = {"authorization", "cookie", "proxy-authorization"}


def load(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)}: expected a JSON object")
    return value


def validate(path: Path, schema_name: str) -> dict:
    value = load(path)
    schema = load(SCHEMAS / schema_name)
    if schema_name == "jobhound-monitor-v1.schema.json":
        legacy = load(SCHEMAS / "jobhound-preset-v1.schema.json")
        schema["properties"]["recipe"] = legacy["$defs"]["recipe"]
        schema["$defs"] = legacy["$defs"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '$'}: {error.message}" for error in errors
        )
        raise ValueError(f"{path.relative_to(ROOT)}: {details}")
    return value


def canonical_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: dict) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def monitor_contract(path: Path, monitor: dict, company_id: str) -> None:
    if monitor["company_id"] != company_id:
        raise ValueError(f"{path.relative_to(ROOT)}: company_id does not match its directory")
    recipe = monitor["recipe"]
    if recipe["careers_url"].rstrip("/") != monitor["careers_url"].rstrip("/"):
        raise ValueError(f"{path.relative_to(ROOT)}: recipe careers_url must match monitor careers_url")
    request_host = (urlsplit(recipe["request"]["url"]).hostname or "").casefold().rstrip(".")
    allowed = {host.casefold().rstrip(".") for host in recipe["allowed_hosts"]}
    if request_host not in allowed:
        raise ValueError(f"{path.relative_to(ROOT)}: request host is not in allowed_hosts")
    headers = {name.casefold() for name in recipe["request"].get("headers", {})}
    if headers & FORBIDDEN_HEADERS:
        raise ValueError(f"{path.relative_to(ROOT)}: credential-bearing headers are forbidden")


def build(*, output: Path, source_commit: str = "local") -> dict:
    companies: dict[str, dict] = {}
    monitors: dict[str, dict] = {}
    for path in sorted(COMPANIES.glob("*/company.json")):
        company = validate(path, "jobhound-company-v1.schema.json")
        if path.parent.name != company["id"] or company["id"] in companies:
            raise ValueError(f"{path.relative_to(ROOT)}: company ID must match its directory and be unique")
        companies[company["id"]] = company
        for monitor_path in sorted((path.parent / "monitors").glob("*.json")):
            monitor = validate(monitor_path, "jobhound-monitor-v1.schema.json")
            monitor_contract(monitor_path, monitor, company["id"])
            if monitor_path.stem != monitor["id"] or monitor["id"] in monitors:
                raise ValueError(f"{monitor_path.relative_to(ROOT)}: monitor ID must match its filename and be unique")
            monitors[monitor["id"]] = monitor

    collections: list[dict] = []
    for path in sorted(COLLECTIONS.glob("*.json")):
        collection = validate(path, "jobhound-collection-v1.schema.json")
        if path.stem != collection["id"]:
            raise ValueError(f"{path.relative_to(ROOT)}: collection ID must match its filename")
        seen_companies: set[str] = set()
        for member in collection["companies"]:
            company_id = member["company_id"]
            if company_id not in companies or company_id in seen_companies:
                raise ValueError(f"{path.relative_to(ROOT)}: unknown or duplicate company {company_id!r}")
            seen_companies.add(company_id)
            selected = member.get("monitor_ids") or [
                monitor_id for monitor_id, monitor in monitors.items() if monitor["company_id"] == company_id
            ]
            if not selected:
                raise ValueError(f"{path.relative_to(ROOT)}: {company_id!r} has no installable monitor")
            for monitor_id in selected:
                if monitor_id not in monitors or monitors[monitor_id]["company_id"] != company_id:
                    raise ValueError(f"{path.relative_to(ROOT)}: invalid monitor {monitor_id!r} for {company_id!r}")
        collections.append(collection)

    if output.exists():
        shutil.rmtree(output)
    api_root = output / "api" / "v1"
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    company_entries = []
    for company_id, company in sorted(companies.items()):
        company_monitors = [value for value in monitors.values() if value["company_id"] == company_id]
        artifact = {**company, "monitors": company_monitors}
        rel = f"companies/{company_id}.json"
        write_json(api_root / rel, artifact)
        company_entries.append({
            "id": company_id, "name": company["name"], "legal_name": company.get("legal_name"),
            "aliases": company.get("aliases", []), "facets": company.get("facets", {}),
            "monitor_count": len(company_monitors), "path": rel, "sha256": digest(artifact),
        })

    collection_entries = []
    for collection in collections:
        expanded = []
        bundle_companies = []
        for member in collection["companies"]:
            company = companies[member["company_id"]]
            selected_ids = member.get("monitor_ids") or [
                key for key, value in monitors.items() if value["company_id"] == company["id"]
            ]
            selected_monitors = [monitors[key] for key in selected_ids]
            expanded.append({**member, "name": company["name"], "legal_name": company.get("legal_name"),
                             "aliases": company.get("aliases", []), "monitor_count": len(selected_monitors)})
            for monitor in selected_monitors:
                bundle_companies.append({
                    "key": monitor["id"], "catalog_company_id": company["id"],
                    "catalog_monitor_id": monitor["id"], "catalog_revision": monitor["revision"],
                    "name": company["name"], "legal_name": company.get("legal_name"),
                    "careers_url": monitor["careers_url"], "logo_url": company.get("logo_url"),
                    "recipe": monitor["recipe"], "verification": monitor["verification"],
                })
        detail = {**collection, "companies": expanded}
        detail_rel = f"collections/{collection['id']}.json"
        write_json(api_root / detail_rel, detail)
        bundle = {
            "format": "jobhound-preset", "version": 2, "id": collection["id"],
            "revision": collection["revision"], "name": collection["name"],
            "description": collection["description"], "tags": collection["tags"],
            "facets": collection["facets"], "suggested_criteria": collection.get("suggested_criteria", {}),
            "source": collection.get("source"), "companies": bundle_companies,
        }
        bundle_rel = f"presets/{collection['id']}.json"
        write_json(api_root / bundle_rel, bundle)
        collection_entries.append({
            "id": collection["id"], "revision": collection["revision"], "name": collection["name"],
            "description": collection["description"], "tags": collection["tags"],
            "facets": collection["facets"], "suggested_criteria": collection.get("suggested_criteria", {}),
            "source": collection.get("source"), "company_count": len(collection["companies"]),
            "monitor_count": len(bundle_companies), "path": detail_rel, "download_path": bundle_rel,
            "sha256": digest(bundle), "companies": [
                {"key": item["key"], "catalog_company_id": item["catalog_company_id"],
                 "catalog_monitor_id": item["catalog_monitor_id"], "catalog_revision": item["catalog_revision"],
                 "name": item["name"], "legal_name": item.get("legal_name"),
                 "careers_url": item["careers_url"], "logo_url": item.get("logo_url"),
                 "adapter": item["recipe"]["strategy"], "verification": item["verification"]}
                for item in bundle_companies
            ],
        })

    catalog = {
        "format": "jobhound-preset-catalog", "catalog_version": 2,
        "generated_at": generated_at, "source_commit": source_commit,
        "company_schema_version": 1, "monitor_schema_version": 1,
        "collection_schema_version": 1, "preset_versions": [1, 2],
        "companies": company_entries, "collections": collection_entries,
    }
    write_json(api_root / "catalog.json", catalog)
    write_json(output / "catalog.json", catalog)
    for path in SITE.iterdir():
        if path.is_file():
            shutil.copy2(path, output / path.name)
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DIST)
    parser.add_argument("--source-commit", default="local")
    args = parser.parse_args()
    catalog = build(output=args.output.resolve(), source_commit=args.source_commit)
    print(f"Built {len(catalog['companies'])} companies and {len(catalog['collections'])} collections.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Catalog build failed: {exc}")
        raise SystemExit(1)
