"""Domain logic: shape mdr.de's official RSS feeds and article pages
into compact dicts (stdlib only).

Data source: the official Mitteldeutscher Rundfunk RSS feeds (no key,
no login) — the MDR Aktuell main feed
(https://www.mdr.de/nachrichten/index-rss.xml), one feed per state
(sachsen, sachsen-anhalt, thueringen), one per section (deutschland,
kultur, wissen, sport) and one per city (leipzig, dresden, chemnitz,
magdeburg, halle) — plus article pages, whose full text lives in the
JSON-LD NewsArticle "articleBody" (2,125-2,792 chars sampled).

Honest limitations (verified live 2026-11-23):
- The feeds carry NO <category> and NO image: region is derived from
  the link path (/nachrichten/sachsen/... etc.); sport links live
  under /sport/... and podcast/video links under /sachsenradio/...
  and /video/... (region None).
- The feeds mix in hub/navigation items (section pages such as
  /nachrichten/sachsen/bautzen, social links such as the MDR Sport
  Facebook page) with stale dates (some from 2023). Those are NOT
  news: parse_rss filters out every item whose link does not end in
  ".html" (Sachsen feed: 54 -> 49 items; Deutschland feed: 125 ->
  104; Sport feed: 37 -> 33; Leipzig feed: 65 -> 61).
- Feed items carry a short description (the teaser, ~120-210 chars).
  The content:encoded block adds nothing beyond the teaser (it is
  the teaser plus a "[mehr]" marker) — but it carries the item's
  image (an <img> from images.mdr.de, present on ~95% of items),
  which is returned as image_url.
- Eilmeldung (breaking-news) items carry an EMPTY <title>; the title
  falls back to the description — the feed's own breaking-news line
  ("+++ ... +++"), not fabricated text.
- A few .html topic/service pages slip through the filter (e.g.
  "Schwerpunkt Carolabrücke", "Kommentierbare Artikel") — they are
  genuine mdr.de pages linked by the feed, returned as-is.
- Only the listed regions/sections/cities exist as feeds: politik,
  wirtschaft, panorama, gesundheit, thueringen/erfurt and
  thueringen/jena all 404; sport lives at /sport/index-rss.xml, not
  under /nachrichten/.
- Live-ticker pages carry a NewsArticle articleBody (the intro text,
  385 words sampled) AND a LiveBlogPosting block; they are reported
  as kind="live-ticker" — the ticker entries themselves load
  client-side and are not in the fetched HTML.
- MDR is public broadcasting: sampled pages are free
  (isAccessibleForFree=true); the flag is still honoured if a page
  ever sets it to false.
- Off-site links (sportschau.de, youtube.com, whatsapp.com) are
  returned as-is in feed items and never fetched by mdr_get_article.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

BASE = "https://www.mdr.de"
HEADLINES_FEED = f"{BASE}/nachrichten/index-rss.xml"

# One feed per state (verified 200, 2026-11-23; item counts are
# pre-filter counts — hub items are dropped by parse_rss).
REGIONS = {
    "sachsen": f"{BASE}/nachrichten/sachsen/index-rss.xml",
    "sachsen-anhalt": f"{BASE}/nachrichten/sachsen-anhalt/index-rss.xml",
    "thueringen": f"{BASE}/nachrichten/thueringen/index-rss.xml",
}

# One feed per section (verified 200, 2026-11-23). Sport lives at
# /sport/index-rss.xml, not under /nachrichten/.
SECTIONS = {
    "deutschland": f"{BASE}/nachrichten/deutschland/index-rss.xml",
    "kultur": f"{BASE}/nachrichten/kultur/index-rss.xml",
    "wissen": f"{BASE}/nachrichten/wissen/index-rss.xml",
    "sport": f"{BASE}/sport/index-rss.xml",
}

# One feed per city (verified 200, 2026-11-23). Leipzig/Dresden/
# Chemnitz are Sachsen cities; Magdeburg/Halle are Sachsen-Anhalt
# cities. Thueringen cities (erfurt, jena) 404 — no feed exists.
CITIES = {
    "leipzig": f"{BASE}/nachrichten/sachsen/leipzig/index-rss.xml",
    "dresden": f"{BASE}/nachrichten/sachsen/dresden/index-rss.xml",
    "chemnitz": f"{BASE}/nachrichten/sachsen/chemnitz/index-rss.xml",
    "magdeburg": f"{BASE}/nachrichten/sachsen-anhalt/magdeburg/index-rss.xml",
    "halle": f"{BASE}/nachrichten/sachsen-anhalt/halle/index-rss.xml",
}

# Link-path segments that identify the state a story belongs to.
_REGION_SEGMENTS = ("sachsen", "sachsen-anhalt", "thueringen",
                    "deutschland", "welt")

_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)


def validate_limit(limit: int) -> int:
    """Clamp/validate the page size (feeds carry 20-125 items)."""
    if not 1 <= limit <= 150:
        raise ValueError(f"limit out of range: {limit} (expected 1..150)")
    return limit


def validate_region(region: str) -> str:
    """Normalise a state name to one of the three regional feeds."""
    r = (region or "").strip().casefold()
    if r not in REGIONS:
        raise ValueError(
            f"unknown region: {region!r} (expected one of "
            f"{', '.join(sorted(REGIONS))})"
        )
    return r


def validate_section(section: str) -> str:
    """Normalise a section name to one of the four section feeds."""
    s = (section or "").strip().casefold()
    if s not in SECTIONS:
        raise ValueError(
            f"unknown section: {section!r} (expected one of "
            f"{', '.join(sorted(SECTIONS))})"
        )
    return s


def validate_city(city: str) -> str:
    """Normalise a city name to one of the five city feeds."""
    c = (city or "").strip().casefold()
    if c not in CITIES:
        raise ValueError(
            f"unknown city: {city!r} (expected one of "
            f"{', '.join(sorted(CITIES))})"
        )
    return c


def _text(elem, tag: str) -> str:
    child = elem.find(tag)
    if child is None or child.text is None:
        return ""
    return html.unescape(child.text).strip()


def _iso(date_text: str) -> str | None:
    if not date_text:
        return None
    text = date_text.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(raw: str) -> str:
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _published(item: ET.Element) -> str | None:
    """pubDate (RSS 2.0) or dc:date — matched by local name."""
    for child in item:
        local = child.tag.rsplit("}", 1)[-1]
        if local in ("pubDate", "date") and child.text:
            return _iso(child.text)
    return None


def _region_from_link(link: str) -> str | None:
    """State/section segment of an mdr.de news link, or None.

    /nachrichten/sachsen/... -> "sachsen"; /nachrichten/deutschland/...
    -> "deutschland"; /sport/..., /sachsenradio/... and /video/...
    links -> None.
    """
    try:
        path = urlparse(link).path
    except ValueError:
        return None
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "nachrichten":
        if parts[1] in _REGION_SEGMENTS:
            return parts[1]
    return None


def compact_item(item: ET.Element) -> dict | None:
    """One RSS 2.0 <item>: title, link, teaser, image (from the
    content:encoded <img>), region (from the link path) and publish
    time.

    Returns None for hub/navigation items: feed items whose link does
    not end in ".html" are section pages or social links, not news.
    MDR feeds carry no <category>. Eilmeldung items carry an empty
    <title>: the title falls back to the description (the feed's own
    breaking-news line).
    """
    link = _text(item, "link")
    if not link.endswith(".html"):
        return None
    title = _text(item, "title")
    description = _strip_tags(_text(item, "description"))
    if not title:
        title = description
    encoded = item.find(f"{{{_CONTENT_NS}}}encoded")
    image = None
    if encoded is not None and encoded.text:
        match = _IMG_RE.search(encoded.text)
        if match:
            image = html.unescape(match.group(1)).strip() or None
    return {
        "title": title,
        "link": link,
        "description": description,
        "published": _published(item),
        "region": _region_from_link(link),
        "category": None,
        "image_url": image,
    }


def parse_rss(xml_text: str) -> dict:
    """Parse an MDR RSS 2.0 feed into {feed_title, count, items}.

    Hub/navigation items are filtered out (see compact_item), so
    count is the number of news items, not the raw feed size.
    Raises ValueError on malformed XML or a non-RSS document.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid RSS XML: {e}") from e
    channel = root.find("channel")
    if channel is None:
        raise ValueError("unexpected RSS shape: no <channel> element")
    items = []
    for it in channel.findall("item"):
        compacted = compact_item(it)
        if compacted is not None:
            items.append(compacted)
    return {
        "feed_title": _text(channel, "title"),
        "count": len(items),
        "items": items,
    }


