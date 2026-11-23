# mdr-mcp 📡

mcp-name: io.github.mohammad-abbasi-sh/mdr-mcp

Unofficial **read-only** MCP server for **[MDR](https://www.mdr.de)** — the Mitteldeutscher Rundfunk, the public broadcaster for Saxony, Saxony-Anhalt and Thuringia and ARD member — via its official RSS feeds (the MDR Aktuell main feed, one feed per state, one per section and one per city) and article pages, whose full text is read from the JSON-LD NewsArticle `articleBody` (MDR pages carry a real one). Top headlines, news by state (sachsen, sachsen-anhalt, thueringen), news by city (leipzig, dresden, chemnitz, magdeburg, halle), news by section (deutschland, kultur, wissen, sport), keyword search, and full article text. No key, no login.

> Built by Mohammad Abbasi as part of the "Germany MCP factory" (Sepehr-style pipeline). Not affiliated with MDR or ARD.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "mdr": {
      "command": "uvx",
      "args": ["mdr-mcp==0.1.0"]
    }
  }
}
```

Or run locally: `python -m mdr_mcp.server` (needs `mcp<2`, `httpx`).

## Tools

| Tool | Description |
|------|-------------|
| `mdr_headlines` | Top MDR Aktuell headlines (official RSS feed, ~45 items), newest first — `limit` 1..150. Every item carries a title, a per-article link, a teaser, an image URL, the region (derived from the link path) and publish time |
| `mdr_regional_news` | Newest news for one federal state, from its own official RSS feed — `region`: "sachsen", "sachsen-anhalt" or "thueringen", `limit` 1..150 |
| `mdr_local_news` | Newest news for one city, from its own official RSS feed — `city`: "leipzig", "dresden", "chemnitz" (Sachsen) or "magdeburg", "halle" (Sachsen-Anhalt), `limit` 1..150 |
| `mdr_section_news` | Newest news of one section, from its own official RSS feed — `section`: "deutschland", "kultur", "wissen" or "sport", `limit` 1..150 |
| `mdr_search_news` | Search news by keyword (title + teaser) across the main feed, all state, section and city feeds (~470 items) — `query` (e.g. "Leipzig"), `limit` 1..150 |
| `mdr_get_article` | Full text of one MDR article page (JSON-LD NewsArticle `articleBody`, with a server-rendered `<article>` fallback) — `url`: a www.mdr.de article URL (/nachrichten/<section>/<slug>,<id> or /sport/<section>/<slug>,<id>). Live-ticker pages return `kind: "live-ticker"` (their body is the intro text; ticker entries load client-side). Section-hub and off-site links are refused; a non-free page returns `paywalled: true` with the teaser only |
| `mdr_health` | Reachability probe (ok / blocked / error) — one polite request |

Example output (`mdr_headlines`, `limit` 2):

```json
{"feed_title": "MDR Aktuell – Nachrichten für Sachsen, Sachsen-Anhalt und Thüringen", "total_results": 45, "count": 2,
 "items": [
  {"title": "Deutsche Bahn lobt Sicherheitskonzept in Regionalzügen",
   "link": "https://www.mdr.de/nachrichten/deutschland/politik/deutsche-bahn-regio-bodycam-magdeburg-sachsen-anhalt,db-sicherheit-108.html",
   "description": "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet. Dabei wurden Zugbegleiter durch Sicherheitsmitarbeiter verstärkt und Bodycams eingesetzt. ...",
   "published": "2026-11-23T06:03:18+00:00", "region": "deutschland", "category": null,
   "image_url": "https://images.mdr.de/image/0975f5c7-c7fc-4511-ad48-baac0ca44eec/AAABogSUPsA/AAABnSSvrFg/16x9-big/db-bodycam-100.jpg?width=1920"},
  ...]}
```

Notes:
- The server reads the **official RSS feeds** (main feed 45 items; state feeds 54/116/107; section feeds 125/20/19/37; city feeds 65/66/65/47/46 — verified live 2026-11-23). Search runs client-side over the fetched feeds.
- The feeds carry **no `<category>` and no image element**: the region is derived from the link path (`/nachrichten/sachsen/...` → "sachsen"; `/sport/...` links → `null`), and the image is read from the `content:encoded` `<img>` (images.mdr.de, present on ~95% of items).
- The feeds mix in **hub/navigation items** (section pages such as `/nachrichten/sachsen/bautzen`, social links such as the MDR Sport Facebook page) with stale dates (some from 2023). Those are NOT news: items whose link does not end in `.html` are filtered out (Sachsen feed 54 → 49, Deutschland feed 125 → 104, Sport feed 37 → 33, Leipzig feed 65 → 61). A few `.html` topic pages ("Schwerpunkt Carolabrücke", "Kommentierbare Artikel") still slip through — genuine mdr.de pages linked by the feed, returned as-is.
- **Eilmeldung quirk:** breaking-news items carry an empty `<title>`; the title falls back to the description — the feed's own "+++ ... +++" line, not fabricated text.
- **Article text, honestly:** MDR article pages carry a REAL JSON-LD `articleBody` (266 words sampled for a news article, 385 for a live ticker), so the body comes from there; the server-rendered `<article>` paragraphs are only the fallback (259 words sampled, AUDIO/byline/promo lines filtered out). Live-ticker pages carry a `LiveBlogPosting` block too: they are reported as `kind: "live-ticker"` — the body is the intro text, the ticker entries load client-side and are not included. MDR is public broadcasting: sampled pages are free; a page that is not free returns `paywalled: true` with the teaser only.
- Off-site links in feed items (sportschau.de, youtube.com, whatsapp.com) are returned as-is and never fetched by `mdr_get_article`.
- Only the listed regions/sections/cities exist as feeds — politik, wirtschaft, panorama, gesundheit, thueringen/erfurt and thueringen/jena all 404 on the live site; sport lives at `/sport/index-rss.xml`, not under `/nachrichten/`.
- Data: MDR public RSS feeds and article pages — no key, no login, read-only.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — offline, parses the real captured main, state, section and city feeds plus two real article pages (a NewsArticle with a real JSON-LD body, and a live-ticker page with a LiveBlogPosting block)
- `tests/test_live.py` — cautious live requests against www.mdr.de

Tests: 35/35 green (28 offline + 7 live, 2026-11-23).

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — free for personal and non-commercial use; commercial use needs a separate license (see LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
