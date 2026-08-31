#!/usr/bin/env python3
"""One-way helper for converting a v1 embedded preset into reusable sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.preset.read_text(encoding="utf-8"))
    for item in manifest["companies"]:
        company_id = item["key"]
        website = f"https://{urlsplit(item['careers_url']).hostname}/"
        company = {
            "format": "jobhound-company", "schema_version": 1, "id": company_id,
            "name": item["name"], "legal_name": None, "aliases": [], "website_url": website,
            "logo_url": item.get("logo_url"),
            "facets": {"industries": ["technology"], "specialties": ["artificial-intelligence"],
                       "tags": ["AI", "Technology", "Global"]},
        }
        monitor = {
            "format": "jobhound-monitor", "schema_version": 1, "id": company_id,
            "company_id": company_id, "revision": 1, "label": f"{item['name']} careers",
            "careers_url": item["careers_url"],
            "compatibility": {"min_jobhound_version": "0.1.0", "recipe_schema_version": 1},
            "verification": {"status": "unverified", "checked_at": None, "job_count": None, "warnings": []},
            "recipe": item["recipe"],
        }
        base = ROOT / "companies" / company_id
        write(base / "company.json", company)
        write(base / "monitors" / f"{company_id}.json", monitor)
    collection = {
        "format": "jobhound-collection", "schema_version": 1, "id": manifest["id"], "revision": 1,
        "name": manifest["name"], "description": manifest["description"], "tags": manifest["tags"],
        "facets": {"collection_types": ["industry"], "industries": ["technology"],
                   "role_families": [], "locations": []},
        "suggested_criteria": {"cities": [], "title_terms": [], "keywords": []},
        "source": None, "companies": [{"company_id": item["key"]} for item in manifest["companies"]],
    }
    write(ROOT / "collections" / f"{manifest['id']}.json", collection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
