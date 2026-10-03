"""Bounded proposal contracts shared by UI, CLI, MCP and trusted validation."""
from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from ..scrapers.models import ScraperRecipe

REPOSITORY = "CrudMaster92/job-hound-presets"
WORKSPACE_REPOSITORY = "CrudMaster92/job-hound-workspace"
SHA_PATTERN = r"^[a-f0-9]{40}$"
ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
MAX_DOCUMENT_BYTES = 512_000
MAX_FIXTURE_BYTES = 128_000
SENSITIVE_KEYS = {"authorization", "cookie", "proxy-authorization", "access_token", "refresh_token",
                  "password", "credentials", "personal_criteria", "resume", "application_history",
                  "api_key", "apikey", "api-key", "x-api-key", "client_secret", "secret", "token"}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def safe_public_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Use a credential-free public HTTPS URL without fragments")
    if parsed.port not in {None, 443} or host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Private hosts and non-HTTPS ports are not public contribution sources")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private addresses are not public contribution sources")
    if any(key.casefold() in SENSITIVE_KEYS | {"token", "api_key", "key", "signature"} for key, _ in parse_qsl(parsed.query)):
        raise ValueError("URLs cannot carry credentials")
    return value


def public_data(value: Any) -> None:
    if isinstance(value, dict):
        if any(str(key).strip().casefold() in SENSITIVE_KEYS for key in value):
            raise ValueError("Contribution data contains a forbidden private or credential field")
        for item in value.values():
            public_data(item)
    elif isinstance(value, list):
        for item in value:
            public_data(item)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Fixture(Contract):
    source_url: str
    fetched_at: AwareDatetime
    payload: dict[str, Any] | list[Any] | str

    _url = field_validator("source_url")(safe_public_url)

    @model_validator(mode="after")
    def bounded(self):
        if self.fetched_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Fixture fetch time cannot be in the future")
        if len(canonical_bytes(self.payload)) > MAX_FIXTURE_BYTES:
            raise ValueError("Trim the public fixture to at most 128 KB")
        public_data(self.payload)
        return self


class OwnershipEvidence(Contract):
    company_url: str
    explanation: str = Field(min_length=20, max_length=1500)
    shared_feed: bool = False
    representative_urls: list[str] = Field(min_length=1, max_length=10)

    _url = field_validator("company_url")(safe_public_url)

    @field_validator("representative_urls")
    @classmethod
    def urls(cls, values):
        return [safe_public_url(value) for value in values]


class Proposal(Contract):
    base_commit: str = Field(pattern=SHA_PATTERN)
    company: dict[str, Any]
    monitor: dict[str, Any]
    collections: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    fixture: Fixture
    ownership: OwnershipEvidence

    @model_validator(mode="after")
    def bounded(self):
        value = self.model_dump(mode="json")
        if len(canonical_bytes(value)) > MAX_DOCUMENT_BYTES:
            raise ValueError("Contribution exceeds 512 KB")
        public_data(value)
        return self


class Prepare(Contract):
    request_id: str = Field(min_length=8, max_length=120)
    human_requested: Literal[True]
    public_submission: Literal[True]
    proposal: Proposal


class Submission(Contract):
    repository: Literal["CrudMaster92/job-hound-presets"] = REPOSITORY
    pr_number: int = Field(ge=1)
    head_commit: str = Field(pattern=SHA_PATTERN)


def validate_documents(proposal: Proposal) -> dict[str, Any]:
    """Use the catalog's actual schemas; emit authored data, never generated files."""
    from pathlib import Path
    from jsonschema import Draft202012Validator, FormatChecker
    root = Path(__file__).parent / "schemas"
    documents = [(proposal.company, "jobhound-company-v1.schema.json"),
                 (proposal.monitor, "jobhound-monitor-v1.schema.json")]
    documents.extend((item, "jobhound-collection-v1.schema.json") for item in proposal.collections)
    for document, name in documents:
        schema = json.loads((root / name).read_text(encoding="utf-8"))
        if name == "jobhound-monitor-v1.schema.json":
            definitions = json.loads((root / "jobhound-preset-v1.schema.json").read_text(encoding="utf-8"))["$defs"]
            schema["properties"]["recipe"] = definitions["recipe"]
            schema["$defs"] = definitions
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    company, monitor = proposal.company, proposal.monitor
    recipe = ScraperRecipe.model_validate(monitor["recipe"])
    if monitor["company_id"] != company["id"] or recipe.company != company["name"]:
        raise ValueError("Monitor and recipe must belong to the proposed company identity")
    if recipe.careers_url.rstrip("/") != monitor["careers_url"].rstrip("/"):
        raise ValueError("Monitor and recipe careers URLs differ")
    safe_public_url(company["website_url"])
    if company.get("logo_url"):
        safe_public_url(company["logo_url"])
    safe_public_url(recipe.careers_url)
    safe_public_url(recipe.request.url)
    if proposal.fixture.source_url != recipe.request.url:
        raise ValueError("Fixture source must be the recipe's public request URL")
    if proposal.ownership.company_url != company["website_url"]:
        raise ValueError("Ownership evidence must identify the company's public website")
    if proposal.ownership.shared_feed and not recipe.source_filter:
        raise ValueError("A shared feed requires explicit employer ownership predicates")
    for host in recipe.allowed_hosts:
        safe_public_url(f"https://{host}/")
    collection_ids = [item["id"] for item in proposal.collections]
    if len(collection_ids) != len(set(collection_ids)):
        raise ValueError("Duplicate collection updates")
    for collection in proposal.collections:
        member = next((item for item in collection["companies"] if item["company_id"] == company["id"]), None)
        if member is None or (member.get("monitor_ids") is not None and monitor["id"] not in member["monitor_ids"]):
            raise ValueError("Collection must reference the proposed company and monitor")
    # Author sandbox evidence never claims trusted live verification.
    monitor = {**monitor, "verification": {"status": "unverified", "checked_at": None,
               "job_count": None, "warnings": ["Awaiting trusted JobHound runtime validation."]}}
    files = {f"companies/{company['id']}/company.json": company,
             f"companies/{company['id']}/monitors/{monitor['id']}.json": monitor,
             f"contributions/{monitor['id']}/proposal.json": {**proposal.model_dump(mode="json"), "monitor": monitor}}
    files.update({f"collections/{item['id']}.json": item for item in proposal.collections})
    return {"files": files, "monitor": monitor, "company": company,
            "proposal_hash": content_hash(files), "runtime_verified": False,
            "warnings": ["Offline parsing is not live verification.", "the maintainer must review employer ownership before merging."],
            "public_collection_eligible": recipe.strategy.value != "playwright"}
