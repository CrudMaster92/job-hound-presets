"""Normalization shared by deterministic adapters."""

from __future__ import annotations

import re
from datetime import date, datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import JobRecord, RemoteMode


_EMPLOYMENT_LABELS = {
    "fulltime": "Full-time",
    "full time": "Full-time",
    "parttime": "Part-time",
    "part time": "Part-time",
    "temporary": "Temporary",
    "temp": "Temporary",
    "contract": "Contract",
    "contractor": "Contract",
    "fixed term": "Fixed-term",
    "permanent": "Permanent",
    "intern": "Internship",
    "internship": "Internship",
    "seasonal": "Seasonal",
    "casual": "Casual",
}


def plain_text(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(timestamp).date()
        except (ValueError, OSError, OverflowError):
            return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None


def infer_remote(location: str, title: str = "", description: str = "") -> RemoteMode:
    haystack = f"{location} {title} {description[:1000]}".casefold()
    if "hybrid" in haystack:
        return RemoteMode.HYBRID
    if re.search(r"\b(remote|work from home|distributed)\b", haystack):
        return RemoteMode.REMOTE
    if location.strip() and location.casefold() not in {"unspecified", "multiple locations"}:
        return RemoteMode.ONSITE
    return RemoteMode.UNKNOWN


def first(value: Any, *paths: str) -> Any:
    for path in paths:
        current = value
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                current = None
                break
        if current not in (None, "", []):
            return current
    return None


def normalize_employment_type(value: Any, *, title: str = "", description: str = "") -> str | None:
    """Return a concise human-readable employment label, inferring only explicit terms."""
    values = value if isinstance(value, list) else [value]
    labels: list[str] = []
    for item in values:
        text = plain_text(item)
        if not text:
            continue
        words = re.sub(r"(?<=[a-z])(?=[A-Z])|[_-]+", " ", text).casefold()
        words = re.sub(r"\s+", " ", words).strip()
        label = _EMPLOYMENT_LABELS.get(words, text)
        if label not in labels:
            labels.append(label)
    if not labels:
        haystack = f"{title} {description[:2500]}"
        patterns = (
            (r"\bfixed[- ]term\b", "Fixed-term"),
            (r"\btemporary\b|\btemp(?:orary)? position\b", "Temporary"),
            (r"\bcontract(?:or)?\b", "Contract"),
            (r"\bseasonal\b", "Seasonal"),
            (r"\bintern(?:ship)?\b", "Internship"),
            (r"\bpermanent\b", "Permanent"),
            (r"\bpart[- ]time\b", "Part-time"),
            (r"\bfull[- ]time\b", "Full-time"),
            (r"\bcasual\b", "Casual"),
        )
        labels = [label for pattern, label in patterns if re.search(pattern, haystack, re.IGNORECASE)]
    return ", ".join(dict.fromkeys(labels)) or None


def _salary_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = plain_text(value).replace(",", "")
    match = re.search(r"(?:CA\$|US\$|[$€£])?\s*(\d+(?:\.\d+)?)\s*([kK])?", text)
    if not match:
        return None
    number = float(match.group(1))
    return number * 1000 if match.group(2) else number


def normalize_salary_period(value: Any = None, *texts: Any) -> str | None:
    explicit = plain_text(value).casefold().replace("_", " ").strip()
    aliases = {
        "hour": "hour", "hourly": "hour", "hr": "hour",
        "day": "day", "daily": "day",
        "week": "week", "weekly": "week", "wk": "week",
        "month": "month", "monthly": "month", "mo": "month",
        "year": "year", "yearly": "year", "annual": "year", "annually": "year",
        "annum": "year", "yr": "year",
    }
    if explicit:
        normalized = re.sub(r"^per\s+", "", explicit).strip(" /-")
        if normalized in aliases:
            return aliases[normalized]
    haystack = " ".join(plain_text(item) for item in texts if item)[:20_000]
    for pattern, period in (
        (r"\b(?:per\s+hour|hourly)\b|/(?:hr|hour)\b", "hour"),
        (r"\b(?:per\s+day|daily)\b|/day\b", "day"),
        (r"\b(?:per\s+week|weekly)\b|/(?:wk|week)\b", "week"),
        (r"\b(?:per\s+month|monthly)\b|/(?:mo|month)\b", "month"),
        (r"\b(?:per\s+(?:year|annum)|annual(?:ly)?)\b|/(?:yr|year)\b", "year"),
    ):
        if re.search(pattern, haystack, re.IGNORECASE):
            return period
    return None


def _salary_amount_context(description: str, *amounts: float | None) -> str:
    """Return text near a selected salary amount, excluding unrelated cadence phrases."""
    for amount in amounts:
        if amount is None:
            continue
        whole = int(amount) if float(amount).is_integer() else amount
        needles = [f"{whole:,}", str(whole)]
        if float(amount) >= 1_000:
            needles.append(f"{float(amount) / 1_000:g}k")
        for needle in needles:
            match = re.search(re.escape(needle), description, re.IGNORECASE)
            if match:
                return description[max(0, match.start() - 300):min(len(description), match.end() + 300)]
    return ""


def infer_salary(description: str, *, require_context: bool = True) -> tuple[float | None, float | None, str | None]:
    """Extract an explicitly labelled monetary range without guessing its cadence."""
    text = description[:20_000]
    currency_match = re.search(r"\b(CAD|USD|EUR|GBP)\b", text, re.IGNORECASE)
    currency_match = currency_match or re.search(r"CA\$|US\$|[€£$]", text, re.IGNORECASE)
    if not currency_match:
        return None, None, None
    token = currency_match.group(0).upper()
    currency = token if token in {"CAD", "USD", "EUR", "GBP"} else {
        "CA$": "CAD", "US$": "USD", "€": "EUR", "£": "GBP",
    }.get(token)
    pattern = re.compile(
        r"(?:CAD|USD|EUR|GBP|CA\$|US\$|[$€£])\s*"
        r"(\d[\d,]*(?:\.\d+)?\s*[kK]?)"
        r"(?:\s*(?:-|\u2013|\u2014|to)\s*(?:CAD|USD|EUR|GBP|CA\$|US\$|[$€£])?\s*"
        r"(\d[\d,]*(?:\.\d+)?\s*[kK]?))?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        # Do not truncate a revenue/quota amount such as '$2M' to salary '2'.
        # Unsupported amount suffixes must remain unknown rather than guessed.
        if not match.group(0)[-1].isspace() and re.match(r"[a-zA-Z0-9]|[,.]\d", text[match.end():]):
            continue
        if require_context:
            context = text[max(0, match.start() - 100):min(len(text), match.end() + 100)]
            before = re.split(r"[.;!?]\s+", text[max(0, match.start() - 45):match.start()])[-1]
            after = re.split(r"[.;!?]\s+", text[match.end():min(len(text), match.end() + 45)])[0]
            nearby = before + match.group(0) + after
            if re.search(r"\b(?:quotas?|revenue|ARR|stipend|allowance|funding|sales target|budget)\b", nearby, re.IGNORECASE):
                continue
            if not re.search(
                r"\b(?:salary|compensation|wage|base pay|pay range|paying|annual(?:ly)?|hourly|per (?:year|hour|annum))\b|/(?:yr|year|hr|hour)\b",
                context, re.IGNORECASE,
            ):
                continue
        low = _salary_number(match.group(1))
        high = _salary_number(match.group(2)) if match.group(2) else low
        return low, high, currency
    return None, None, None


def make_job(
    *, company: str, source: str, source_id: Any, title: Any, location: Any,
    url: Any, base_url: str, description: Any = "", posted_date: Any = None,
    employment_type: Any = None, salary_min: Any = None, salary_max: Any = None,
    currency: Any = None, salary_period: Any = None, remote_mode: Any = None,
) -> JobRecord:
    title_text = plain_text(title)
    location_text = plain_text(location) or "Unspecified"
    description_text = plain_text(description)
    resolved_url = urljoin(base_url, str(url or ""))
    identity = str(source_id or "").strip() or JobRecord.stable_id(company, title_text, location_text, resolved_url)
    try:
        mode = RemoteMode(str(remote_mode).casefold()) if remote_mode else infer_remote(location_text, title_text, description_text)
    except ValueError:
        mode = infer_remote(location_text, title_text, description_text)
    salary_field_min, salary_field_max, salary_field_currency = (
        infer_salary(plain_text(salary_min), require_context=False)
        if salary_max in (None, "") and isinstance(salary_min, str)
        else (None, None, None)
    )
    explicit_min = salary_field_min if salary_field_min is not None else _salary_number(salary_min)
    explicit_max = salary_field_max if salary_field_max is not None else _salary_number(salary_max)
    inferred_min, inferred_max, inferred_currency = infer_salary(description_text)
    normalized_min = explicit_min if explicit_min is not None else inferred_min
    normalized_max = explicit_max if explicit_max is not None else inferred_max
    if normalized_min is not None and normalized_max is None:
        normalized_max = normalized_min
    if normalized_max is not None and normalized_min is None:
        normalized_min = normalized_max
    period_texts = [salary_min, salary_max]
    if inferred_min is not None or inferred_max is not None:
        period_texts.append(_salary_amount_context(description_text, inferred_min, inferred_max))
    normalized_period = (
        normalize_salary_period(salary_period, *period_texts)
        if normalized_min is not None or normalized_max is not None
        else None
    )
    return JobRecord(
        company=company,
        source_id=identity,
        title=title_text,
        location=location_text,
        remote_mode=mode,
        employment_type=normalize_employment_type(employment_type, title=title_text, description=description_text),
        posted_date=parse_date(posted_date),
        description=description_text,
        salary_min=normalized_min,
        salary_max=normalized_max,
        salary_currency=plain_text(currency).upper() or salary_field_currency or inferred_currency,
        salary_period=normalized_period,
        canonical_url=resolved_url,
        source_url=resolved_url,
        source=source,
    )
