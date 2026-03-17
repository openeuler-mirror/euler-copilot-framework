"""URL 工具函数。"""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

_LOOPBACK_HOST_FALLBACKS = {
    "localhost": "127.0.0.1",
    "::1": "127.0.0.1",
}


def _replace_hostname(parsed: SplitResult, host: str) -> str:
    """替换 URL 中的 hostname，并保留用户信息、端口和路径。"""
    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    host_part = f"[{host}]" if ":" in host else host
    port_part = f":{parsed.port}" if parsed.port is not None else ""
    netloc = f"{userinfo}{host_part}{port_part}"
    return parsed._replace(netloc=netloc).geturl()


def get_url_host_candidates(url: str) -> list[str]:
    """返回 URL 可用于连接的 hostname 候选列表。"""
    parsed = urlsplit(url)
    host = parsed.hostname or "127.0.0.1"
    fallback = _LOOPBACK_HOST_FALLBACKS.get(host.casefold())
    candidates = [fallback] if fallback else [host]
    if fallback and host not in candidates:
        candidates.append(host)
    return candidates


def normalize_loopback_url(url: str) -> str:
    """将 localhost/::1 规范化为优先可用的 IPv4 loopback URL。"""
    return get_url_candidates(url)[0]


def get_url_candidates(url: str) -> list[str]:
    """返回 URL 连接候选列表，对 localhost/::1 追加 IPv4 loopback 兜底。"""
    parsed = urlsplit(url)
    candidates = [_replace_hostname(parsed, host) for host in get_url_host_candidates(url)]

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped
