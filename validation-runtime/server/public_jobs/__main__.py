"""CLI for pinned public builds; never reads personal JobHound state."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .catalog import build_lock, load_monitors, read_json
from .collector import collect
from .lifecycle import apply_results, empty_state
from .publish import publish, retain_generations
from .schema import json_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    lock_parser = commands.add_parser("lock", help="Explicitly select and pin current verified non-browser catalog monitors")
    lock_parser.add_argument("--catalog", type=Path, required=True)
    lock_parser.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build", help="Collect selected pins and atomically publish a static feed")
    build.add_argument("--catalog", type=Path, required=True)
    build.add_argument("--lock", type=Path, required=True)
    build.add_argument("--state", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--generation")
    build.add_argument("--monitor", action="append", default=[], help="Restrict a local smoke run; never use to update production state")
    build.add_argument("--minutes", type=int, default=40)
    args = parser.parse_args()
    if args.command == "lock":
        lock = build_lock(args.catalog.resolve())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(json_bytes(lock))
        print(json.dumps({"catalog_commit": lock["catalog_commit"], "eligible": len(lock["monitors"]), "excluded": len(lock["excluded"])}))
        return
    if args.minutes < 1 or args.minutes > 45:
        parser.error("--minutes must be between 1 and 45")
    lock = read_json(args.lock)
    monitors = load_monitors(args.catalog.resolve(), lock)
    state = read_json(args.state) if args.state.exists() else empty_state()
    if args.monitor:
        if args.state.exists():
            parser.error("Restricted smoke runs require a new isolated state file")
        wanted = set(args.monitor)
        monitors = [(entry, recipe) for entry, recipe in monitors if entry["id"] in wanted]
        if len(monitors) != len(wanted):
            parser.error("--monitor must name eligible pinned IDs")
    now = datetime.now(timezone.utc)
    # Oldest actual attempt first. Sources never reached before the shared
    # deadline retain their place for the next run rather than starving.
    monitors.sort(key=lambda item: (state.get("sources", {}).get(item[0]["id"], {}).get("last_attempt_at") or "", item[0]["id"]))
    generation = args.generation or now.strftime("%Y%m%dT%H%M%S")
    results = collect(monitors, now=now, minutes=args.minutes,
                      source_caches=state.get("source_caches", {}),
                      progress=lambda source: print(json.dumps({key: source[key] for key in ("id", "status", "job_count")}), flush=True))
    if not any(result["source"]["status"] in {"complete", "partial"} for result in results):
        raise SystemExit("No sources succeeded; previous state and published generation preserved")
    updated = apply_results(state, results, generation=generation, now=now)
    updated["catalog_lock"] = lock
    for source in lock["excluded"]:
        updated["sources"][source["id"]] = {key: source[key] for key in ("id", "company_id", "company_name", "revision")}
        updated["sources"][source["id"]].update(status="excluded", complete=False, job_count=0,
                                                       last_attempt_at=None, last_success_at=None, warnings=[source["reason"]])
    manifest = publish(updated, lock, args.output, generation=generation, now=now)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    pending = args.state.with_suffix(".pending.json")
    pending.write_bytes(json_bytes(updated))
    os.replace(pending, args.state)
    retain_generations(args.output)
    print(json.dumps({"generation": generation, "total_jobs": manifest["total_jobs"], "active_jobs": manifest["active_jobs"],
                      "successful_sources": sum(result["source"]["status"] in {"complete", "partial"} for result in results)}))


if __name__ == "__main__":
    main()
