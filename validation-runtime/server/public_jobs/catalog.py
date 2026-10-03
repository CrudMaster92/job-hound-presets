"""Explicitly pin eligible catalog sources; never silently activate revisions."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from ..scrapers.models import ScraperRecipe
from .schema import digest, public_url


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def checked_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("Catalog path escapes its root")
    return path


def source_commit(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def build_lock(root: Path) -> dict:
    commit = source_commit(root)
    collections = []
    memberships: dict[str, list[tuple[str, list[str] | None]]] = {}
    for path in sorted((root / "collections").glob("*.json")):
        item = read_json(path)
        collections.append({"id": item["id"], "name": item["name"]})
        for member in item["companies"]:
            memberships.setdefault(member["company_id"], []).append((item["id"], member.get("monitor_ids")))
    monitors, excluded = [], []
    for path in sorted((root / "companies").glob("*/monitors/*.json")):
        item = read_json(path)
        company = read_json(path.parent.parent / "company.json")
        entry = {
            "id": item["id"], "company_id": item["company_id"], "company_name": company["name"],
            "revision": item["revision"], "path": path.relative_to(root).as_posix(),
            "sha256": digest(path.read_bytes().replace(b"\r\n", b"\n")),
            "collection_ids": sorted(collection for collection, ids in memberships.get(item["company_id"], [])
                                     if ids is None or item["id"] in ids),
        }
        reason = None
        if item.get("verification", {}).get("status") != "verified":
            reason = "Catalog verification is not verified"
        elif item["recipe"].get("strategy") == "playwright":
            reason = "Browser sources are excluded from the initial public feed"
        else:
            try:
                recipe = ScraperRecipe.model_validate(item["recipe"])
                public_url(recipe.careers_url)
                public_url(recipe.request.url)
                if recipe.source_filter and any(p.phase == "detail" for p in recipe.source_filter.predicates):
                    reason = "Detail ownership predicates require a separately reviewed public detail budget"
            except ValueError:
                reason = "Recipe is incompatible with the pinned runtime"
        if reason:
            excluded.append({**entry, "reason": reason})
        else:
            monitors.append(entry)
    return {"version": 1, "repository": "CrudMaster92/job-hound-presets", "catalog_commit": commit,
            "collections": collections, "monitors": monitors, "excluded": excluded}


def load_monitors(root: Path, lock: dict) -> list[tuple[dict, ScraperRecipe]]:
    if lock.get("repository") != "CrudMaster92/job-hound-presets" or not re.fullmatch(r"[a-f0-9]{40}", lock.get("catalog_commit", "")):
        raise ValueError("Invalid pinned catalog repository or commit")
    if source_commit(root) != lock["catalog_commit"]:
        raise ValueError("Catalog checkout does not match the reviewed lock")
    selected = []
    for entry in lock["monitors"]:
        path = checked_path(root, entry["path"])
        if lock.get("version") == 2:
            commit = entry["catalog_commit"]
            if not re.fullmatch(r"[a-f0-9]{40}", commit):
                raise ValueError("Invalid individual source pin")
            # All reachable history is fetched by the collector. No candidate
            # code is checked out or executed; only exact normal JSON blobs.
            from ..contributions.cli import read_blob
            document = read_blob(root, commit, entry["path"])
            raw = subprocess.check_output(["git", "-C", str(root), "show", f"{commit}:{entry['path']}"])
        else:
            raw = path.read_bytes()
            document = read_json(path)
        if digest(raw.replace(b"\r\n", b"\n")) != entry["sha256"]:
            raise ValueError(f"Pinned recipe content changed: {entry['id']}")
        if (document["id"], document["company_id"], document["revision"]) != (entry["id"], entry["company_id"], entry["revision"]):
            raise ValueError("Pinned monitor identity changed")
        if entry.get("validation"):
            from ..contributions.validation import effective_verification
            effective_verification(document, entry["validation"])
        elif document["verification"]["status"] != "verified":
            raise ValueError("Only reviewed verified monitors can be collected")
        recipe = ScraperRecipe.model_validate(document["recipe"])
        if recipe.strategy.value == "playwright":
            raise ValueError("Browser sources cannot run in the public collector")
        public_url(recipe.request.url)
        public_url(recipe.careers_url)
        selected.append((entry, recipe))
    return selected
