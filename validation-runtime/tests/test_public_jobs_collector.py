"""Public collection, lifecycle, privacy and atomic publication contracts."""
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest

from server.public_jobs.collector import HostLimiter, collect_monitor, normalize_job
from server.public_jobs.lifecycle import apply_results, empty_state
from server.public_jobs.publish import publish, validate_publication
from server.public_jobs.schema import job_id, json_bytes, timestamp
from server.scrapers.models import JobRecord, ScrapeResult, ScraperRecipe

NOW = datetime(2026, 9, 26, 12, tzinfo=timezone.utc)
MONITOR = {"id": "acme", "company_id": "acme", "company_name": "Acme", "revision": 1, "collection_ids": ["technology"]}
RECIPE = {"version": 1, "company": "Acme", "careers_url": "https://acme.example/careers", "strategy": "generic_json",
          "allowed_hosts": ["acme.example"], "request": {"url": "https://acme.example/jobs"},
          "mapping": {"items": "jobs", "title": "title", "url": "url", "source_id": "id"}}


def job(url="https://acme.example/jobs/1", **changes):
    values = dict(company="Acme", source_id="1", title="Engineer", location="Toronto", canonical_url=url,
                  source_url=url, source="generic_json", description="<p>A role</p><script>bad()</script>")
    values.update(changes)
    return normalize_job(JobRecord(**values), MONITOR, NOW)


def result(jobs=None, *, complete=True, status=None, monitor="acme"):
    return {"source": {**MONITOR, "id": monitor, "status": status or ("complete" if complete else "partial"),
                       "complete": complete, "job_count": len(jobs or []), "warnings": []}, "jobs": jobs or []}


def merge(state, results, n, days=0):
    return apply_results(state, results, generation=f"run-{n}", now=NOW + timedelta(days=days))


def clean_result(value):
    value["source"].pop("collection_ids", None)
    return value


def test_two_complete_misses_partial_failure_and_retry_are_safe():
    record = job()
    state = merge(empty_state(), [result([record])], 1)
    state = merge(state, [result()], 2)
    assert state["jobs"][record["id"]]["job"]["status"] == "active"
    state = merge(state, [result([], complete=False), result([], complete=False, status="failed")], 3)
    assert state["jobs"][record["id"]]["observations"]["acme"]["miss_count"] == 1
    assert merge(state, [result()], 3) == state
    state = merge(state, [result()], 4)
    assert state["jobs"][record["id"]]["job"]["status"] == "closed"
    state = merge(state, [result([record])], 5, days=1)
    assert state["jobs"][record["id"]]["job"]["status"] == "active"
    assert state["jobs"][record["id"]]["job"]["first_seen_at"] == timestamp(NOW)


def test_partial_and_failed_sources_expire_without_claiming_closed():
    record = job()
    state = merge(empty_state(), [result([record], complete=False)], 1)
    state = merge(state, [result([], complete=False)], 2, days=3)
    state = merge(state, [result([], complete=False, status="failed")], 3, days=8)
    assert state["jobs"][record["id"]]["job"]["status"] == "expired"
    assert state["jobs"][record["id"]]["job"]["last_seen_at"] == timestamp(NOW)
    assert state["sources"]["acme"]["last_success_at"] == timestamp(NOW + timedelta(days=3))


def test_overlapping_monitors_need_all_observations_closed():
    record = job()
    state = merge(empty_state(), [result([record]), result([record], monitor="acme-other")], 1)
    for run in (2, 3):
        state = merge(state, [result(), result([record], monitor="acme-other")], run)
    assert len(state["jobs"]) == 1
    assert state["jobs"][record["id"]]["job"]["status"] == "active"
    assert state["jobs"][record["id"]]["job"]["monitor_ids"] == ["acme", "acme-other"]


def test_identity_and_normalization_only_publish_allowlisted_public_fields():
    record = job()
    assert "bad()" not in record["description"] and "<" not in record["description"]
    assert job_id("acme", record["source_url"] + "#fragment") == record["id"]
    assert job_id("other", record["source_url"]) != record["id"]
    assert not {"criteria", "resume", "notes", "headers", "recipe"} & record.keys()
    from server.public_jobs.schema import public_url
    with pytest.raises(ValueError):
        public_url("https://user:secret@acme.example/jobs/1")


