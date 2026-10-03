"""Bounded HTTP helpers with explicit per-recipe host confinement."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

import httpx

from ..external_http import external_trust_env, external_client_kwargs
from .models import RequestConfig


class ScraperNetworkError(RuntimeError):
    pass


def _validate_target(url: str, allowed_hosts: list[str], *, resolve_dns: bool = True) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host not in allowed_hosts:
        raise ScraperNetworkError(f"request target is outside allowed hosts: {url}")
    if parsed.username or parsed.password:
        raise ScraperNetworkError("request targets cannot contain credentials")
    if not resolve_dns:
        return
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            addresses = list({ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or 443)})
        except (OSError, ValueError) as exc:
            raise ScraperNetworkError("request target could not be resolved") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ScraperNetworkError("request target must resolve only to public internet addresses; synthetic/private workspace DNS remains blocked even in environment proxy mode")


def bounded_request(
    config: RequestConfig,
    allowed_hosts: list[str],
    client: httpx.Client | None = None,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    max_redirects: int = 3,
) -> httpx.Response:
    owned = client is None
    active = client or httpx.Client(follow_redirects=False, **external_client_kwargs())
    url = config.url
    configured_params = dict(config.params)
    if params is not None:
        configured_params.update(params)
    try:
        for _ in range(max_redirects + 1):
            # An injected client is the runtime's test/adapter seam (normally a
            # MockTransport). Real requests retain DNS/IP confinement and host confinement,
            # including when the configured workspace proxy is enabled.
            _validate_target(url, allowed_hosts, resolve_dns=owned or bool(getattr(active, "_jobhound_resolve_dns", False)))
            request_url = url
            request_params = None
            if url == config.url:
                parsed = urlsplit(url)
                merged_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
                merged_params.update(configured_params)
                request_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
                request_params = merged_params or None
            response = active.request(
                config.method,
                request_url,
                headers={"User-Agent": "JobHound/1.0", "Accept": "application/json,text/html;q=0.9", **config.headers},
                params=request_params,
                json=json_body if json_body is not None else config.json_body,
                timeout=config.timeout_seconds,
                follow_redirects=False,
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise ScraperNetworkError("redirect response omitted Location")
                url = urljoin(str(response.url), location)
                continue
            response.raise_for_status()
            declared = int(response.headers.get("content-length", "0") or 0)
            if declared > config.max_response_bytes or len(response.content) > config.max_response_bytes:
                raise ScraperNetworkError("response exceeds recipe size limit")
            return response
        raise ScraperNetworkError("too many redirects")
    except httpx.HTTPError as exc:
        raise ScraperNetworkError(str(exc)) from exc
    finally:
        if owned:
            active.close()
