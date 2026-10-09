"""Scheduler-facing compatibility hooks.

These functions deliberately create/repair declarative recipes only.  A future
Codex integration can propose the same schema without changing the scheduler.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from .detection import build_recipe
from .http import bounded_request
from .models import RequestConfig, ScraperRecipe, ScraperStrategy, ValidationReport
from .runtime import _notify, run_scraper, validate_recipe


def _company_value(company: Any, *names: str) -> Any:
    for name in names:
        if isinstance(company, dict) and company.get(name) is not None:
            return company[name]
        value = getattr(company, name, None)
        if value is not None:
            return value
    return None


def build_scraper(company: Any, progress=None, *, client: httpx.Client | None = None) -> dict[str, Any]:
    name = str(_company_value(company, "name", "company") or "Unknown company")
    url = _company_value(company, "careers_url", "url")
    if not url:
        raise ValueError("company must provide careers_url")
    _notify(progress, "detecting", "Detecting career platform", 5)
    recipe = build_recipe(name, str(url))
    evidence = ""
    if recipe.strategy == ScraperStrategy.GENERIC_HTML:
        host = (urlsplit(str(url)).hostname or "").lower()
        response = bounded_request(RequestConfig(url=str(url)), [host], client)
        html = response.text
        recipe = build_recipe(name, str(url), html=html)
        soup = BeautifulSoup(html, "html.parser")
        for element in soup.select("script:not([type='application/ld+json']),style,noscript,svg,iframe"):
            element.decompose()
        evidence = str(soup)[:120_000]
    _notify(progress, "validating", f"Validating {recipe.strategy.value} recipe", 30)
    if recipe.strategy in {ScraperStrategy.GENERIC_HTML, ScraperStrategy.PLAYWRIGHT}:
        report = ValidationReport(valid=True, warnings=["Recipe requires Codex-assisted selector compilation"])
    else:
        report = validate_recipe(recipe, client=client, require_jobs=False)
    _notify(progress, "complete", "Scraper recipe built", 100)
    return {
        "recipe": recipe.model_dump(mode="json"),
        "validation": report.model_dump(mode="json"),
        "source": recipe.strategy.value,
        "evidence": evidence,
    }


def repair_scraper(
    company: Any,
    recipe: ScraperRecipe | dict,
    diagnostics: Any = None,
    progress=None,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Re-detect a deterministic recipe and validate before returning it.

    The old recipe is never mutated.  Callers decide whether to activate the
    proposed replacement based on the returned validation report.
    """
    _notify(progress, "repairing", "Re-detecting career platform", 10)
    name = str(_company_value(company, "name", "company") or getattr(recipe, "company", "Unknown company"))
    url = _company_value(company, "careers_url", "url")
    if not url:
        current = recipe if isinstance(recipe, ScraperRecipe) else ScraperRecipe.model_validate(recipe)
        url = current.careers_url
    replacement = build_recipe(name, str(url))
    report = validate_recipe(replacement, client=client, require_jobs=False)
    _notify(progress, "complete" if report.valid else "failed", "Repair candidate validated" if report.valid else "Repair candidate failed validation", 100)
    return {
        "recipe": replacement.model_dump(mode="json"),
        "validation": report.model_dump(mode="json"),
        "source": replacement.strategy.value,
        "diagnostics_received": diagnostics is not None,
    }
