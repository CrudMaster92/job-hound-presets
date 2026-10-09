"""Versioned public feed contracts; explicit allowlists prevent data leakage."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

FORMAT = "jobhound-public-jobs"
VERSION = 1
STALE_HOURS = 36
EXPIRE_DAYS = 7


def timestamp(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Public job URLs must be credential-free HTTPS URLs")
    return urlunsplit(("https", parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


def job_id(company_id: str, canonical_url: str) -> str:
    # Monitor-independent identity collapses the same opening across collections
    # and overlapping company feeds without merging unrelated employers.
    identity = public_url(canonical_url).rstrip("/")
    return "job_" + digest(f"{company_id}\n{identity}".encode())[:32]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactRef(Contract):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    count: int = Field(ge=0)


class PublicJob(Contract):
    id: str
    company_id: str
    company_name: str
    collection_ids: list[str] = Field(default_factory=list)
    monitor_ids: list[str] = Field(default_factory=list)
    title: str
    location: str
    work_mode: Literal["onsite", "hybrid", "remote", "unknown"] = "unknown"
    employment_type: str | None = None
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    description: str = ""
    source_url: str
    source_job_id: str
    posted_at: str | None = None
    first_seen_at: str
    last_seen_at: str
    status: Literal["active", "closed", "expired"] = "active"

    _source_url = field_validator("source_url")(public_url)


class PublicSource(Contract):
    id: str
    company_id: str
    company_name: str
    revision: int
    artifact_hash: str | None = None
    status: Literal["complete", "partial", "failed", "excluded"]
    last_attempt_at: str | None = None
    last_success_at: str | None = None
    complete: bool = False
    job_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class Collection(Contract):
    id: str
    name: str


class FeedManifest(Contract):
    format: Literal["jobhound-public-jobs"] = FORMAT
    version: Literal[1] = VERSION
    generation: str
    generated_at: str
    catalog_commit: str
    total_jobs: int
    active_jobs: int
    stale_after_hours: int = STALE_HOURS
    expire_after_days: int = EXPIRE_DAYS
    collections: list[Collection]
    sources: list[PublicSource]
    search_pages: list[ArtifactRef]
    detail_pages: list[ArtifactRef]
