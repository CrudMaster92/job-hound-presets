"""Pure feed lifecycle transitions, separate from personal matching/storage."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta

from .schema import EXPIRE_DAYS, parse_time, timestamp


def empty_state() -> dict:
    return {"version": 1, "jobs": {}, "sources": {}, "source_caches": {}, "last_generation": None}


def apply_results(state: dict, results: list[dict], *, generation: str, now: datetime) -> dict:
    """Merge once per generation. A partial or failed read never proves absence."""
    if state.get("last_generation") == generation:
        return copy.deepcopy(state)
    updated = copy.deepcopy(state)
    moment = timestamp(now)
    jobs = updated.setdefault("jobs", {})
    sources = updated.setdefault("sources", {})
    caches = updated.setdefault("source_caches", {})
    for result in results:
        source = dict(result["source"])
        monitor_id = source["id"]
        previous = sources.get(monitor_id, {})
        source["last_attempt_at"] = moment
        success = source["status"] in {"complete", "partial"}
        source["last_success_at"] = moment if success else previous.get("last_success_at")
        sources[monitor_id] = source
        if not success:
            continue
        if "detail_cache" in result:
            caches[monitor_id] = result["detail_cache"]
        seen = set()
        for incoming in result["jobs"]:
            identifier = incoming["id"]
            seen.add(identifier)
            prior = jobs.get(identifier)
            observations = copy.deepcopy(prior.get("observations", {})) if prior else {}
            observations[monitor_id] = {"last_seen_at": moment, "miss_count": 0}
            record = dict(incoming)
            record["first_seen_at"] = prior["job"]["first_seen_at"] if prior else moment
            record["last_seen_at"] = moment
            record["status"] = "active"
            # Preserve richer details if this cycle's bounded enrichment misses.
            if prior and not record.get("description"):
                record["description"] = prior["job"].get("description", "")
            record["monitor_ids"] = sorted(observations)
            if prior:
                record["collection_ids"] = sorted(set(record["collection_ids"]) | set(prior["job"]["collection_ids"]))
            jobs[identifier] = {"job": record, "observations": observations}
        if source["complete"]:
            for identifier, entry in jobs.items():
                observation = entry["observations"].get(monitor_id)
                if observation and identifier not in seen:
                    observation["miss_count"] += 1
    cutoff = now - timedelta(days=EXPIRE_DAYS)
    for entry in jobs.values():
        record = entry["job"]
        observations = entry["observations"].values()
        if observations and all(item["miss_count"] >= 2 for item in observations):
            record["status"] = "closed"
        elif parse_time(record["last_seen_at"]) <= cutoff:
            record["status"] = "expired"
        else:
            record["status"] = "active"
    retention_cutoff = now - timedelta(days=30)
    updated["jobs"] = {key: entry for key, entry in jobs.items()
                       if entry["job"]["status"] == "active" or parse_time(entry["job"]["last_seen_at"]) > retention_cutoff}
    updated["last_generation"] = generation
    return updated
