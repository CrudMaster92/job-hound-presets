"""Bounded anonymous collection using the same deterministic scraper runtime."""
from __future__ import annotations

import threading
import time
import copy
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from ..scrapers.models import ScraperRecipe
from ..scrapers.http import ScraperNetworkError
from ..scrapers.runtime import run_scraper
from .schema import PublicJob, job_id, timestamp

WORKERS = 4
SOURCE_SECONDS = 180
MAX_REQUESTS = 60
DETAIL_LIMIT = 20
MAX_BODY_BYTES = 20_000_000


class CollectionBudgetError(ScraperNetworkError):
    pass


class HostLimiter:
    """One request at a time per host, with a short quiet interval."""
    def __init__(self):
        self.lock = threading.Lock()
        self.hosts: dict[str, threading.Lock] = {}
        self.last: dict[str, float] = {}

    def acquire(self, host: str, deadline: float) -> threading.Lock:
        with self.lock:
            guard = self.hosts.setdefault(host, threading.Lock())
        if not guard.acquire(timeout=max(0, deadline - time.monotonic())):
            raise CollectionBudgetError("Host request budget exhausted")
        pause = max(0, self.last.get(host, 0) + 0.5 - time.monotonic())
        if time.monotonic() + pause >= deadline:
            guard.release()
            raise CollectionBudgetError("Source time budget exhausted")
        if pause:
            time.sleep(pause)
        return guard


class PublicClient(httpx.Client):
    # The injected-client runtime seam must keep DNS/IP protections enabled.
    _jobhound_resolve_dns = True

    def __init__(self, limiter: HostLimiter, deadline: float):
        super().__init__(trust_env=False, follow_redirects=False)
        self.limiter = limiter
        self.deadline = deadline
        self.requests_used = 0

    def request(self, method, url, **kwargs):
        self.requests_used += 1
        remaining = self.deadline - time.monotonic()
        if self.requests_used > MAX_REQUESTS or remaining <= 0:
            raise CollectionBudgetError("Source request/time budget exhausted")
        if urlsplit(str(url)).scheme != "https":
            raise CollectionBudgetError("Public collection requires HTTPS")
        host = urlsplit(str(url)).hostname or ""
        guard = self.limiter.acquire(host, self.deadline)
        try:
            kwargs["timeout"] = min(float(kwargs.get("timeout", 15)), max(0.1, self.deadline - time.monotonic()))
            with super().stream(method, url, **kwargs) as response:
                if int(response.headers.get("content-length", "0") or 0) > MAX_BODY_BYTES:
                    raise CollectionBudgetError("Source response exceeds byte budget")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BODY_BYTES or time.monotonic() > self.deadline:
                        raise CollectionBudgetError("Source response exceeds collection budget")
                    chunks.append(chunk)
                headers = dict(response.headers)
                headers.pop("content-encoding", None)
                headers.pop("content-length", None)
                return httpx.Response(response.status_code, headers=headers, content=b"".join(chunks), request=response.request)
        finally:
            self.limiter.last[host] = time.monotonic()
            guard.release()


def text_only(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for node in soup(["script", "style", "iframe", "object"]):
        node.decompose()
    return soup.get_text("\n", strip=True)[:100_000]


def normalize_job(record, monitor: dict, now: datetime) -> dict:
    value = record.model_dump(mode="json")
    salary_min, salary_max = value.get("salary_min"), value.get("salary_max")
    amount = " – ".join(f"{amount:,.0f}" for amount in (salary_min, salary_max) if amount is not None)
    salary_text = f"{value.get('salary_currency') or ''} {amount}".strip() if amount else None
    if salary_text and value.get("salary_period"):
        salary_text += "/" + value["salary_period"]
    return PublicJob(
        id=job_id(monitor["company_id"], value["canonical_url"]),
        company_id=monitor["company_id"], company_name=monitor["company_name"],
        collection_ids=monitor["collection_ids"], monitor_ids=[monitor["id"]],
        title=text_only(value["title"]), location=text_only(value["location"]),
        work_mode=value["remote_mode"], employment_type=value["employment_type"],
        salary_text=salary_text, salary_min=salary_min, salary_max=salary_max,
        salary_currency=value["salary_currency"], salary_period=value["salary_period"],
        description=text_only(value["description"]), source_url=value["canonical_url"],
        source_job_id=value["source_id"], posted_at=value["posted_date"],
        first_seen_at=timestamp(now), last_seen_at=timestamp(now),
    ).model_dump(mode="json")


def collect_monitor(monitor: dict, recipe: ScraperRecipe, *, now: datetime, limiter: HostLimiter,
                    deadline: float, runner=run_scraper, detail_cache: dict | None = None) -> dict:
    source = {key: monitor[key] for key in ("id", "company_id", "company_name", "revision")}
    if monitor.get("artifact_hash"):
        source["artifact_hash"] = monitor["artifact_hash"]
    source.update(status="failed", complete=False, job_count=0, warnings=[])
    try:
        if time.monotonic() >= deadline:
            raise CollectionBudgetError("Build time budget exhausted")
        bounded = recipe.model_copy(deep=True)
        bounded.metadata["detail_fetch_limit"] = DETAIL_LIMIT
        cache = copy.deepcopy(detail_cache or {})
        with PublicClient(limiter, min(deadline, time.monotonic() + SOURCE_SECONDS)) as client:
            result = runner(bounded, client=client, detail_cache=cache)
        # Fail the source if normalization rejects even one record: discarding it
        # and calling this a complete listing could incorrectly close a job.
        jobs = [normalize_job(job, monitor, now) for job in result.jobs]
        source.update(status="complete" if result.complete else "partial", complete=result.complete,
                      job_count=len(jobs), warnings=[str(warning)[:500] for warning in result.warnings[:10]])
        if not result.complete:
            source["warnings"].insert(0, "Bounded source: this listing is incomplete; unseen roles are not confirmed closed.")
        # Runtime prunes against the original listing before ownership filtering.
        # Retry/proof state for withheld rows must survive without exporting jobs.
        return {"source": source, "jobs": jobs, "detail_cache": cache}
    except Exception as exc:
        # No response bodies, request URLs, internal paths or environment values
        # enter the public feed diagnostics.
        source["warnings"] = [f"Collection failed ({type(exc).__name__}); previous results retained until expiry."]
        return {"source": source, "jobs": []}


def collect(monitors: list[tuple[dict, ScraperRecipe]], *, now: datetime, minutes: int = 40,
            runner=run_scraper, progress=None, source_caches: dict | None = None) -> list[dict]:
    limiter = HostLimiter()
    deadline = time.monotonic() + minutes * 60
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        remaining = iter(monitors)
        active = set()
        exhausted = False
        while active or not exhausted:
            while not exhausted and len(active) < WORKERS and time.monotonic() < deadline:
                item = next(remaining, None)
                if item is None:
                    exhausted = True
                    break
                monitor, recipe = item
                active.add(pool.submit(collect_monitor, monitor, recipe, now=now, limiter=limiter,
                                       deadline=deadline, runner=runner, detail_cache=(source_caches or {}).get(monitor["id"])))
            if time.monotonic() >= deadline:
                exhausted = True
            if not active:
                break
            finished, active = wait(active, return_when=FIRST_COMPLETED)
            for future in finished:
                result = future.result()
                results.append(result)
                if progress:
                    progress(result["source"])
    return sorted(results, key=lambda result: result["source"]["id"])
