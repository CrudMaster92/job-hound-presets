"""Explicit workspace egress selection; loopback clients never use this policy."""
from __future__ import annotations
import os
import ipaddress
import ssl
from urllib.parse import urlsplit

import httpx

PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def external_trust_env() -> bool:
    mode = os.getenv("JOBHOUND_EXTERNAL_NETWORK_MODE", "direct")
    if mode not in {"direct", "environment"}:
        raise ValueError("JOBHOUND_EXTERNAL_NETWORK_MODE must be direct or environment")
    return mode == "environment"


def no_proxy_patterns(value: str) -> list[str]:
    """Normalize ambient bypass patterns, including Muse's *[::1].

    Invalid entries are ignored (traffic continues through the approved proxy),
    rather than mutating process-global environment or disabling TLS.
    """
    patterns = []
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        if item == "*":
            return ["all://"]
        candidate = item.lstrip("*")
        literal = candidate.strip("[]")
        try:
            address = ipaddress.ip_address(literal)
            patterns.append(f"all://[{address}]" if address.version == 6 else f"all://{address}")
            continue
        except ValueError:
            pass
        try:
            parsed = urlsplit(candidate if "://" in candidate else "http://" + candidate)
            host = parsed.hostname or ""
            port = parsed.port
            if not host or parsed.username or parsed.password or parsed.path not in {"", "/"}:
                continue
            if ":" in host:
                address = ipaddress.ip_address(host)
                host = f"[{address}]"
            elif host.startswith("."):
                host = "*" + host
            elif item.startswith("*"):
                host = "*" + host
            if any(char.isspace() for char in host) or "/" in host:
                continue
            patterns.append("all://" + host + (f":{port}" if port else ""))
        except ValueError:
            continue
    return list(dict.fromkeys(patterns))


def external_client_kwargs(*, transport=None, asynchronous: bool = False) -> dict:
    """Explicit ambient egress with TLS, without HTTPX's malformed IPv6 proxy parser."""
    if transport is not None or not external_trust_env():
        return {"trust_env": False, **({"transport": transport} if transport is not None else {})}
    context = ssl.create_default_context(cafile=os.getenv("SSL_CERT_FILE") or None,
                                         capath=os.getenv("SSL_CERT_DIR") or None)
    transport_type = httpx.AsyncHTTPTransport if asynchronous else httpx.HTTPTransport
    mounts = {}
    try:
        all_proxy = os.getenv("all_proxy", os.getenv("ALL_PROXY", ""))
        for scheme in ("http", "https"):
            proxy = os.getenv(f"{scheme}_proxy", os.getenv(f"{scheme.upper()}_PROXY", "")) or all_proxy
            if proxy:
                mounts[f"{scheme}://"] = transport_type(proxy=proxy, verify=context, trust_env=False)
        bypass = os.getenv("no_proxy", os.getenv("NO_PROXY", ""))
        mounts.update({pattern: None for pattern in no_proxy_patterns(bypass)})
        return {"trust_env": False, "verify": context, "mounts": mounts}
    except (ValueError, ImportError) as exc:
        raise ValueError("Invalid ambient proxy configuration; review the host's approved proxy setup.") from exc


def network_failure_hint() -> str:
    if not external_trust_env() and any(os.getenv(key) for key in PROXY_KEYS):
        return " Ambient proxy detected; restart with JOBHOUND_EXTERNAL_NETWORK_MODE=environment if required by this workspace."
    return ""
