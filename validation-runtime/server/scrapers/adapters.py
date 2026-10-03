"""Deterministic ATS and generic document adapters."""

from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from .models import JobRecord, ScraperRecipe
from .normalize import first, make_job, plain_text


def _smartrecruiters_description(raw: dict[str, Any]) -> str:
    sections = raw.get("jobAd", {}).get("sections", {})
    return " ".join(
        plain_text(first(sections, key + ".text"))
        for key in ("jobDescription", "qualifications", "additionalInformation")
    ).strip()


def ashby(data: dict[str, Any], recipe: ScraperRecipe) -> list[JobRecord]:
    jobs = []
    for raw in data.get("jobs", []):
        if raw.get("isListed") is False:
            continue
        locations = [raw.get("location")]
        locations.extend(
            item.get("location") or item.get("name")
            for item in (raw.get("secondaryLocations") or [])
            if isinstance(item, dict)
        )
        location = "; ".join(dict.fromkeys(str(item).strip() for item in locations if item)) or "Unspecified"
        jobs.append(make_job(
            company=recipe.company,
            source="ashby",
            source_id=raw.get("id"),
            title=raw.get("title"),
            location=location,
            url=raw.get("jobUrl") or raw.get("applyUrl"),
            base_url=recipe.careers_url,
            description=raw.get("descriptionPlain") or raw.get("descriptionHtml"),
            posted_date=raw.get("publishedAt"),
            employment_type=raw.get("employmentType"),
            salary_min=first(raw, "compensation.min", "salary.min", "salaryRange.min", "compensationTierSummary"),
            salary_max=first(raw, "compensation.max", "salary.max", "salaryRange.max"),
            currency=first(raw, "compensation.currency", "salary.currency", "salaryRange.currency"),
            salary_period=first(raw, "compensation.interval", "salary.interval", "salaryRange.interval"),
            remote_mode="remote" if raw.get("isRemote") is True or raw.get("workplaceType") == "Remote" else raw.get("workplaceType"),
        ))
    return jobs


def greenhouse(data: dict[str, Any], recipe: ScraperRecipe) -> list[JobRecord]:
    jobs = []
    for raw in data.get("jobs", []):
        location = first(raw, "location.name", "offices.0.name") or "Unspecified"
        metadata = {str(item.get("name", "")).casefold(): item.get("value") for item in raw.get("metadata", []) if isinstance(item, dict)}
        pay_range = first(raw, "pay_input_ranges.0") or {}
        salary_min = pay_range.get("min_cents") / 100 if isinstance(pay_range.get("min_cents"), (int, float)) else first(raw, "salary_range.min")
        salary_max = pay_range.get("max_cents") / 100 if isinstance(pay_range.get("max_cents"), (int, float)) else first(raw, "salary_range.max")
        jobs.append(make_job(company=recipe.company, source="greenhouse", source_id=raw.get("id"), title=raw.get("title"), location=location, url=raw.get("absolute_url"), base_url=recipe.careers_url, description=raw.get("content"), posted_date=raw.get("updated_at"), employment_type=first(raw, "employment_type", "employmentType") or metadata.get("employment type") or metadata.get("job type"), salary_min=salary_min, salary_max=salary_max, currency=pay_range.get("currency_type") or first(raw, "salary_range.currency"), salary_period=pay_range.get("pay_period") or pay_range.get("unit") or first(raw, "salary_range.period")))
    return jobs


def lever(data: list[dict[str, Any]], recipe: ScraperRecipe) -> list[JobRecord]:
    jobs = []
    for raw in data:
        categories = raw.get("categories") or {}
        lists = raw.get("lists") or []
        extra = " ".join(plain_text(item.get("content")) for item in lists if isinstance(item, dict))
        salary = raw.get("salaryRange") or {}
        jobs.append(make_job(company=recipe.company, source="lever", source_id=raw.get("id"), title=raw.get("text"), location=categories.get("location"), url=raw.get("hostedUrl") or raw.get("applyUrl"), base_url=recipe.careers_url, description=f"{raw.get('descriptionPlain') or raw.get('description') or ''} {extra}", employment_type=categories.get("commitment"), salary_min=salary.get("min"), salary_max=salary.get("max"), currency=salary.get("currency"), salary_period=salary.get("interval"), remote_mode=raw.get("workplaceType")))
    return jobs


