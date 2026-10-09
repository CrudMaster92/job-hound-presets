"""Strict provider contract for AI-authored scraper recipes.

Runtime recipes intentionally use dictionaries for request and extraction
configuration. Strict structured-output providers cannot generate arbitrary
object keys, so the AI boundary represents those dictionaries as bounded entry
lists and converts them back before the runtime contract validates the recipe.
"""

from __future__ import annotations

import json
from typing import Literal, TypeVar

from pydantic import Field, field_validator

from .models import PaginationConfig, ScraperRecipe, ScraperStrategy, StrictModel


Scalar = str | int | float | bool
SelectorKey = Literal[
    "item", "title", "link", "location", "description", "employment_type",
    "posted_date", "remote_mode", "salary", "salary_min", "salary_max",
    "salary_currency", "salary_period",
]
MappingKey = Literal[
    "items", "source_id", "title", "location", "url", "description",
    "posted_date", "employment_type", "remote_mode", "salary_min", "salary_max",
    "salary_currency", "salary_period",
]


class StringEntry(StrictModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(max_length=20_000)


class ScalarEntry(StrictModel):
    key: str = Field(min_length=1, max_length=200)
    value: Scalar


class SelectorEntry(StrictModel):
    key: SelectorKey
    value: str = Field(max_length=20_000)


class MappingEntry(StrictModel):
    key: MappingKey
    value: str = Field(max_length=20_000)


Entry = TypeVar("Entry", StringEntry, ScalarEntry)


def _unique_entries(entries: list[Entry]) -> list[Entry]:
    keys = [entry.key for entry in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("entry keys must be unique")
    return entries


def _entry_dict(entries: list[Entry]) -> dict:
    return {entry.key: entry.value for entry in entries}


class RequestProposal(StrictModel):
    url: str
    method: Literal["GET", "POST"]
    headers: list[StringEntry]
    params: list[ScalarEntry]
    json_body_json: str | None = Field(
        description="A JSON-encoded object for the request body, or null for no body",
    )
    timeout_seconds: float
    max_response_bytes: int

    _unique_headers = field_validator("headers")(_unique_entries)
    _unique_params = field_validator("params")(_unique_entries)


class ScraperRecipeProposal(StrictModel):
    """Provider-safe representation converted into ``ScraperRecipe`` locally."""

    version: Literal[1]
    company: str
    careers_url: str
    strategy: ScraperStrategy
    allowed_hosts: list[str]
    request: RequestProposal
    pagination: PaginationConfig
    selectors: list[SelectorEntry]
    mapping: list[MappingEntry]
    metadata: list[ScalarEntry]

    _unique_selectors = field_validator("selectors")(_unique_entries)
    _unique_mapping = field_validator("mapping")(_unique_entries)
    _unique_metadata = field_validator("metadata")(_unique_entries)

    def to_recipe(self) -> ScraperRecipe:
        body = None
        if self.request.json_body_json is not None:
            try:
                body = json.loads(self.request.json_body_json)
            except json.JSONDecodeError as exc:
                raise ValueError("request json_body_json must contain valid JSON") from exc
            if not isinstance(body, dict):
                raise ValueError("request json_body_json must encode an object")
        return ScraperRecipe.model_validate({
            "version": self.version,
            "company": self.company,
            "careers_url": self.careers_url,
            "strategy": self.strategy,
            "allowed_hosts": self.allowed_hosts,
            "request": {
                "url": self.request.url,
                "method": self.request.method,
                "headers": _entry_dict(self.request.headers),
                "params": _entry_dict(self.request.params),
                "json_body": body,
                "timeout_seconds": self.request.timeout_seconds,
                "max_response_bytes": self.request.max_response_bytes,
            },
            "pagination": self.pagination.model_dump(mode="json"),
            "selectors": _entry_dict(self.selectors),
            "mapping": _entry_dict(self.mapping),
            "metadata": _entry_dict(self.metadata),
        })


def compile_recipe_proposal(payload: dict) -> dict:
    proposal = ScraperRecipeProposal.model_validate(payload)
    return proposal.to_recipe().model_dump(mode="json")
