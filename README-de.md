# mdr-mcp 📡

mcp-name: io.github.mohammad-abbasi-sh/mdr-mcp

Inoffizieller **Read-only**-MCP-Server für **[MDR](https://www.mdr.de)** — den Mitteldeutschen Rundfunk, öffentlich-rechtlichen Sender für Sachsen, Sachsen-Anhalt und Thüringen und ARD-Mitglied — über die offiziellen RSS-Feeds (MDR-Aktuell-Hauptfeed, ein Feed je Bundesland, ein Feed je Ressort und ein Feed je Stadt) und Artikelseiten, deren Volltext aus dem JSON-LD-NewsArticle-`articleBody` gelesen wird (MDR-Seiten tragen ein echtes). Top-Schlagzeilen, Nachrichten nach Bundesland (sachsen, sachsen-anhalt, thueringen), Nachrichten nach Stadt (leipzig, dresden, chemnitz, magdeburg, halle), Nachrichten nach Ressort (deutschland, kultur, wissen, sport), Stichwortsuche und Volltexte von Artikeln. Kein Schlüssel, kein Login.

> Gebaut von Mohammad Abbasi als Teil der "Germany MCP factory" (Sepehr-ähnliche Pipeline). Nicht mit MDR oder ARD verbunden.

## Für KI-Agenten

In die MCP-Client-Konfiguration eintragen (stdio):

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

Oder lokal starten: `python -m mdr_mcp.server` (benötigt `mcp<2`, `httpx`).

## Tools

| Tool | Beschreibung |
|------|-------------|
| `mdr_headlines` | Top-Schlagzeilen von MDR Aktuell (offizieller RSS-Feed, ~45 Einträge), neueste zuerst — `limit` 1..150. Jeder Eintrag trägt Titel, Artikel-Link, Teaser, Bild-URL, Region (aus dem Link-Pfad abgeleitet) und Veröffentlichungszeit |
| `mdr_regional_news` | Neueste Nachrichten eines Bundeslands, aus dem eigenen offiziellen RSS-Feed — `region`: "sachsen", "sachsen-anhalt" oder "thueringen", `limit` 1..150 |
| `mdr_local_news` | Neueste Nachrichten einer Stadt, aus dem eigenen offiziellen RSS-Feed — `city`: "leipzig", "dresden", "chemnitz" (Sachsen) oder "magdeburg", "halle" (Sachsen-Anhalt), `limit` 1..150 |
| `mdr_section_news` | Neueste Nachrichten eines Ressorts, aus dem eigenen offiziellen RSS-Feed — `section`: "deutschland", "kultur", "wissen" oder "sport", `limit` 1..150 |
| `mdr_search_news` | Stichwortsuche in den Nachrichten (Titel + Teaser) über Hauptfeed, alle Bundesland-, Ressort- und Stadt-Feeds (~470 Einträge) — `query` (z. B. "Leipzig"), `limit` 1..150 |
| `mdr_get_article` | Volltext einer MDR-Artikelseite (JSON-LD-NewsArticle-`articleBody`, mit serverseitig gerenderten `<article>`-Absätzen als Fallback) — `url`: eine www.mdr.de-Artikel-URL (/nachrichten/<ressort>/<slug>,<id> oder /sport/<ressort>/<slug>,<id>). Live-Ticker-Seiten liefern `kind: "live-ticker"` (der Text ist der Einleitungstext; Ticker-Einträge laden clientseitig). Hub- und externe Links werden abgelehnt; eine nicht frei zugängliche Seite liefert `paywalled: true` und nur den Teaser |
| `mdr_health` | Erreichbarkeitsprüfung (ok / blocked / error) — eine höfliche Anfrage |

Beispielausgabe (`mdr_headlines`, `limit` 2):

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

Hinweise:
- Der Server liest die **offiziellen RSS-Feeds** (Hauptfeed 45 Einträge; Bundesland-Feeds 54/116/107; Ressort-Feeds 125/20/19/37; Stadt-Feeds 65/66/65/47/46 — live verifiziert 2026-11-23). Die Suche läuft clientseitig über die geladenen Feeds.
- Die Feeds tragen **kein `<category>` und kein Bildelement**: die Region wird aus dem Link-Pfad abgeleitet (`/nachrichten/sachsen/...` → "sachsen"; `/sport/...`-Links → `null`), und das Bild wird aus dem `<img>` in `content:encoded` gelesen (images.mdr.de, bei ~95 % der Einträge vorhanden).
- Die Feeds mischen **Hub-/Navigations-Einträge** ein (Bereichsseiten wie `/nachrichten/sachsen/bautzen`, Social-Links wie die MDR-Sport-Facebook-Seite) mit alten Daten (teilweise aus 2023). Das sind KEINE Nachrichten: Einträge, deren Link nicht auf `.html` endet, werden herausgefiltert (Sachsen-Feed 54 → 49, Deutschland-Feed 125 → 104, Sport-Feed 37 → 33, Leipzig-Feed 65 → 61). Ein paar `.html`-Themenseiten ("Schwerpunkt Carolabrücke", "Kommentierbare Artikel") rutschen trotzdem durch — echte mdr.de-Seiten aus dem Feed, unverändert zurückgegeben.
- **Eilmeldungs-Eigenheit:** Eilmeldungen tragen einen leeren `<title>`; der Titel fällt auf die Beschreibung zurück — die feed-eigene "+++ ... +++"-Zeile, kein erfundener Text.
- **Artikeltexte, ehrlich:** MDR-Artikelseiten tragen ein ECHTES JSON-LD-`articleBody` (266 Wörter in der Stichprobe für einen Nachrichtenartikel, 385 für einen Live-Ticker), der Text kommt daher von dort; die serverseitig gerenderten `<article>`-Absätze sind nur der Fallback (259 Wörter in der Stichprobe, AUDIO-/Byline-/Promo-Zeilen herausgefiltert). Live-Ticker-Seiten tragen zusätzlich einen `LiveBlogPosting`-Block: sie werden als `kind: "live-ticker"` gemeldet — der Text ist der Einleitungstext, die Ticker-Einträge laden clientseitig und sind nicht enthalten. MDR ist öffentlich-rechtlich: die Stichproben sind frei; eine nicht freie Seite liefert `paywalled: true` und nur den Teaser.
- Externe Links in Feed-Einträgen (sportschau.de, youtube.com, whatsapp.com) werden unverändert zurückgegeben und von `mdr_get_article` nie abgerufen.
- Nur die aufgeführten Regionen/Ressorts/Städte existieren als Feeds — politik, wirtschaft, panorama, gesundheit, thueringen/erfurt und thueringen/jena liefern auf der Live-Seite alle 404; Sport liegt unter `/sport/index-rss.xml`, nicht unter `/nachrichten/`.
- Daten: öffentliche MDR-RSS-Feeds und Artikelseiten — kein Schlüssel, kein Login, nur lesend.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — offline, parst die echten, gespeicherten Haupt-, Bundesland-, Ressort- und Stadt-Feeds sowie zwei echte Artikelseiten (ein NewsArticle mit echtem JSON-LD-Text und eine Live-Ticker-Seite mit LiveBlogPosting-Block)
- `tests/test_live.py` — vorsichtige Live-Anfragen an www.mdr.de

Tests: 35/35 grün (28 offline + 7 live, 2026-11-23).

## Lizenz

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — frei für private und nicht-kommerzielle Nutzung; kommerzielle Nutzung braucht eine separate Lizenz (siehe LICENSE).

---

Gebaut von [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
