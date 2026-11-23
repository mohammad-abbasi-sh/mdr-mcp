"""HTTP layer for mdr_mcp — plain httpx GETs against www.mdr.de.

Endpoints, all public, no key, no login:
- the official RSS feeds: the MDR Aktuell main feed
  https://www.mdr.de/nachrichten/index-rss.xml, one feed per state
  (/nachrichten/<sachsen|sachsen-anhalt|thueringen>/index-rss.xml),
  one per section (/nachrichten/<deutschland|kultur|wissen>/
  index-rss.xml and /sport/index-rss.xml) and one per city
  (/nachrichten/sachsen/<leipzig|dresden|chemnitz>/index-rss.xml and
  /nachrichten/sachsen-anhalt/<magdeburg|halle>/index-rss.xml)
- article pages: https://www.mdr.de/nachrichten/<section>/<slug>,<id>
  and https://www.mdr.de/sport/<section>/<slug>,<id> — the full text
  is read from the JSON-LD NewsArticle "articleBody" (see
  domain.parse_article), with a server-rendered <article> fallback.

Only www.mdr.de is ever fetched. Feed items that link off-site
(sportschau.de, youtube.com, whatsapp.com) or to section hubs are
never fetched: fetch_article only accepts www.mdr.de URLs ending in
".html".
"""
from __future__ import annotations

import os
import ssl
import time
from urllib.parse import urlparse

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 25.0
ALLOWED_HOSTS = ("www.mdr.de",)
HEALTH_URL = "https://www.mdr.de/nachrichten/index-rss.xml"


class MdrError(RuntimeError):
    pass


def _verify():
    """TLS trust store: the OS bundle when present, else httpx/certifi.

    The OS bundle matters behind MITM egress proxies (their CA is in the
    system store, not in certifi) and is the right default on Linux
    anyway; on systems without it we fall back to certifi.
    """
    for path in (
        "/etc/ssl/certs/ca-certificates.crt",
        ssl.get_default_verify_paths().openssl_cafile,
    ):
        if path and os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return True


def _client(accept: str) -> httpx.Client:
    # NOTE: we read the proxy URL from the environment but never log it.
    # trust_env=False because httpx fails to parse bracketed IPv6 entries
    # (e.g. [::1]) that some environments put in no_proxy.
    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": accept},
        timeout=TIMEOUT,
        proxy=proxy or None,
        trust_env=False,
        verify=_verify(),
        follow_redirects=True,
    )


def _check_host(url: str) -> None:
    host = (urlparse(url).netloc or "").lower()
    if host not in ALLOWED_HOSTS:
        raise MdrError(
            f"only {', '.join(ALLOWED_HOSTS)} pages are fetched "
            f"(got {host or url!r})"
        )


def _get(url: str, accept: str) -> str:
    """GET with one retry on 429/5xx and on transient network errors."""
    _check_host(url)
    last_exc: Exception | None = None
    r: httpx.Response | None = None
    for attempt in range(2):
        try:
            with _client(accept) as c:
                r = c.get(url)
        except httpx.HTTPError as e:
            last_exc = e
            if attempt == 0:
                time.sleep(1.0)
                continue
            raise MdrError(f"network error fetching {url}: {e}") from e
        if r.status_code in (429, 500, 502, 503):
            if attempt == 0:
                time.sleep(1.0)
                continue
        break
    assert r is not None  # loop always assigns r or raises
    if r.status_code == 403:
        raise MdrError(
            f"www.mdr.de returned HTTP 403 for {url} (bot wall) — try again later"
        )
    if r.status_code == 429:
        raise MdrError(
            "www.mdr.de rate-limited the request (HTTP 429) — try again later"
        )
    if r.status_code != 200:
        raise MdrError(f"www.mdr.de returned HTTP {r.status_code} for {url}")
    return r.text


def fetch_feed(url: str) -> str:
    """GET an official MDR RSS feed; returns the raw XML text."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path
    ok = (
        host in ALLOWED_HOSTS
        and path.endswith("-rss.xml")
        and (path.startswith("/nachrichten/") or path.startswith("/sport/"))
    )
    if not ok:
        raise MdrError(f"only MDR RSS feed URLs are fetched (got {url!r})")
    return _get(url, "application/rss+xml, application/xml, text/xml, */*")


def fetch_article(url: str) -> str:
    """GET one www.mdr.de article page; returns the raw HTML text.

    Article URLs are /nachrichten/<section>/<slug>,<id> or
    /sport/<section>/<slug>,<id> — always ending in ".html". URLs
    with a fragment, section-hub URLs (no .html) and any other host
    are refused: hub items carry their whole short text in the feed
    description already, and off-site links are never fetched.
    """
    parsed = urlparse(url)
    if parsed.fragment:
        raise MdrError(
            "URLs with a fragment are not articles — the item's full "
            f"short text is already in its feed description (got {url!r})"
        )
    path = parsed.path
    if not path.endswith(".html"):
        raise MdrError(
            "only www.mdr.de article URLs (ending in .html) are fetched — "
            f"section hubs and social links are not articles (got {url!r})"
        )
    if not (path.startswith("/nachrichten/") or path.startswith("/sport/")):
        raise MdrError(
            "only www.mdr.de article URLs (/nachrichten/... or /sport/...) "
            f"are fetched (got {url!r})"
        )
    return _get(url, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")


def health_check() -> dict:
    """One polite probe of the source feed.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `mdr_health` tool
    and the daily smoke CI.
    """
    url = HEALTH_URL
    try:
        fetch_feed(url)
    except MdrError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
