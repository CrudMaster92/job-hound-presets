"""Strict public contracts used by the JobHound scraper runtime."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ScraperStrategy(str, Enum):
    ASHBY = "ashby"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    SMARTRECRUITERS = "smartrecruiters"
    WORKDAY = "workday"
    JOBVITE = "jobvite"
    JSON_LD = "json_ld"
    GENERIC_JSON = "generic_json"
    GENERIC_HTML = "generic_html"
    PLAYWRIGHT = "playwright"


class RemoteMode(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


SalaryPeriod = Literal["hour", "day", "week", "month", "year"]

SELECTOR_FIELDS = {
    "item", "title", "link", "location", "description", "employment_type",
    "posted_date", "remote_mode", "salary", "salary_min", "salary_max",
    "salary_currency", "salary_period",
}
MAPPING_FIELDS = {
    "items", "source_id", "title", "location", "url", "description",
    "posted_date", "employment_type", "remote_mode", "salary_min", "salary_max",
    "salary_currency", "salary_period",
}


def canonicalize_url(value: str, *, strip_trailing_slash: bool = True) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    if strip_trailing_slash:
        path = path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), host + port, path, parsed.query, ""))


class JobRecord(StrictModel):
    company: str = Field(min_length=1, max_length=300)
    source_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    location: str = Field(default="Unspecified", max_length=500)
    remote_mode: RemoteMode = RemoteMode.UNKNOWN
    employment_type: str | None = Field(default=None, max_length=200)
    posted_date: date | None = None
    description: str = Field(default="", max_length=500_000)
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = Field(default=None, max_length=8)
    salary_period: SalaryPeriod | None = None
    canonical_url: str
    source_url: str
    source: str = Field(min_length=1, max_length=100)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("canonical_url", "source_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonicalize_url(value)

    @field_validator("salary_min", "salary_max")
    @classmethod
    def non_negative_salary(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("salary must be non-negative")
        return value

    @model_validator(mode="after")
    def salary_order(self) -> "JobRecord":
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min cannot exceed salary_max")
        return self

    @staticmethod
    def stable_id(*parts: Any) -> str:
        value = "\x1f".join(str(part or "").strip().casefold() for part in parts)
        return sha256(value.encode("utf-8")).hexdigest()[:32]


class RequestConfig(StrictModel):
    url: str
    method: Literal["GET", "POST"] = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    timeout_seconds: float = Field(default=15, ge=1, le=30)
    max_response_bytes: int = Field(default=5_000_000, ge=1_024, le=20_000_000)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonicalize_url(value, strip_trailing_slash=False)

    @field_validator("headers")
    @classmethod
    def safe_headers(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = {"authorization", "cookie", "proxy-authorization"}
        if forbidden.intersection(key.casefold() for key in value):
            raise ValueError("credential-bearing headers are not allowed in recipes")
        return value


class PaginationConfig(StrictModel):
    kind: Literal["none", "offset", "page", "next_link"] = "none"
    parameter: str | None = None
    page_size_parameter: str | None = None
    page_size: int = Field(default=100, ge=1, le=500)
    max_pages: int = Field(default=10, ge=1, le=100)
    next_path: str | None = None


class SourcePredicate(StrictModel):
    phase: Literal["listing", "detail"] = "listing"
    path: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
    operator: Literal["equals_ci", "contains_ci", "html_label_equals_ci", "array_object_field_equals_ci"] = "equals_ci"
    values: list[str] = Field(min_length=1, max_length=20)
    label: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("values")
    @classmethod
    def clean_values(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in values:
            value = " ".join(raw.split()).strip()
            if not value:
                raise ValueError("source predicate values cannot be empty")
            if value.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(value)
        return cleaned

    @model_validator(mode="after")
    def label_matches_operator(self) -> "SourcePredicate":
        needs_label = self.operator in {"html_label_equals_ci", "array_object_field_equals_ci"}
        if needs_label != bool(self.label):
            raise ValueError("label is required only for label-based predicate operators")
        return self


class SourceFilter(StrictModel):
    title_contains_any: list[str] | None = Field(default=None, min_length=1, max_length=20)
    predicate_match: Literal["all", "any"] = "all"
    predicates: list[SourcePredicate] = Field(default_factory=list, max_length=20)

    @field_validator("title_contains_any")
    @classmethod
    def clean_titles(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        cleaned: list[str] = []
        for raw in values:
            value = " ".join(raw.split()).strip()
            if not value:
                raise ValueError("source filter title terms cannot be empty")
            if value.casefold() not in {item.casefold() for item in cleaned}:
                cleaned.append(value)
        return cleaned

    @model_validator(mode="after")
    def has_filter(self) -> "SourceFilter":
        if not self.title_contains_any and not self.predicates:
            raise ValueError("source filter requires title terms or predicates")
        return self


class ScraperRecipe(StrictModel):
    version: Literal[1] = 1
    company: str = Field(min_length=1, max_length=300)
    careers_url: str
    strategy: ScraperStrategy
    allowed_hosts: list[str] = Field(min_length=1, max_length=10)
    request: RequestConfig
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    source_key: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    source_filter: SourceFilter | None = None
    selectors: dict[str, str] = Field(default_factory=dict)
    mapping: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)

    @field_validator("careers_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonicalize_url(value)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, value: list[str]) -> list[str]:
        hosts = []
        for host in value:
            clean = host.strip().lower().rstrip(".")
            if not clean or "/" in clean or ":" in clean:
                raise ValueError("allowed_hosts entries must be hostnames")
            if clean not in hosts:
                hosts.append(clean)
        return hosts

    @field_validator("selectors")
    @classmethod
    def known_selector_fields(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(value) - SELECTOR_FIELDS)
        if unknown:
            raise ValueError(f"unknown selector fields: {', '.join(unknown)}")
        if any(not selector.strip() for selector in value.values()):
            raise ValueError("selectors cannot be empty")
        return {key: selector.strip() for key, selector in value.items()}

    @field_validator("mapping")
    @classmethod
    def known_mapping_fields(cls, value: dict[str, str]) -> dict[str, str]:
        unknown = sorted(set(value) - MAPPING_FIELDS)
        if unknown:
            raise ValueError(f"unknown mapping fields: {', '.join(unknown)}")
        if any(not path.strip() for path in value.values()):
            raise ValueError("mapping paths cannot be empty")
        return {key: path.strip() for key, path in value.items()}

    @model_validator(mode="after")
    def request_host_is_allowed(self) -> "ScraperRecipe":
        host = (urlsplit(self.request.url).hostname or "").lower()
        if host not in self.allowed_hosts:
            raise ValueError("request URL host must be explicitly allowed")
        return self


class DetectionResult(StrictModel):
    strategy: ScraperStrategy
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ScrapeResult(StrictModel):
    jobs: list[JobRecord]
    strategy: ScraperStrategy
    pages_fetched: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    complete: bool = True


class ValidationReport(StrictModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    job_count: int = Field(default=0, ge=0)
    coverage: dict[str, int] = Field(default_factory=dict)
