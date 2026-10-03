"""Persistent detail-cache recovery without losing known descriptions or ownership safety."""
from datetime import date
import httpx
import pytest
from server.scrapers import build_recipe, run_scraper
from server.scrapers import runtime, detail_cache
from server.scrapers.models import JobRecord, ScraperRecipe


@pytest.fixture
def clock(monkeypatch):
    now = [1_800_000_000.0]
    monkeypatch.setattr(runtime.time, "time", lambda: now[0])
    return now


def job(identity="a", **changes):
    return JobRecord(company="Acme", source_id=identity, title="Engineer " + identity,
        canonical_url="https://jobs.smartrecruiters.com/Acme/" + identity,
        source_url="https://jobs.smartrecruiters.com/Acme/" + identity,
        source="smartrecruiters", **changes)


def rich(text="Description"):
    return httpx.Response(200, json={"jobAd":{"sections":{"jobDescription":{"text":text}}}})


def test_stable_dates_and_salaries_keep_current_listing_and_cached_text(clock):
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    cache, calls = {}, []
    def handler(request):
        calls.append(request.url.path)
        return rich()
    original = job(posted_date=date(2026,9,1), salary_min=100000)
    changed = original.model_copy(update={"posted_date":date(2026,9,2), "salary_min":120000})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runtime._enrich_details([original], recipe, client, cache)
        records, _, _ = runtime._enrich_details([changed], recipe, client, cache)
    assert len(calls) == 1
    assert records[0].description == "Description" and records[0].salary_min == 120000
    assert records[0].posted_date == date(2026,9,2)