def test_collector_uses_shared_runtime_and_rejects_invalid_complete_results():
    import time
    received = {}
    def runner(recipe, *, client, detail_cache):
        received.update(limit=recipe.metadata["detail_fetch_limit"], dns=client._jobhound_resolve_dns)
        return ScrapeResult(strategy="generic_json", complete=False, jobs=[JobRecord(company="Acme", source_id="1",
            title="Engineer", canonical_url="https://acme.example/1", source_url="https://acme.example/1", source="generic_json")])
    value = collect_monitor(MONITOR, ScraperRecipe.model_validate(RECIPE), now=NOW, limiter=HostLimiter(),
                            deadline=time.monotonic() + 10, runner=runner)
    assert value["source"]["status"] == "partial" and len(value["jobs"]) == 1
    assert received == {"limit": 20, "dns": True}


def test_publisher_validates_before_pointer_switch_and_has_hashed_lazy_details(tmp_path):
    state = merge(empty_state(), [clean_result(result([job()]))], 1)
    lock = {"catalog_commit": "a" * 40, "collections": [{"id": "technology", "name": "Technology"}]}
    manifest = publish(state, lock, tmp_path, generation="20260926-1", now=NOW)
    api = tmp_path / "api/v1"
    validate_publication(api, manifest)
    search = json.loads((api / manifest["search_pages"][0]["path"]).read_text())
    assert "description" not in search["jobs"][0]
    assert "salary_min" not in search["jobs"][0]
    details = json.loads((api / manifest["detail_pages"][0]["path"]).read_text())
    assert details["jobs"][0]["salary_min"] is None
    assert search["jobs"][0]["detail_ref"]["sha256"] == manifest["detail_pages"][0]["sha256"]
    before = (api / "manifest.json").read_bytes()
    state["jobs"][job()["id"]]["job"]["private_data"] = "must never leak"
    with pytest.raises(ValueError):
        publish(state, lock, tmp_path, generation="20260926-2", now=NOW)
    assert (api / "manifest.json").read_bytes() == before
    (api / manifest["search_pages"][0]["path"]).write_text("tampered")
    with pytest.raises(ValueError, match="hash"):
        validate_publication(api, manifest)


def test_catalog_requires_exact_commit_and_recipe_hash(tmp_path, monkeypatch):
    from server.public_jobs import catalog
    monitor = {"id": "acme", "company_id": "acme", "revision": 1,
               "verification": {"status": "verified"}, "recipe": RECIPE}
    path = tmp_path / "recipe.json"
    path.write_bytes(json_bytes(monitor))
    from server.public_jobs.schema import digest
    lock = {"repository": "CrudMaster92/job-hound-presets", "catalog_commit": "a" * 40,
            "monitors": [{**MONITOR, "path": "recipe.json", "sha256": digest(path.read_bytes())}]}
    monkeypatch.setattr(catalog, "source_commit", lambda root: "b" * 40)
    with pytest.raises(ValueError, match="checkout"):
        catalog.load_monitors(tmp_path, lock)
    monkeypatch.setattr(catalog, "source_commit", lambda root: "a" * 40)
    assert len(catalog.load_monitors(tmp_path, lock)) == 1
    path.write_text("{}")
    with pytest.raises(ValueError, match="content"):
        catalog.load_monitors(tmp_path, lock)


def test_detail_cache_advances_bounded_batches_and_only_refetches_changed_listings():
    from server.scrapers.detection import build_recipe
    from server.scrapers.runtime import run_scraper
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    recipe.metadata["detail_fetch_limit"] = 1
    postings = [{"id": name, "name": name, "ref": f"https://jobs.smartrecruiters.com/Acme/{name}"} for name in ("one", "two")]
    requests = []
    def handler(request):
        if request.url.path.endswith("/postings"):
            return httpx.Response(200, json={"totalFound": 2, "content": postings})
        requests.append(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, json={"jobAd": {"sections": {"jobDescription": {"text": "Role details"}}}})
    cache = {}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run_scraper(recipe, client=client, detail_cache=cache)
        assert requests == ["one"]
        run_scraper(recipe, client=client, detail_cache=cache)
        assert requests == ["one", "two"]
        third = run_scraper(recipe, client=client, detail_cache=cache)
        assert requests == ["one", "two"] and all(job.description for job in third.jobs)
        postings[0]["name"] = "Changed role"
        run_scraper(recipe, client=client, detail_cache=cache)
        assert requests == ["one", "two", "one"]


