"""Platform detection and safe default recipe construction."""

from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from .http import bounded_request
from .models import DetectionResult, PaginationConfig, RequestConfig, ScraperRecipe, ScraperStrategy


def detect_platform(careers_url: str, *, html: str | None = None) -> DetectionResult:
    url = careers_url.casefold()
    host = (urlsplit(careers_url).hostname or "").casefold()
    # Some companies serve a branded careers UI that blocks non-browser HTTP,
    # while publishing the same listings through an ATS feed. Detect those
    # aliases before probing the branded page.
    if (host == "openai.com" or host.endswith(".openai.com")) and "/careers" in url:
        return DetectionResult(strategy=ScraperStrategy.ASHBY, confidence=1, evidence=["OpenAI Ashby careers feed"])
    checks = [
        ("ashby", ScraperStrategy.ASHBY, ["jobs.ashbyhq.com", "api.ashbyhq.com", "posting-api/job-board"]),
        ("greenhouse", ScraperStrategy.GREENHOUSE, ["greenhouse.io", "boards.greenhouse", "gh_jid"]),
        ("lever", ScraperStrategy.LEVER, ["jobs.lever.co", "lever.co"]),
        ("smartrecruiters", ScraperStrategy.SMARTRECRUITERS, ["smartrecruiters.com"]),
        ("workday", ScraperStrategy.WORKDAY, ["myworkdayjobs.com", "workday"]),
        ("jobvite", ScraperStrategy.JOBVITE, ["jobs.jobvite.com", "jobvite"]),
    ]
    haystack = f"{url}\n{(html or '').casefold()}"
    for label, strategy, markers in checks:
        found = [marker for marker in markers if marker in haystack]
        if found:
            return DetectionResult(strategy=strategy, confidence=.99 if any(m in host for m in found) else .9, evidence=found)
    directemployers_markers = [
        marker for marker in (
            "directemployersgooglemapscallback",
            "directemployers.org/privacy-terms",
            "seo.nlx.org",
            "window.__nuxt__.config",
        )
        if marker in haystack
    ]
    if len(directemployers_markers) >= 2:
        return DetectionResult(
            strategy=ScraperStrategy.GENERIC_JSON,
            confidence=.98,
            evidence=["DirectEmployers/NLX public jobs feed", *directemployers_markers],
        )
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or script.get_text())
            except (json.JSONDecodeError, TypeError):
                continue
            serialized = json.dumps(data)
            if "JobPosting" in serialized:
                return DetectionResult(strategy=ScraperStrategy.JSON_LD, confidence=.95, evidence=["JobPosting JSON-LD"])
    return DetectionResult(strategy=ScraperStrategy.GENERIC_HTML, confidence=.35, evidence=["no known ATS signature"])


def _parts(url: str) -> tuple[str, list[str], str]:
    parsed = urlsplit(url)
    return parsed.hostname or "", [p for p in parsed.path.split("/") if p], f"{parsed.scheme}://{parsed.netloc}"