def test_workday_posted_today_then_relative_days_does_not_invalidate(clock):
    recipe = build_recipe("Acme", "https://acme.wd5.myworkdayjobs.com/en-US/Careers")
    dates, calls, cache = ["Posted Today"], [], {}
    def handler(request):
        if request.method == "GET":
            calls.append(str(request.url))
            return httpx.Response(200, json={"jobPostingInfo":{"jobDescription":"Full role description"}})
        return httpx.Response(200, json={"total":1,"jobPostings":[{
            "title":"Analyst", "externalPath":"/en-US/Careers/job/Analyst_R1",
            "locationsText":"Toronto","bulletFields":["R1"],"postedOn":dates[0]}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = run_scraper(recipe, client=client, detail_cache=cache)
        dates[0] = "Posted 2 Days Ago"
        second = run_scraper(recipe, client=client, detail_cache=cache)
    assert len(calls) == 1 and first.jobs[0].description == second.jobs[0].description


def test_failed_head_row_cannot_starve_later_rows_and_eventually_recovers(clock):
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    recipe.metadata["detail_fetch_limit"] = 1
    cache, calls, recovery = {}, [], [False]
    def handler(request):
        identity = request.url.path.rsplit("/",1)[-1]
        calls.append(identity)
        return httpx.Response(503) if identity == "a" and not recovery[0] else rich()
    jobs = [job("a"),job("b"),job("c")]
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for _ in range(4):
            runtime._enrich_details(jobs,recipe,client,cache)
        assert calls == ["a","b","c"]
        recovery[0] = True
        clock[0] += detail_cache.RETRY_BASE + 1
        records, _, _ = runtime._enrich_details(jobs,recipe,client,cache)
    assert calls == ["a","b","c","a"] and all(record.description for record in records)
    assert cache["a"]["failures"] == 0


def test_failed_invalidation_preserves_success_and_ttl_eventually_refreshes(clock):
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    cache, calls, text = {}, [], ["First valid text"]
    def handler(request):
        calls.append(request.url.path)
        return rich(text[0]) if text[0] else httpx.Response(200,json={})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        runtime._enrich_details([job()],recipe,client,cache)
        changed = job().model_copy(update={"title":"New title"})
        text[0] = ""
        records, _, _ = runtime._enrich_details([changed],recipe,client,cache)
        assert records[0].title == "New title" and records[0].description == "First valid text"
        runtime._enrich_details([changed],recipe,client,cache)
        assert len(calls) == 2
        clock[0] += detail_cache.RETRY_BASE + 1
        text[0] = "Updated detail"
        records, _, _ = runtime._enrich_details([changed],recipe,client,cache)
        assert records[0].description == "Updated detail"
        text[0] = "Daily refresh"
        clock[0] += detail_cache.SUCCESS_TTL + 1
        records, _, _ = runtime._enrich_details([changed],recipe,client,cache)
        assert records[0].description == "Daily refresh" and len(calls) == 4


def test_legacy_empty_cache_retries_and_retry_delay_is_capped(clock):
    recipe = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme")
    cache = {"a":{"signature":"legacy-signature","job":job().model_dump(mode="json")}}
    with httpx.Client(transport=httpx.MockTransport(lambda request:rich("Recovered"))) as client:
        records, count, _ = runtime._enrich_details([job()],recipe,client,cache)
    assert count == 1 and records[0].description == "Recovered"
    failure = {}
    for _ in range(30):
        failure = detail_cache.failure(failure,"sig",clock[0])
    assert failure["next_attempt_at"] - clock[0] == detail_cache.RETRY_MAX


def test_missing_or_changed_ownership_proof_never_leaks_unverified_roles(clock):
    recipe = build_recipe("Acme", "https://acme.wd5.myworkdayjobs.com/en-US/Careers").model_dump(mode="json")
    recipe["metadata"]["detail_fetch_limit"] = 1
    recipe["source_filter"] = {"predicates":[{"phase":"detail","path":"jobPostingInfo.brand","operator":"equals_ci","values":["Acme"]}]}
    available, cache = [False], {}
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200,json={"jobPostingInfo":{"brand":"Acme","jobDescription":"Known owned description"}}) if available[0] else httpx.Response(503)
        return httpx.Response(200,json={"total":2,"jobPostings":[
            {"title":key,"externalPath":"/en-US/Careers/job/"+key,"bulletFields":[key]} for key in ("a","b")]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = run_scraper(recipe,client=client,detail_cache=cache)
        assert not first.jobs and not first.complete
        available[0] = True
        second = run_scraper(recipe,client=client,detail_cache=cache)
        assert len(second.jobs) == 1 and not second.complete
        clock[0] += detail_cache.RETRY_BASE + 1
        complete = run_scraper(recipe,client=client,detail_cache=cache)
        assert len(complete.jobs) == 2 and complete.complete
        recipe["source_filter"]["predicates"][0]["values"] = ["Other"]
        available[0] = False
        for _ in range(2):
            changed = run_scraper(recipe,client=client,detail_cache=cache)
            assert not changed.jobs and not changed.complete


def test_generic_smartrecruiters_recipe_uses_verified_json_detail_endpoint(clock):
    raw = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme").model_dump(mode="json")
    raw["strategy"] = "generic_json"
    recipe = ScraperRecipe.model_validate(raw)
    calls = []
    def handler(request):
        calls.append(str(request.url))
        return rich("API description")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        records, count, _ = runtime._enrich_details([job()],recipe,client,{})
    assert count == 1 and records[0].description == "API description"
    assert calls == ["https://api.smartrecruiters.com/v1/companies/Acme/postings/a"]


def test_detail_human_url_can_differ_but_original_listing_identity_must_match():
    original = job()
    detailed = original.model_copy(update={"canonical_url":"https://jobs.smartrecruiters.com/Acme/a-readable-slug",
                                           "description":"Verified prior detail"})
    prior = {"job":detailed.model_dump(mode="json"), "job_listing_url":original.canonical_url}
    assert detail_cache.restore_missing(original,prior).description == "Verified prior detail"
    changed_identity = original.model_copy(update={"canonical_url":"https://jobs.smartrecruiters.com/Acme/different"})
    assert not detail_cache.restore_missing(changed_identity,prior).description


def test_cache_prunes_by_original_listing_not_filtered_ownership_results(clock):
    raw = build_recipe("Acme", "https://careers.smartrecruiters.com/Acme").model_dump(mode="json")
    raw["metadata"]["detail_fetch_limit"] = 1
    raw["source_filter"] = {"predicates":[{"phase":"detail","path":"brand","operator":"equals_ci","values":["Acme"]}]}
    recipe = ScraperRecipe.model_validate(raw)
    cache, calls = {"gone":{"signature":"absent"}}, []
    def handler(request):
        identity = request.url.path.rsplit("/",1)[-1]
        calls.append(identity)
        if identity == "a":
            return httpx.Response(503)
        return httpx.Response(200,json={"brand":"Other company","jobAd":{"sections":{"jobDescription":{"text":"Other role"}}}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first, _, _ = runtime._enrich_details([job("a"),job("b")],recipe,client,cache)
        assert not first and set(cache) == {"a"}
        second, _, _ = runtime._enrich_details([job("a"),job("b")],recipe,client,cache)
        assert not second and set(cache) == {"a","b"} and calls == ["a","b"]
        assert cache["b"]["ownership"] == "excluded"
        runtime._enrich_details([job("a"),job("b")],recipe,client,cache)
        assert calls == ["a","b"]
        runtime._enrich_details([job("b")],recipe,client,cache)
        assert set(cache) == {"b"} and calls == ["a","b"]


def test_cache_removes_absent_listing_ids_even_without_supported_enrichment():
    recipe = build_recipe("Acme","https://boards.greenhouse.io/acme")
    cache = {"a":{"job":"unchanged"},"gone":{"job":"old"}}
    records, count, warnings = runtime._enrich_details([job("a")],recipe,None,cache)
    assert [record.source_id for record in records] == ["a"]
    assert set(cache) == {"a"} and count == 0 and warnings == []
