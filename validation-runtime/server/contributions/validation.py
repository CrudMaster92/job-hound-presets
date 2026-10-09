"""Trusted deterministic validation. Candidate files are data, never Python."""
from __future__ import annotations

import copy
import json
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import AwareDatetime, Field
from ..scrapers.models import ScraperRecipe
from ..scrapers.runtime import run_scraper
from ..scrapers.http import _validate_target
from ..public_jobs.collector import PublicClient, HostLimiter, SOURCE_SECONDS
from .contracts import Contract, Proposal, SHA_PATTERN, content_hash, safe_public_url, validate_documents


class ValidationReceipt(Contract):
    format: Literal["jobhound-scraper-validation"] = "jobhound-scraper-validation"
    version: Literal[1] = 1
    pr_number: int = Field(ge=1)
    head_commit: str = Field(pattern=SHA_PATTERN)
    base_commit: str = Field(pattern=SHA_PATTERN)
    monitor_id: str
    company_id: str
    revision: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    proposal_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    runtime_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    checked_at: AwareDatetime
    verdict: Literal["pass", "needs_repair", "blocked"]
    job_count: int = Field(ge=0)
    pages: int = Field(ge=0)
    complete: bool
    warnings: list[str] = Field(max_length=30)
    representative_urls: list[str] = Field(max_length=10)
    ownership_review_required: Literal[True] = True
    public_collection_eligible: bool
    errors: list[str] = Field(max_length=30)


def parse_fixture(proposal: Proposal) -> dict:
    """A bounded test seam; cannot contact the Internet or establish live proof."""
    recipe = ScraperRecipe.model_validate(proposal.monitor["recipe"]).model_copy(deep=True)
    if recipe.strategy.value == "playwright":
        return {"status": "unsupported", "job_count": 0, "runtime_verified": False,
                "message": "Browser fixtures cannot prove browser execution."}
    recipe.pagination.kind = "none"
    recipe.metadata["detail_fetch_limit"] = 0
    def respond(request):
        if str(request.url).split("?", 1)[0] != recipe.request.url.split("?", 1)[0]:
            return httpx.Response(404)
        payload = proposal.fixture.payload
        return httpx.Response(200, text=payload) if isinstance(payload, str) else httpx.Response(200, json=payload)
    with httpx.Client(transport=httpx.MockTransport(respond), trust_env=False) as client:
        result = run_scraper(recipe, client=client)
    return {"status": "parsed" if result.jobs else "empty", "job_count": len(result.jobs),
            "runtime_verified": False, "warnings": result.warnings[:10],
            "representative_urls": [job.source_url for job in result.jobs[:3]]}


def validate_live(proposal: Proposal, *, pr_number: int, head_commit: str,
                  runtime_revision: str, runner=run_scraper) -> ValidationReceipt:
    normalized = validate_documents(proposal)
    recipe = ScraperRecipe.model_validate(normalized["monitor"]["recipe"])
    evidence = dict(pr_number=pr_number, head_commit=head_commit, base_commit=proposal.base_commit,
                    monitor_id=proposal.monitor["id"], company_id=proposal.company["id"], revision=proposal.monitor["revision"],
                    artifact_hash=content_hash(normalized["monitor"]), proposal_hash=normalized["proposal_hash"],
                    runtime_revision=runtime_revision, checked_at=datetime.now(timezone.utc),
                    verdict="blocked", job_count=0, pages=0, complete=False, warnings=[],
                    representative_urls=[], public_collection_eligible=recipe.strategy.value != "playwright", errors=[])
    if recipe.strategy.value == "playwright":
        evidence["errors"] = ["Browser execution requires separate supported desktop validation; excluded from public collection."]
        return ValidationReceipt.model_validate(evidence)
    try:
        offline = parse_fixture(proposal)
        if offline["job_count"] < 1:
            evidence.update(verdict="needs_repair", errors=["The trimmed public fixture produces no jobs in the canonical parser."])
            return ValidationReceipt.model_validate(evidence)
        bounded = recipe.model_copy(deep=True)
        bounded.metadata["detail_fetch_limit"] = 20
        with PublicClient(HostLimiter(), time.monotonic() + SOURCE_SECONDS) as client:
            result = runner(bounded, client=client, detail_cache={})
        errors = []
        evidence.update(job_count=len(result.jobs), pages=result.pages_fetched, complete=result.complete,
                        warnings=[str(item)[:500] for item in result.warnings[:20]],
                        representative_urls=[job.source_url for job in result.jobs[:10]])
        if not result.jobs:
            errors.append("No live company-owned jobs; empty sources remain blocked, not verified.")
        if not result.complete and not recipe.metadata.get("partial_listing"):
            errors.append("Unexplained incomplete listing; declare and review bounded coverage.")
        actual_urls = {job.source_url.rstrip("/") for job in result.jobs}
        if not actual_urls.intersection(url.rstrip("/") for url in proposal.ownership.representative_urls):
            errors.append("Ownership examples do not match any currently returned source URL.")
        for job in result.jobs:
            safe_public_url(job.source_url)
            safe_public_url(job.canonical_url)
            if job.company != proposal.company["name"]:
                errors.append("Normalized job belongs to a different company.")
        # The runtime applies all declared listing/detail ownership predicates.
        # Source/company relationship remains an explicit human review item;
        # assigning recipe.company is not proof of employer identity.
        if proposal.ownership.shared_feed and not recipe.source_filter:
            errors.append("Shared feed has no ownership boundary.")
        evidence["errors"] = list(dict.fromkeys(errors))[:30]
        evidence["verdict"] = "pass" if not errors else "blocked" if not result.jobs else "needs_repair"
    except Exception as exc:
        # Never publish bodies, credentials or environment values in diagnostics.
        evidence["errors"] = [f"Live validation blocked ({type(exc).__name__}); inspect network/source access on the trusted runner."]
    return ValidationReceipt.model_validate(evidence)


def effective_verification(monitor: dict, receipt: dict, *, runtime_revision: str | None = None) -> dict:
    """Caller must load receipts from the trusted publisher, never a contributor path."""
    proof = ValidationReceipt.model_validate(receipt)
    if proof.verdict != "pass" or proof.job_count < 1 or not proof.public_collection_eligible:
        raise ValueError("Receipt does not establish public collection eligibility")
    if (proof.monitor_id, proof.company_id, proof.revision) != (monitor["id"], monitor["company_id"], monitor["revision"]):
        raise ValueError("Receipt identity/revision mismatch")
    if proof.artifact_hash != content_hash(monitor):
        raise ValueError("Monitor changed after validation")
    if runtime_revision is not None and proof.runtime_revision != runtime_revision:
        raise ValueError("Receipt uses a different pinned runtime")
    return {"status": "verified", "checked_at": proof.checked_at.isoformat(),
            "job_count": proof.job_count, "warnings": proof.warnings}
