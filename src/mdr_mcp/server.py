"""MCP server: unofficial read-only access to MDR (mdr.de) — the
Mitteldeutscher Rundfunk, the public broadcaster for Saxony,
Saxony-Anhalt and Thuringia and ARD member — via its official RSS
feeds (MDR Aktuell main feed, one feed per state, one per section
and one per city) and article pages (full text from the JSON-LD
NewsArticle articleBody, with a server-rendered <article> fallback).
No key, no login."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import domain as _dom
from . import http as _http

INSTRUCTIONS = """\
Unofficial read-only MCP server for MDR (mdr.de) — the
Mitteldeutscher Rundfunk, the public broadcaster for Saxony,
Saxony-Anhalt and Thuringia and ARD member — via its official RSS
feeds (no key, no login) and article pages. The MDR Aktuell main
feed (45 items, newest first, with teaser + image),
news by state (sachsen, sachsen-anhalt, thueringen), news by city
(leipzig, dresden, chemnitz, magdeburg, halle), news by section
(deutschland, kultur, wissen, sport), keyword search across all
feeds, and full article text (the JSON-LD NewsArticle articleBody —
MDR pages carry a real one). Live-ticker pages are reported as
kind="live-ticker": their articleBody is the intro text and the
ticker entries load client-side, so they are not included. NOTE:
feed items that are section hubs or social links (no .html URL)
are filtered out — they are navigation, not news. Off-site links
(sportschau.de, youtube.com) are returned as-is and never fetched.
MDR is public broadcasting: sampled pages are free; a page that is
not free returns paywalled=true with the teaser, never fabricated
text.
Built by Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir · \
https://mabbasi.ir — Germany MCP factory.\
"""


_SOURCE = "www.mdr.de"
_DISCLAIMER = "Unofficial read-only data from MDR's public RSS feeds and article pages; verify on the site before acting on it."


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


mcp = FastMCP("mdr-mcp", instructions=INSTRUCTIONS)


def _feed(url: str, limit: int) -> dict:
    """Fetch one MDR RSS 2.0 feed and return its items, newest first, capped."""
    parsed = _dom.parse_rss(_http.fetch_feed(url))
    items = parsed["items"][:limit]
    return {
        "feed_title": parsed["feed_title"],
        "total_results": parsed["count"],
        "count": len(items),
        "items": items,
    }


@mcp.tool()
def mdr_headlines(limit: int = 10) -> str:
    """Top MDR Aktuell headlines (official RSS feed, ~45 items), newest
first. limit: 1..150 (default 10). Every item carries a title, a
per-article link for mdr_get_article, a teaser (description), an
image URL, the region (sachsen / sachsen-anhalt / thueringen /
deutschland / welt, derived from the link path) and publish time."""
    try:
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.HEADLINES_FEED, lim)
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_regional_news(region: str, limit: int = 10) -> str:
    """Newest MDR news for one federal state, from its own official RSS
feed. region: "sachsen", "sachsen-anhalt" or "thueringen".
limit: 1..150 (default 10). Items carry title, link (a per-article
URL for mdr_get_article), teaser, image URL, region and publish
time."""
    try:
        reg = _dom.validate_region(region)
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.REGIONS[reg], lim)
        out["region"] = reg
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_local_news(city: str, limit: int = 10) -> str:
    """Newest MDR news for one city, from its own official RSS feed.
city: "leipzig", "dresden", "chemnitz" (Sachsen) or "magdeburg",
"halle" (Sachsen-Anhalt). limit: 1..150 (default 10). Items carry
title, link (a per-article URL for mdr_get_article), teaser,
image URL, region and publish time."""
    try:
        c = _dom.validate_city(city)
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.CITIES[c], lim)
        out["city"] = c
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_section_news(section: str, limit: int = 10) -> str:
    """Newest MDR news of one section, from its own official RSS feed.
section: "deutschland", "kultur", "wissen" or "sport".
limit: 1..150 (default 10). Items carry title, link (a per-article
URL for mdr_get_article), teaser, image URL and publish time."""
    try:
        sec = _dom.validate_section(section)
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.SECTIONS[sec], lim)
        out["section"] = sec
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_search_news(query: str, limit: int = 10) -> str:
    """Search MDR news by keyword (title + teaser)
across the main feed, all three state feeds, all four section feeds
and all five city feeds. query: free text, e.g. "Leipzig" or
"Bundesliga". limit: 1..150 (default 10). Searches ~470 items
client-side, newest first, de-duplicated by link."""
    try:
        if not (query or "").strip():
            return _ok({"error": "query must not be empty"})
        lim = _dom.validate_limit(limit)
        all_items: list[dict] = []
        urls = (
            [_dom.HEADLINES_FEED]
            + list(_dom.REGIONS.values())
            + list(_dom.SECTIONS.values())
            + list(_dom.CITIES.values())
        )
        for url in urls:
            parsed = _dom.parse_rss(_http.fetch_feed(url))
            all_items.extend(parsed["items"])
        found = _dom.dedupe_sort(_dom.search_items(all_items, query.strip()))
        out = {
            "query": query.strip(),
            "total_results": len(found),
            "count": min(lim, len(found)),
            "items": found[:lim],
        }
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_get_article(url: str) -> str:
    """Full text of one MDR article page (the JSON-LD NewsArticle
articleBody — MDR pages carry a real one — with a server-rendered
<article> fallback). url: a www.mdr.de article URL, e.g. from
mdr_headlines (/nachrichten/<section>/<slug>,<id>) or a sport page
(/sport/<section>/<slug>,<id>). Returns title, author, publish
time, the body text and its word count. Live-ticker pages return
kind="live-ticker": their body is the intro text, and the ticker
entries load client-side. Section-hub and off-site links are
refused — hub items carry their full short text in the feed
already. A page that is not freely accessible returns
paywalled=true with the teaser only. Nothing is ever fabricated."""
    try:
        if not (url or "").strip():
            return _ok({"error": "url must not be empty"})
        url = url.strip()
        article = _dom.parse_article(_http.fetch_article(url))
        paywalled = article["paywalled"]
        note = ""
        if paywalled:
            note = (
                "This article is not freely accessible: only the teaser "
                "is available."
            )
        elif article["kind"] == "live-ticker":
            note = (
                "Live ticker: the body is the intro text; the ticker "
                "entries load live on the page and are not included."
            )
        elif article["kind"] == "video":
            note = (
                "Video page: the description is the whole freely "
                "available text; watch the video at video_url."
            )
        elif article["teaser_only"]:
            note = (
                "Only the teaser is available for this item; the teaser "
                "is the whole freely available text."
            )
        out = {
            "url": url,
            "title": article["title"],
            "author": article["author"],
            "published": article["published"],
            "kind": article["kind"],
            "paywalled": paywalled,
            "teaser_only": article["teaser_only"],
            "word_count": article["word_count"],
            "body": article["body"],
            "description": article["description"],
            "video_url": article["video_url"],
            "duration": article["duration"],
            "note": note,
        }
    except (_http.MdrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def mdr_health() -> str:
    """Check whether the MDR Aktuell main feed is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    One polite request; it does not fetch any listings."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    sys.exit(main())
