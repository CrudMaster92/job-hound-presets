import json

import httpx

from server.scrapers.detail_extraction import enrich
from server.scrapers.models import JobRecord, ScraperRecipe
from server.scrapers.runtime import run_scraper


def recipe():
    return ScraperRecipe.model_validate({
        "company": "Example", "careers_url": "https://example.com/jobs",
        "strategy": "generic_html", "allowed_hosts": ["example.com"],
        "request": {"url": "https://example.com/jobs"},
        "selectors": {"item": ".job", "title": "h2", "link": "a"},
        "metadata": {"detail_fetch_limit": 1},
    })


def job():
    return JobRecord(source_id="one", title="Engineer", company="Example",
                     canonical_url="https://example.com/jobs/one", source_url="https://example.com/jobs/one", source="generic_html")


def html(*postings):
    return '<script type="application/ld+json">' + json.dumps({"@graph": list(postings)}) + '</script>'


def posting(**changes):
    return {"@type": "JobPosting", "title": "Engineer",
            "url": "https://example.com/jobs/one", "description": "<p>Build reliable tools.</p>", **changes}


def test_extracts_matching_structured_posting_not_navigation():
    result = enrich(job(), '<nav>Account login</nav>' + html(posting()), recipe())
    assert result.description == "Build reliable tools."


def test_rejects_other_roles_and_ambiguous_same_title():
    for content in [html(posting(title="Designer")), html(posting(url="https://example.com/jobs/two")),
                    html(posting(url=None), posting(url=None)), '<main>Login required</main>']:
        assert not enrich(job(), content, recipe()).description


def test_generic_details_use_bounded_runner_cache_and_host_allowlist():
    seen = []
    def handler(request):
        seen.append(str(request.url))
        if request.url.path == "/jobs":
            return httpx.Response(200, text='<div class="job"><h2>Engineer</h2><a href="/jobs/one">View</a></div>')
        return httpx.Response(200, text=html(posting()))
    cache = {}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        first = run_scraper(recipe(), client=client, detail_cache=cache)
        second = run_scraper(recipe(), client=client, detail_cache=cache)
    assert first.jobs[0].description == second.jobs[0].description == "Build reliable tools."
    assert seen.count("https://example.com/jobs/one") == 1


def test_labelled_html_detail_requires_matching_canonical_and_title():
    page = ('<link rel="canonical" href="https://example.com/jobs/one">'
            '<h2>Engineer</h2><article><h3>Description &amp; Requirements</h3>'
            '<div class="article__content">Build tools.</div></article>'
            '<aside>Share and login</aside>')
    assert enrich(job(), page, recipe()).description == "Build tools."
    assert not enrich(job(), page.replace('/jobs/one', '/jobs/two'), recipe()).description
    assert not enrich(job(), page.replace('Engineer', 'Designer'), recipe()).description
    assert not enrich(job(), page + '<h2>Engineer</h2>', recipe()).description