_LD_JSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S | re.I,
)
_ARTICLE_RE = re.compile(r"<article[^>]*>(.*?)</article>", re.S | re.I)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_OG_DESC_RE = re.compile(
    r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
    re.S | re.I,
)


def _author_name(raw) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return str(raw.get("name") or "").strip()
    if isinstance(raw, list):
        names = [_author_name(a) for a in raw]
        return ", ".join(n for n in names if n)
    return ""


def _is_free(block: dict) -> bool:
    """isAccessibleForFree from a JSON-LD block; absent means free
    (MDR pages that carry the field at all set it explicitly)."""
    val = block.get("isAccessibleForFree")
    return True if val is None else bool(val)


def _ssr_body(html_text: str, title: str, description: str) -> str:
    """Body text from the server-rendered <article> paragraphs.

    Filters out the audio teaser line ("AUDIO: ..."), the byline
    ("von MDR AKTUELL" / "von MDR SACHSEN"), the Google-preference
    promo ("Nachrichten personalisieren ...") and the programme note
    ("Dieses Thema im Programm:"). Raises ValueError when no usable
    body paragraphs are found.
    """
    match = _ARTICLE_RE.search(html_text)
    if not match:
        raise ValueError(
            "no article text found on this page (no JSON-LD articleBody "
            "and no <article> body) — the page may be JS-rendered or an "
            "error page"
        )
    paras: list[str] = []
    for raw in _P_RE.findall(match.group(1)):
        text = _strip_tags(raw)
        if not text:
            continue
        if text.startswith("AUDIO:"):
            continue  # audio teaser line, not article text
        if text.startswith("von MDR "):
            continue  # byline paragraph
        if text.startswith("Nachrichten personalisieren"):
            continue  # Google-preference promo paragraph
        if text.startswith("Dieses Thema im Programm:"):
            continue  # programme note, not article text
        if title and text == title:
            continue  # header paragraph: the title again
        if description and text == description:
            continue  # teaser paragraph: the description again
        paras.append(text)
    body = "\n\n".join(paras).strip()
    if not body:
        raise ValueError(
            "no article text found on this page (the <article> body is "
            "empty after filtering)"
        )
    return body