def _embedded_ashby_slug(html: str | None) -> str | None:
    if not html:
        return None
    patterns = (
        r"api\.ashbyhq\.com/posting-api/job-board/([a-z0-9_-]+)",
        r"jobs\.ashbyhq\.com/([a-z0-9_-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def build_recipe(company: str, careers_url: str, *, html: str | None = None) -> ScraperRecipe:
    detected = detect_platform(careers_url, html=html)
    host, parts, origin = _parts(careers_url)
    strategy = detected.strategy
    request_url = careers_url
    method = "GET"
    body = None
    pagination = PaginationConfig()
    allowed = [host.lower()]
    metadata: dict[str, str | int | bool] = {}
    selectors: dict[str, str] = {}
    mapping: dict[str, str] = {}
    params: dict[str, str | int | float | bool] = {}

    if strategy == ScraperStrategy.ASHBY:
        if host == "openai.com" or host.endswith(".openai.com"):
            slug = "openai"
        elif host == "api.ashbyhq.com" and "job-board" in parts:
            slug = parts[-1]
        elif embedded_slug := _embedded_ashby_slug(html):
            slug = embedded_slug
        else:
            slug = parts[0] if parts else host.split(".")[0]
        request_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        allowed.append("api.ashbyhq.com")
        metadata["company_slug"] = slug
    elif strategy == ScraperStrategy.GREENHOUSE:
        token = parts[0] if parts else host.split(".")[0]
        if token in {"embed", "jobs"} and len(parts) > 1:
            token = parts[1]
        request_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        params = {"content": True}
        allowed.append("boards-api.greenhouse.io")
        metadata["board_token"] = token
    elif strategy == ScraperStrategy.LEVER:
        slug = parts[0] if parts else host.split(".")[0]
        request_url = f"https://api.lever.co/v0/postings/{slug}"
        params = {"mode": "json"}
        allowed.append("api.lever.co")
        metadata["company_slug"] = slug
    elif strategy == ScraperStrategy.SMARTRECRUITERS:
        slug = parts[0] if parts else ""
        request_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        allowed.append("api.smartrecruiters.com")
        metadata["company_slug"] = slug
        metadata["detail_fetch_limit"] = 100
        pagination = PaginationConfig(kind="offset", parameter="offset", page_size_parameter="limit", page_size=100, max_pages=10)
    elif strategy == ScraperStrategy.WORKDAY:
        # Common form: tenant.wdN.myworkdayjobs.com/en-US/site[/job/...]
        tenant = host.split(".")[0]
        locale_index = next((i for i, p in enumerate(parts) if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)), -1)
        site = parts[locale_index + 1] if locale_index >= 0 and len(parts) > locale_index + 1 else (parts[0] if parts else "jobs")
        request_url = f"{origin}/wday/cxs/{tenant}/{site}/jobs"
        method = "POST"
        body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
        metadata.update({"tenant": tenant, "site": site})
        metadata["detail_fetch_limit"] = 100
        pagination = PaginationConfig(kind="offset", parameter="offset", page_size_parameter="limit", page_size=20, max_pages=25)
    elif strategy == ScraperStrategy.JOBVITE:
        selectors = {"item": "[data-job-id], .jv-job-list-name, .jv-job-list > li", "title": "h2, h3, .jv-job-list-name", "link": "a", "location": ".jv-job-list-location, .location"}
    elif strategy == ScraperStrategy.GENERIC_JSON and "DirectEmployers/NLX public jobs feed" in detected.evidence:
        request_url = f"{careers_url.rstrip('/')}/feeds/json"
        pagination = PaginationConfig(kind="page", parameter="page", page_size=14, max_pages=100)
        mapping = {
            "source_id": "guid", "title": "title", "location": "location", "url": "url",
            "description": "description", "posted_date": "date_new",
        }
        metadata["platform"] = "directemployers"
    elif strategy == ScraperStrategy.GENERIC_HTML:
        selectors = {"item": "[data-job-id], .job, .job-listing, li.position, article", "title": "h2, h3, .title, [itemprop=title]", "link": "a[href]", "location": ".location, [itemprop=jobLocation]", "description": ".description, [itemprop=description]", "employment_type": ".employment-type, .job-type, [itemprop=employmentType]", "salary": ".salary, .compensation, [itemprop=baseSalary]"}

    return ScraperRecipe(
        company=company,
        careers_url=careers_url,
        strategy=strategy,
        allowed_hosts=list(dict.fromkeys(allowed)),
        request=RequestConfig(
            url=request_url,
            method=method,
            params=params,
            json_body=body,
            # Large employers can publish many descriptions in one ATS response.
            max_response_bytes=(
                20_000_000
                if strategy in {ScraperStrategy.ASHBY, ScraperStrategy.GREENHOUSE}
                else 1_000_000
                if metadata.get("platform") == "directemployers"
                else 5_000_000
            ),
        ),
        pagination=pagination,
        selectors=selectors,
        mapping=mapping,
        metadata=metadata,
    )


def build_recipe_from_url(company: str, careers_url: str, *, client: httpx.Client | None = None) -> ScraperRecipe:
    host = (urlsplit(careers_url).hostname or "").lower()
    probe = RequestConfig(url=careers_url)
    response = bounded_request(probe, [host], client)
    content_type = response.headers.get("content-type", "")
    html = response.text if "html" in content_type or response.text.lstrip().startswith("<") else None
    return build_recipe(company, careers_url, html=html)