def smartrecruiters(data: dict[str, Any], recipe: ScraperRecipe) -> list[JobRecord]:
    jobs = []
    for raw in data.get("content", data.get("jobs", [])):
        location = raw.get("location") or {}
        location_text = location.get("fullLocation") or ", ".join(filter(None, [location.get("city"), location.get("region"), location.get("country")]))
        description = _smartrecruiters_description(raw)
        jobs.append(make_job(company=recipe.company, source="smartrecruiters", source_id=raw.get("id"), title=raw.get("name") or raw.get("title"), location=location_text, url=raw.get("ref") or raw.get("applyUrl"), base_url=recipe.careers_url, description=description, posted_date=raw.get("releasedDate"), employment_type=first(raw, "typeOfEmployment.label", "typeOfEmployment"), salary_min=first(raw, "compensation.minimum", "compensation.min", "salary.min", "salaryRange.min"), salary_max=first(raw, "compensation.maximum", "compensation.max", "salary.max", "salaryRange.max"), currency=first(raw, "compensation.currency", "salary.currency", "salaryRange.currency"), salary_period=first(raw, "compensation.interval", "compensation.period", "salary.interval", "salaryRange.period"), remote_mode="remote" if location.get("remote") is True else None))
    return jobs


def enrich_smartrecruiters(job: JobRecord, raw: dict[str, Any], recipe: ScraperRecipe) -> JobRecord:
    """Merge one bounded posting-detail response into its list record."""
    location = raw.get("location") or {}
    location_text = location.get("fullLocation") or ", ".join(
        filter(None, [location.get("city"), location.get("region"), location.get("country")])
    )
    return make_job(
        company=job.company, source=job.source, source_id=job.source_id,
        title=raw.get("name") or raw.get("title") or job.title,
        location=location_text or job.location, url=job.source_url, base_url=recipe.careers_url,
        description=_smartrecruiters_description(raw) or job.description,
        posted_date=raw.get("releasedDate") or job.posted_date,
        employment_type=first(raw, "typeOfEmployment.label", "typeOfEmployment") or job.employment_type,
        salary_min=first(raw, "compensation.minimum", "compensation.min", "salary.min", "salaryRange.min") or job.salary_min,
        salary_max=first(raw, "compensation.maximum", "compensation.max", "salary.max", "salaryRange.max") or job.salary_max,
        currency=first(raw, "compensation.currency", "salary.currency", "salaryRange.currency") or job.salary_currency,
        salary_period=first(raw, "compensation.interval", "compensation.period", "salary.interval", "salaryRange.period") or job.salary_period,
        remote_mode="remote" if location.get("remote") is True else job.remote_mode.value,
    )


def workday(data: dict[str, Any], recipe: ScraperRecipe) -> list[JobRecord]:
    jobs = []
    for raw in data.get("jobPostings", []):
        path = raw.get("externalPath") or raw.get("url")
        info = raw.get("jobPostingInfo") or raw
        if not (info.get("title") or raw.get("title")) or not path:
            continue
        jobs.append(make_job(company=recipe.company, source="workday", source_id=first(info, "jobReqId", "jobPostingId") or raw.get("bulletFields", [None])[0] or path, title=info.get("title") or raw.get("title"), location=info.get("location") or raw.get("locationsText") or raw.get("location"), url=info.get("externalUrl") or path, base_url=recipe.careers_url, description=info.get("jobDescription") or raw.get("description"), posted_date=info.get("startDate") or raw.get("postedOn"), employment_type=info.get("timeType") or raw.get("timeType")))
    return jobs


def enrich_workday(job: JobRecord, raw: dict[str, Any], recipe: ScraperRecipe) -> JobRecord:
    """Merge Workday's jobPostingInfo detail payload into its compact list record."""
    info = raw.get("jobPostingInfo") or raw
    return make_job(
        company=job.company, source=job.source, source_id=job.source_id,
        title=info.get("title") or job.title,
        location=info.get("location") or job.location,
        url=info.get("externalUrl") or job.source_url, base_url=recipe.careers_url,
        description=info.get("jobDescription") or info.get("description") or job.description,
        posted_date=info.get("startDate") or job.posted_date,
        employment_type=info.get("timeType") or info.get("workerType") or job.employment_type,
        salary_min=first(info, "salary.min", "salaryRange.min") or job.salary_min,
        salary_max=first(info, "salary.max", "salaryRange.max") or job.salary_max,
        currency=first(info, "salary.currency", "salaryRange.currency") or job.salary_currency,
        salary_period=first(info, "salary.period", "salaryRange.period") or job.salary_period,
        remote_mode=job.remote_mode.value,
    )


