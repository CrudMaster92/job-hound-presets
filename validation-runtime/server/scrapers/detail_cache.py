"""Small persistent detail-cache rules, shared by bounded deterministic scraper batches."""
import hashlib
import json
from .models import JobRecord

SUCCESS_TTL = 24 * 60 * 60
RETRY_BASE = 15 * 60
RETRY_MAX = 6 * 60 * 60


def signature(job, recipe):
    # Relative dates and inferred salaries change without changing the posting.
    listing = job.model_dump(mode="json", include={
        "source_id", "canonical_url", "title", "location", "remote_mode", "employment_type",
    })
    value = {"listing": listing, "strategy": recipe.strategy.value, "company": recipe.company,
             "request": recipe.request.url, "allowed_hosts": recipe.allowed_hosts,
             "ownership": recipe.source_filter.model_dump(mode="json") if recipe.source_filter else None}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def timestamp(prior, key):
    if not isinstance(prior, dict):
        return 0.0
    try:
        return max(0.0, float(prior.get(key) or 0))
    except (TypeError, ValueError):
        return 0.0


def restore_missing(listing, prior):
    try:
        saved = JobRecord.model_validate(prior["job"])
    except (KeyError, ValueError, TypeError):
        return listing
    if (saved.source_id, prior.get("job_listing_url", saved.canonical_url), saved.company) != (listing.source_id, listing.canonical_url, listing.company):
        return listing
    fields = ("description", "employment_type", "salary_min", "salary_max", "salary_currency", "salary_period")
    update = {key: getattr(saved, key) for key in fields
              if getattr(listing, key) in (None, "") and getattr(saved, key) not in (None, "")}
    return listing.model_copy(update=update)


def failure(prior, current_signature, now):
    try:
        count = max(0, min(20, int(prior.get("failures", 0)))) + 1
    except (TypeError, ValueError):
        count = 1
    return {**prior, "signature": current_signature, "attempted_at": now, "failures": count,
            "next_attempt_at": now + min(RETRY_MAX, RETRY_BASE * (2 ** min(count - 1, 10)))}
