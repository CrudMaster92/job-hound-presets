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
MEMBERS_PER_PAGE = 100
SEARCH_COMPANIES_PER_PAGE = 250


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


def reference(path: str, value: dict, **fields) -> dict:
    return {**fields, "path": path, "sha256": digest(value)}


def pages(values: list, page_size: int) -> list[list]:
    return [values[index:index + page_size] for index in range(0, len(values), page_size)]


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
    monitor_references: dict[str, dict] = {}
    for monitor_id, monitor in sorted(monitors.items()):
        rel = f"monitors/{monitor_id}.json"
        write_json(api_root / rel, monitor)
        monitor_references[monitor_id] = reference(
            rel, monitor, id=monitor_id, revision=monitor["revision"],
            adapter=monitor["recipe"]["strategy"], careers_url=monitor["careers_url"],
            verification=monitor["verification"],
        )

    company_references: dict[str, dict] = {}
    for company_id, company in sorted(companies.items()):
        company_monitor_refs = [
            monitor_references[key] for key, value in sorted(monitors.items())
            if value["company_id"] == company_id
        ]
        artifact = {**company, "monitors": company_monitor_refs}
        rel = f"companies/{company_id}.json"
        write_json(api_root / rel, artifact)
        company_references[company_id] = reference(
            rel, artifact, id=company_id, name=company["name"],
            legal_name=company.get("legal_name"), aliases=company.get("aliases", []),
            facets=company.get("facets", {}), monitor_count=len(company_monitor_refs),
        )

    collection_entries: list[dict] = []
    company_collections: dict[str, list[str]] = {key: [] for key in companies}
    for collection in collections:
        members = []
        bundle_companies = []
        for member in collection["companies"]:
            company = companies[member["company_id"]]
            company_collections[company["id"]].append(collection["id"])
            selected_ids = member.get("monitor_ids") or [
                key for key, value in monitors.items() if value["company_id"] == company["id"]
            ]
            selected_monitors = [monitors[key] for key in selected_ids]
            members.append({
                **member, "name": company["name"], "legal_name": company.get("legal_name"),
                "aliases": company.get("aliases", []), "logo_url": company.get("logo_url"),
                "company_path": company_references[company["id"]]["path"],
                "company_sha256": company_references[company["id"]]["sha256"],
                "monitors": [monitor_references[key] for key in selected_ids],
            })
            for monitor in selected_monitors:
                bundle_companies.append({
                    "key": monitor["id"], "catalog_company_id": company["id"],
                    "catalog_monitor_id": monitor["id"], "catalog_revision": monitor["revision"],
                    "name": company["name"], "legal_name": company.get("legal_name"),
                    "careers_url": monitor["careers_url"], "logo_url": company.get("logo_url"),
                    "recipe": monitor["recipe"], "verification": monitor["verification"],
                })
        member_page_refs = []
        for page_number, member_page in enumerate(pages(members, MEMBERS_PER_PAGE), start=1):
            page_value = {
                "format": "jobhound-collection-members", "schema_version": 1,
                "collection_id": collection["id"], "page": page_number,
                "companies": member_page,
            }
            page_rel = f"collections/{collection['id']}/members-{page_number:04d}.json"
            write_json(api_root / page_rel, page_value)
            member_page_refs.append(reference(page_rel, page_value, page=page_number, count=len(member_page)))
        detail = {
            **{key: value for key, value in collection.items() if key != "companies"},
            "company_count": len(collection["companies"]), "monitor_count": len(bundle_companies),
            "member_pages": member_page_refs,
        }
        detail_rel = f"collections/{collection['id']}.json"
        write_json(api_root / detail_rel, detail)
        bundle = {
            "format": "jobhound-preset", "version": 2, "id": collection["id"],
            "revision": collection["revision"], "name": collection["name"],
            "description": collection["description"], "tags": collection["tags"],
            "facets": collection["facets"], "suggested_criteria": collection.get("suggested_criteria", {}),
            "source": collection.get("source"), "companies": bundle_companies,
        }
        bundle_rel = f"bundles/{collection['id']}.json"
        write_json(api_root / bundle_rel, bundle)
        collection_entries.append({
            "id": collection["id"], "revision": collection["revision"], "name": collection["name"],
            "description": collection["description"], "tags": collection["tags"],
            "facets": collection["facets"], "suggested_criteria": collection.get("suggested_criteria", {}),
            "source": collection.get("source"), "company_count": len(collection["companies"]),
            "monitor_count": len(bundle_companies), "path": detail_rel,
            "sha256": digest(detail), "bundle_path": bundle_rel, "bundle_sha256": digest(bundle),
        })

    search_values = []
    for company_id, company in sorted(companies.items()):
        search_values.append({
            "id": company_id, "name": company["name"], "legal_name": company.get("legal_name"),
            "aliases": company.get("aliases", []), "facets": company.get("facets", {}),
            "collection_ids": sorted(company_collections[company_id]),
            "path": company_references[company_id]["path"],
            "sha256": company_references[company_id]["sha256"],
        })
    search_page_refs = []
    for page_number, search_page in enumerate(pages(search_values, SEARCH_COMPANIES_PER_PAGE), start=1):
        page_value = {
            "format": "jobhound-company-search", "schema_version": 1,
            "page": page_number, "companies": search_page,
        }
        page_rel = f"search/companies-{page_number:04d}.json"
        write_json(api_root / page_rel, page_value)
        search_page_refs.append(reference(page_rel, page_value, page=page_number, count=len(search_page)))

    catalog = {
        "format": "jobhound-preset-catalog", "catalog_version": 3,
        "generated_at": generated_at, "source_commit": source_commit,
        "company_schema_version": 1, "monitor_schema_version": 1,
        "collection_schema_version": 1, "preset_versions": [1, 2],
        "company_count": len(companies), "monitor_count": len(monitors),
        "search_pages": search_page_refs, "collections": collection_entries,
    }
    write_json(api_root / "catalog.json", catalog)
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
    print(
        f"Built {catalog['company_count']} companies, {catalog['monitor_count']} monitors, "
        f"and {len(catalog['collections'])} collections."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Catalog build failed: {exc}")
        raise SystemExit(1)