def _json_ld_nodes(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from _json_ld_nodes(item)
    elif isinstance(data, dict):
        if data.get("@type") == "JobPosting" or "JobPosting" in (data.get("@type") or []):
            yield data
        for key in ("@graph", "itemListElement"):
            if key in data:
                yield from _json_ld_nodes(data[key])


def json_ld(html: str, recipe: ScraperRecipe) -> list[JobRecord]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for raw in _json_ld_nodes(payload):
            location_data = raw.get("jobLocation") or raw.get("applicantLocationRequirements") or {}
            if isinstance(location_data, list):
                location_data = location_data[0] if location_data else {}
            address = first(location_data, "address") or location_data
            if isinstance(address, dict):
                location = ", ".join(filter(None, [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]))
            else:
                location = address
            identifier = raw.get("identifier")
            if isinstance(identifier, dict):
                identifier = identifier.get("value")
            salary = raw.get("baseSalary") or {}
            salary_value = first(salary, "value")
            salary_min = salary_value.get("minValue") if isinstance(salary_value, dict) else salary_value
            salary_max = salary_value.get("maxValue") if isinstance(salary_value, dict) else salary_value
            jobs.append(make_job(company=recipe.company, source="json_ld", source_id=identifier, title=raw.get("title"), location=location, url=raw.get("url") or recipe.careers_url, base_url=recipe.careers_url, description=raw.get("description"), posted_date=raw.get("datePosted"), employment_type=raw.get("employmentType"), salary_min=salary_min, salary_max=salary_max, currency=salary.get("currency"), salary_period=salary_value.get("unitText") if isinstance(salary_value, dict) else salary.get("unitText"), remote_mode="remote" if raw.get("jobLocationType") == "TELECOMMUTE" else None))
    return jobs


def generic_html(html: str, recipe: ScraperRecipe, *, source: str = "generic_html") -> list[JobRecord]:
    # Prefer standards-based structured data even for pages reached through a generic recipe.
    structured = json_ld(html, recipe)
    if structured:
        return structured
    soup = BeautifulSoup(html, "html.parser")
    selectors = recipe.selectors
    jobs = []

    def selected(item, field: str):
        selector = selectors.get(field)
        return item.select_one(selector) if selector else None

    def node_value(node, *, attribute: str | None = None):
        if not node:
            return None
        return node.get(attribute) or node.get_text(" ", strip=True) if attribute else node.get_text(" ", strip=True)

    for index, item in enumerate(soup.select(selectors.get("item", ".job"))):
        title_node = item.select_one(selectors.get("title", "h2, h3, .title"))
        link_node = item.select_one(selectors.get("link", "a[href]"))
        location_node = item.select_one(selectors.get("location", ".location"))
        description_node = item.select_one(selectors.get("description", ".description"))
        employment_node = selected(item, "employment_type")
        salary_node = selected(item, "salary")
        source_id = item.get("data-job-id") or item.get("id")
        link = link_node.get("href") if link_node else None
        template = recipe.metadata.get("link_template")
        if not link and source_id and isinstance(template, str) and "{source_id}" in template:
            link = template.replace("{source_id}", quote(str(source_id), safe=""))
        if not title_node or not link:
            continue
        salary_text = node_value(salary_node)
        posted_node = selected(item, "posted_date")
        jobs.append(make_job(
            company=recipe.company, source=source, source_id=source_id,
            title=title_node.get_text(" ", strip=True),
            location=location_node.get_text(" ", strip=True) if location_node else "Unspecified",
            url=urljoin(recipe.careers_url, link), base_url=recipe.careers_url,
            description=description_node.get_text(" ", strip=True) if description_node else "",
            employment_type=node_value(employment_node),
            posted_date=node_value(posted_node, attribute="datetime"),
            remote_mode=node_value(selected(item, "remote_mode")),
            salary_min=node_value(selected(item, "salary_min")) or salary_text,
            salary_max=node_value(selected(item, "salary_max")),
            currency=node_value(selected(item, "salary_currency")),
            salary_period=node_value(selected(item, "salary_period")) or salary_text,
        ))
    return jobs


def generic_json(data: Any, recipe: ScraperRecipe) -> list[JobRecord]:
    def at_path(value: Any, path: str | None) -> Any:
        if not path:
            return value
        return first(value, path)
    records = at_path(data, recipe.mapping.get("items"))
    if not isinstance(records, list):
        return []
    jobs = []
    for raw in records:
        if not isinstance(raw, dict):
            continue
        get = lambda field: at_path(raw, recipe.mapping.get(field, field))
        jobs.append(make_job(company=recipe.company, source="generic_json", source_id=get("source_id"), title=get("title"), location=get("location"), url=get("url"), base_url=recipe.careers_url, description=get("description"), posted_date=get("posted_date"), employment_type=get("employment_type"), salary_min=get("salary_min"), salary_max=get("salary_max"), currency=get("salary_currency"), salary_period=get("salary_period"), remote_mode=get("remote_mode")))
    return jobs