def test_retention_removes_unseen_public_records_after_thirty_days():
    record = job()
    state = merge(empty_state(), [result([record])], 1)
    state = merge(state, [result([], complete=False)], 2, days=31)
    assert state["jobs"] == {}


def test_details_split_by_bytes_before_the_count_limit(tmp_path):
    records = [job(f"https://acme.example/jobs/{index}", source_id=str(index), description="x" * 100_000) for index in range(100)]
    state = merge(empty_state(), [clean_result(result(records))], 1)
    lock = {"catalog_commit": "a" * 40, "collections": []}
    manifest = publish(state, lock, tmp_path, generation="large", now=NOW)
    assert len(manifest["detail_pages"]) == 2
    assert all((tmp_path / 'api/v1' / ref['path']).stat().st_size <= 7_000_000 for ref in manifest['detail_pages'])


def test_salary_inference_does_not_turn_million_dollar_sales_quotas_into_pay():
    from server.scrapers.normalize import infer_salary
    assert infer_salary("Track record closing $2M+ annual quotas. Lunch stipend $75.") == (None, None, None)
    assert infer_salary("Managed $5M annual revenue. Salary: USD $120,000 to $150,000 per year.")[:2] == (120000, 150000)


def test_runtime_export_is_portable_between_windows_and_linux(tmp_path, monkeypatch):
    import server.public_jobs.export as exporter
    source, destination = tmp_path / "source", tmp_path / "export"
    source.mkdir()
    (source / "module.py").write_bytes(b"value = 1\r\n")
    monkeypatch.setattr(exporter, "EXPORT_PATHS", ["module.py"])
    exporter.export_runtime(source, destination)
    assert (destination / "module.py").read_bytes() == b"value = 1\n"
    exporter.export_runtime(source, destination, check=True)
    exporter.export_runtime(destination, destination, check=True)

def test_publication_adapts_search_text_without_losing_jobs_or_full_descriptions(tmp_path, monkeypatch):
    from server.public_jobs import publish as publisher
    monkeypatch.setattr(publisher, "MAX_INDEX_BYTES", 18_000)
    description = ('"quoted" \\ 雪\n' * 700)
    records = [job(f"https://acme.example/jobs/{index}", source_id=str(index), description=description)
               for index in range(8)]
    state = merge(empty_state(), [clean_result(result(records))], 1)
    lock = {"catalog_commit": "a" * 40, "collections": []}
    manifest = publisher.publish(state, lock, tmp_path, generation="enriched", now=NOW)
    api = tmp_path / "api/v1"
    index_bytes = sum((api / ref["path"]).stat().st_size for ref in manifest["search_pages"])
    search = [item for ref in manifest["search_pages"]
              for item in json.loads((api / ref["path"]).read_text(encoding="utf-8"))["jobs"]]
    details = [item for ref in manifest["detail_pages"]
               for item in json.loads((api / ref["path"]).read_text(encoding="utf-8"))["jobs"]]
    assert index_bytes <= 18_000
    assert {item["id"] for item in search} == {item["id"] for item in records}
    assert {item["id"] for item in details} == {item["id"] for item in records}
    assert all(item["description"] == records[0]["description"] for item in details)
    assert all(0 < len(item["search_text"]) < 2000 for item in search)
    report = json.loads((tmp_path / "build-report.json").read_text())
    assert report["stage"] == "validated"
    assert report["search_index_bytes"] == index_bytes
    assert report["jobs_with_descriptions"] == 8
    assert all(len(item["search_text"]) == report["search_text_max_chars"] for item in search)