def _page_title(html_text: str) -> str:
    match = _TITLE_RE.search(html_text)
    if not match:
        return ""
    title = _strip_tags(match.group(1))
    return re.sub(r"\s*\|\s*MDR.*$", "", title, flags=re.I)


def parse_article(html_text: str) -> dict:
    """Extract the article from an mdr.de page.

    Prefers the JSON-LD NewsArticle "articleBody" — MDR pages carry
    a real one (2,125-2,792 chars sampled). A page that also carries
    a LiveBlogPosting block is a live ticker: kind="live-ticker"
    (the articleBody is the intro text; ticker entries load
    client-side). Falls back to the server-rendered <article>
    paragraphs when no articleBody exists. Returns {title,
    description, body, author, published, word_count, teaser_only,
    paywalled, kind, video_url, duration}. Raises ValueError when no
    usable text is found.
    """
    blocks: list[dict] = []
    for match in _LD_JSON_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            blocks.append(data)

    title = _page_title(html_text)
    description = ""
    og = _OG_DESC_RE.search(html_text)
    if og:
        description = html.unescape(og.group(1)).strip()

    is_ticker = any(b.get("@type") == "LiveBlogPosting" for b in blocks)

    for block in blocks:
        if block.get("@type") not in ("NewsArticle", "Article"):
            continue
        body = (block.get("articleBody") or "").strip()
        if not body:
            continue
        description = description or _strip_tags(str(block.get("description") or ""))
        return {
            "title": _strip_tags(str(block.get("headline") or "")) or title,
            "description": description,
            "body": body,
            "author": _author_name(block.get("author")),
            "published": str(block.get("datePublished") or "") or None,
            "word_count": len(body.split()),
            "teaser_only": bool(body) and body == description,
            "paywalled": not _is_free(block),
            "kind": "live-ticker" if is_ticker else "article",
            "video_url": None,
            "duration": None,
        }

    # A NewsArticle/Article block means the page IS an article — even
    # when its articleBody is empty (fall back to SSR paragraphs).
    # Only a page with no article block at all is treated as a video
    # page.
    article_block = None
    for block in blocks:
        if block.get("@type") in ("NewsArticle", "Article"):
            article_block = block
            break
    if article_block is not None:
        description = description or _strip_tags(
            str(article_block.get("description") or "")
        )
        body = _ssr_body(html_text, title, description)
        return {
            "title": (
                _strip_tags(str(article_block.get("headline") or "")) or title
            ),
            "description": description,
            "body": body,
            "author": _author_name(article_block.get("author")),
            "published": (
                str(article_block.get("datePublished") or "") or None
            ),
            "word_count": len(body.split()),
            "teaser_only": bool(body) and body == description,
            "paywalled": not _is_free(article_block),
            "kind": "live-ticker" if is_ticker else "article",
            "video_url": None,
            "duration": None,
        }

    for block in blocks:
        if block.get("@type") != "VideoObject":
            continue
        description = description or _strip_tags(str(block.get("description") or ""))
        return {
            "title": _strip_tags(str(block.get("name") or "")) or title,
            "description": description,
            "body": description,
            "author": "",
            "published": str(block.get("uploadDate") or "") or None,
            "word_count": len(description.split()),
            "teaser_only": True,
            "paywalled": not _is_free(block),
            "kind": "video",
            "video_url": str(block.get("contentUrl") or "") or None,
            "duration": str(block.get("duration") or "") or None,
        }

    body = _ssr_body(html_text, title, description)
    return {
        "title": title,
        "description": description,
        "body": body,
        "author": "",
        "published": None,
        "word_count": len(body.split()),
        "teaser_only": bool(body) and body == description,
        "paywalled": False,
        "kind": "live-ticker" if is_ticker else "article",
        "video_url": None,
        "duration": None,
    }


def search_items(items: list, query: str) -> list:
    """Case-insensitive substring match over title + description."""
    q = (query or "").strip().casefold()
    if not q:
        raise ValueError("query must not be empty")
    return [
        it for it in items
        if q in (it.get("title") or "").casefold()
        or q in (it.get("description") or "").casefold()
    ]


def dedupe_sort(items: list) -> list:
    """De-duplicate by link, newest first (empty publish time sorts last)."""
    seen: set[str] = set()
    unique: list[dict] = []
    for it in items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        unique.append(it)
    unique.sort(key=lambda it: it.get("published") or "", reverse=True)
    return unique
