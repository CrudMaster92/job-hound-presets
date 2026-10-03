"""Advance individually pinned sources after Jo merges trusted contributions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..contributions.admission import approved_receipts
from ..contributions.contracts import content_hash
from .catalog import build_lock, source_commit
from .schema import json_bytes, digest


def advance_lock(root: Path, previous: dict, approved: dict, pending=None) -> dict:
    """Never replace an existing pin using author verification or an absent receipt."""
    current = build_lock(root)
    commit = source_commit(root)
    pins = {item["id"]: {**item, "catalog_commit": item.get("catalog_commit", previous["catalog_commit"])}
            for item in previous["monitors"]}
    # Current author status is immaterial. Admission is an exact data hash and
    # trusted live receipt for this runtime, plus Jo's actual merge.
    candidates = {item["id"]: item for item in [*current["monitors"], *current["excluded"]]}
    for monitor_id, authorization in approved.items():
        if monitor_id not in candidates:
            continue
        entry = candidates[monitor_id]
        path = root / entry["path"]
        document = json.loads(path.read_text(encoding="utf-8"))
        if content_hash(document) != authorization["receipt"]["artifact_hash"]:
            raise ValueError("Approved source changed during admission")
        pins[monitor_id] = {key: value for key, value in entry.items() if key != "reason"}
        pins[monitor_id].update(catalog_commit=commit, validation=authorization["receipt"], artifact_hash=content_hash(document))
    excluded = [item for item in current["excluded"] if item["id"] not in pins]
    return {"version": 2, "repository": previous["repository"], "catalog_commit": commit,
            "collections": current["collections"], "monitors": sorted(pins.values(), key=lambda x: x["id"]),
            "excluded": excluded, "pending": pending or {}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--bootstrap-lock", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    runtime = json.loads(args.runtime_manifest.read_text())["runtime_revision"]
    state = json.loads(args.state.read_text()) if args.state.exists() else {}
    previous = state.get("catalog_lock") or json.loads(args.bootstrap_lock.read_text())
    approved, pending = approved_receipts(args.catalog, args.receipts, runtime)
    lock = advance_lock(args.catalog, previous, approved, pending)
    args.output.write_bytes(json_bytes(lock))
    print(json.dumps({"admitted": len(approved), "pins": len(lock["monitors"]), "pending": len(pending)}))


if __name__ == "__main__":
    main()