def test_search_metadata_above_previous_60_mb_budget_is_accepted():
    from server.public_jobs import publish as publisher
    rows = [{"title": "x" * 1000, "search_text": ""} for _ in range(70_000)]
    snippet_chars, size = publisher._fit_search_text(rows, "large-board")
    assert publisher.MAX_INDEX_BYTES == 200_000_000
    assert 60_000_000 < size <= publisher.MAX_INDEX_BYTES
    assert snippet_chars == publisher.MAX_SEARCH_TEXT_CHARS
    assert len(rows) == 70_000


def test_required_metadata_overflow_preserves_previous_generation(tmp_path, monkeypatch):
    from server.public_jobs import publish as publisher
    state = merge(empty_state(), [clean_result(result([job()]))], 1)
    lock = {"catalog_commit": "a" * 40, "collections": []}
    publisher.publish(state, lock, tmp_path, generation="before", now=NOW)
    previous = (tmp_path / "api/v1/manifest.json").read_bytes()
    monkeypatch.setattr(publisher, "MAX_INDEX_BYTES", 1)
    with pytest.raises(ValueError, match="Required search metadata alone"):
        publisher.publish(state, lock, tmp_path, generation="after", now=NOW)
    assert (tmp_path / "api/v1/manifest.json").read_bytes() == previous


def test_publication_budget_counts_retained_generations_without_early_deletion(tmp_path, monkeypatch):
    from server.public_jobs import publish as publisher
    state = merge(empty_state(), [clean_result(result([job()]))], 1)
    lock = {"catalog_commit": "a" * 40, "collections": []}
    for number in range(1, 4):
        publisher.publish(state, lock, tmp_path, generation=f"20260926-{number}", now=NOW)
    api = tmp_path / "api/v1"
    size = sum(p.stat().st_size for p in api.rglob("*") if p.is_file())
    monkeypatch.setattr(publisher, "MAX_PUBLISHED_BYTES", size + 500)
    publisher.publish(state, lock, tmp_path, generation="20260926-4", now=NOW)
    assert (api / "snapshots/20260926-1").exists()
    assert sum(p.stat().st_size for p in api.rglob("*") if p.is_file()) > publisher.MAX_PUBLISHED_BYTES
    publisher.retain_generations(tmp_path)
    assert not (api / "snapshots/20260926-1").exists()
    assert not (api / "snapshots/20260926-2").exists()
    assert (api / "snapshots/20260926-3").exists()
    assert (api / "snapshots/20260926-4").exists()
    assert sum(p.stat().st_size for p in api.rglob("*") if p.is_file()) <= publisher.MAX_PUBLISHED_BYTES


def test_budget_exhaustion_during_details_preserves_listing_and_retry_cache():
    from server.public_jobs.collector import CollectionBudgetError
    from server.scrapers.runtime import run_scraper
    from server.scrapers import build_recipe
    import httpx
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    cache = {}
    def handler(request):
        if request.url.path.endswith("/postings"):
            return httpx.Response(200, json={"content": [{"id": "1", "name": "Engineer",
                "ref": "https://api.smartrecruiters.com/v1/companies/Acme/postings/1"}]})
        raise CollectionBudgetError("Source request/time budget exhausted")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        value = run_scraper(recipe, client=client, detail_cache=cache)
    assert len(value.jobs) == 1 and value.complete
    assert cache["1"]["failures"] == 1
    assert "description detail enrichment was incomplete for 1 jobs" in value.warnings


def test_collector_preserves_withheld_listing_retry_state():
    import time
    def runner(recipe, *, client, detail_cache):
        detail_cache["withheld"] = {"signature": "same", "failures": 1, "next_attempt_at": 100}
        return ScrapeResult(strategy="generic_json", complete=False, jobs=[],
                            warnings=["source ownership could not be verified for 1 jobs"])
    value = collect_monitor(MONITOR, ScraperRecipe.model_validate(RECIPE), now=NOW,
                            limiter=HostLimiter(), deadline=time.monotonic() + 10, runner=runner)
    assert not value["jobs"] and value["source"]["status"] == "partial"
    assert value["detail_cache"]["withheld"]["failures"] == 1
