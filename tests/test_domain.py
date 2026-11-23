"""Offline tests — parse the real captured mdr.de RSS feeds and two
real article pages (a NewsArticle with a real JSON-LD articleBody,
and a live-ticker page carrying both a NewsArticle articleBody and a
LiveBlogPosting block), no network."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mdr_mcp import domain as dom
from mdr_mcp import http as http_mod

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class TestHeadlinesFeed:
    def test_main_shape(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        assert parsed["feed_title"] == (
            "MDR Aktuell – Nachrichten für Sachsen, Sachsen-Anhalt und Thüringen"
        )
        assert parsed["count"] == 45
        assert len(parsed["items"]) == 45

    def test_main_first_item(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        first = parsed["items"][0]
        assert first["title"] == (
            "Deutsche Bahn lobt Sicherheitskonzept in Regionalzügen"
        )
        assert first["link"] == (
            "https://www.mdr.de/nachrichten/deutschland/politik/"
            "deutsche-bahn-regio-bodycam-magdeburg-sachsen-anhalt,"
            "db-sicherheit-108.html"
        )
        assert first["description"].startswith(
            "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet"
        )
        assert first["published"] == "2026-11-23T06:03:18+00:00"
        assert first["region"] == "deutschland"
        assert first["category"] is None
        assert first["image_url"].startswith("https://images.mdr.de/image/")

    def test_main_items_all_have_title_description_image(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        assert all(i["title"] and i["description"] for i in parsed["items"])
        assert all(i["image_url"] for i in parsed["items"])
        assert all(i["link"].endswith(".html") for i in parsed["items"])

    def test_eilmeldung_empty_title_falls_back_to_description(self):
        # One breaking-news item carries an empty <title>; the title
        # falls back to the feed's own "+++ ... +++" line (here a
        # rolling digest of three breaking items).
        parsed = dom.parse_rss(_read("headlines.xml"))
        eilm = [i for i in parsed["items"] if i["title"].startswith("+++")]
        assert len(eilm) == 1
        assert eilm[0]["title"] == eilm[0]["description"]
        assert eilm[0]["title"].startswith(
            "+++ Bombendrohungen an Schulen in Sachsen und Thüringen +++"
        )
        assert eilm[0]["title"].endswith("+++")
        assert eilm[0]["region"] is None  # /nachrichten/nachrichten-mdr-104.html


class TestRegionalFeed:
    def test_sachsen_shape_hubs_filtered(self):
        # Raw feed has 54 items; 5 hub items (Region Bautzen etc.,
        # links without .html) are filtered out.
        parsed = dom.parse_rss(_read("regional-sachsen.xml"))
        assert parsed["feed_title"] == (
            "Sachsen | Nachrichten, News, Videos, Fotos und Liveticker"
        )
        assert parsed["count"] == 49
        assert len(parsed["items"]) == 49

    def test_sachsen_first_item(self):
        parsed = dom.parse_rss(_read("regional-sachsen.xml"))
        first = parsed["items"][0]
        assert first["title"] == "Schwerpunkt Carolabrücke"
        assert first["region"] == "sachsen"
        assert first["published"] == "2026-05-27T11:12:59+00:00"
        assert first["image_url"].startswith("https://images.mdr.de/image/")

    def test_sachsen_all_items_are_news_links(self):
        parsed = dom.parse_rss(_read("regional-sachsen.xml"))
        assert all(i["link"].endswith(".html") for i in parsed["items"])
        assert all(i["link"].startswith("https://www.mdr.de/")
                    for i in parsed["items"])
        # 30 items are /nachrichten/sachsen/ stories; 19 are podcast
        # (/sachsenradio/podcast/...) and video (/video/...) pages —
        # genuine MDR content returned as-is, region None (they are
        # not /nachrichten/ links and mdr_get_article refuses them).
        regions = {i["region"] for i in parsed["items"]}
        assert regions == {"sachsen", None}


class TestSectionFeeds:
    def test_deutschland_shape_hubs_filtered(self):
        # Raw feed has 125 items; 21 hub items (Politik, Wirtschaft,
        # ... section pages) are filtered out.
        parsed = dom.parse_rss(_read("section-deutschland.xml"))
        assert parsed["feed_title"] == (
            "Deutschland | Aktuelle Nachrichten, Hintergründe und Kommentare"
        )
        assert parsed["count"] == 104
        assert len(parsed["items"]) == 104

    def test_deutschland_first_item_is_service_page(self):
        # The first surviving item is the "Kommentierbare Artikel"
        # service page — a genuine .html mdr.de page linked by the
        # feed, with no image.
        parsed = dom.parse_rss(_read("section-deutschland.xml"))
        first = parsed["items"][0]
        assert first["title"] == "Kommentierbare Artikel"
        assert first["image_url"] is None
        assert first["region"] == "deutschland"

    def test_sport_shape(self):
        # Raw feed has 37 items; 4 hub/social items are filtered out.
        parsed = dom.parse_rss(_read("section-sport.xml"))
        assert parsed["feed_title"] == "MDR Sport"
        assert parsed["count"] == 33

    def test_sport_first_item(self):
        parsed = dom.parse_rss(_read("section-sport.xml"))
        first = parsed["items"][0]
        assert first["title"] == (
            "Müller macht es vor: Rücken weitere Nachwuchsspieler bei "
            "Dynamo nach?"
        )
        assert first["link"].startswith("https://www.mdr.de/sport/")
        assert first["region"] is None  # sport links live under /sport/
        assert first["published"] == "2026-11-23T09:25:17+00:00"


class TestLocalFeed:
    def test_leipzig_shape_hubs_filtered(self):
        # Raw feed has 65 items; 4 hub items are filtered out.
        parsed = dom.parse_rss(_read("local-leipzig.xml"))
        assert parsed["feed_title"] == "Nachrichten aus der Region Leipzig"
        assert parsed["count"] == 61

    def test_leipzig_first_item_is_ticker_article(self):
        parsed = dom.parse_rss(_read("local-leipzig.xml"))
        first = parsed["items"][0]
        assert first["title"] == (
            "Prozess nach Amokfahrt in Leipzig: Heute sagen erste Zeugen aus"
        )
        assert first["region"] == "sachsen"
        assert first["published"] == "2026-11-23T09:35:08+00:00"


class TestArticle:
    def test_news_article_jsonld_body(self):
        art = dom.parse_article(_read("article-news.html"))
        assert art["kind"] == "article"
        assert art["title"] == (
            "Keine Übergriffe im Test: Bahn lobt Sicherheitskonzept "
            "in Regionalzügen"
        )
        assert art["author"] == "MDR AKTUELL"
        assert art["published"] == "2026-11-23T07:03:18.303+01:00"
        assert art["word_count"] == 266
        assert art["paywalled"] is False
        assert art["teaser_only"] is False
        assert art["video_url"] is None

    def test_news_article_body_is_jsonld(self):
        # MDR pages carry a REAL articleBody (unlike BR) — the body
        # is the JSON-LD text, not the SSR paragraphs.
        art = dom.parse_article(_read("article-news.html"))
        assert art["body"].startswith(
            "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet"
        )
        assert "Bodycams" in art["body"]
        assert art["description"].startswith(
            "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet"
        )

    def test_live_ticker_article(self):
        art = dom.parse_article(_read("article-ticker.html"))
        assert art["kind"] == "live-ticker"
        assert art["title"] == (
            "Prozess nach Amokfahrt in Leipzig: Heute sagen erste Zeugen aus"
        )
        assert art["author"] == "MDR SACHSEN"
        assert art["published"] == "2026-11-23T10:35:08.184+01:00"
        assert art["word_count"] == 385
        assert art["paywalled"] is False
        assert art["body"].startswith(
            "Nach dem emotionalen Auftakt geht der Prozess um die "
            "tödliche Amokfahrt"
        )

    def test_ssr_fallback_filters_noise(self):
        # The <article> fallback must drop the AUDIO line, the byline
        # and the Google-preference promo, but keep the lead.
        body = dom._ssr_body(_read("article-news.html"), "", "")
        assert len(body.split()) == 259
        assert body.startswith(
            "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet"
        )
        assert "AUDIO:" not in body
        assert "Nachrichten personalisieren" not in body
        assert not body.startswith("von MDR")


class TestValidators:
    def test_limit(self):
        assert dom.validate_limit(1) == 1
        assert dom.validate_limit(150) == 150
        with pytest.raises(ValueError):
            dom.validate_limit(0)
        with pytest.raises(ValueError):
            dom.validate_limit(151)

    def test_region(self):
        assert dom.validate_region("Sachsen") == "sachsen"
        assert dom.validate_region(" SACHSEN-ANHALT ") == "sachsen-anhalt"
        with pytest.raises(ValueError):
            dom.validate_region("bayern")  # no such feed

    def test_section(self):
        assert dom.validate_section("Sport") == "sport"
        assert dom.validate_section(" WISSEN ") == "wissen"
        with pytest.raises(ValueError):
            dom.validate_section("politik")  # 404 on the live site

    def test_city(self):
        assert dom.validate_city(" LEIPZIG ") == "leipzig"
        assert dom.validate_city("Halle") == "halle"
        with pytest.raises(ValueError):
            dom.validate_city("erfurt")  # 404 on the live site


class TestSearchAndDedupe:
    def test_search_items(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        found = dom.search_items(parsed["items"], "Leipzig")
        assert len(found) == 4
        assert dom.search_items(parsed["items"], "leipzig") == found
        assert len(dom.search_items(parsed["items"], "Bahn")) == 2
        with pytest.raises(ValueError):
            dom.search_items(parsed["items"], "   ")

    def test_dedupe_sort(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        doubled = parsed["items"] + parsed["items"][:5]
        out = dom.dedupe_sort(doubled)
        assert len(out) == 45
        pubs = [i["published"] for i in out]
        assert pubs == sorted(pubs, reverse=True)


class TestFeedGuards:
    def test_parse_rss_rejects_garbage(self):
        with pytest.raises(ValueError):
            dom.parse_rss("<html><body>not rss</body></html>")

    def test_fetch_article_refuses_hub_links(self):
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_article(
                "https://www.mdr.de/nachrichten/sachsen/bautzen"
            )
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_article(
                "https://www.mdr.de/nachrichten/deutschland/politik"
            )

    def test_fetch_article_refuses_other_hosts(self):
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_article(
                "https://www.sportschau.de/fussball/bundesliga/bl-spielbericht-100.html"
            )
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_article(
                "https://www.youtube.com/channel/UCWAsbbMMq1LzdyEJkb-JwmQ"
            )

    def test_fetch_feed_refuses_non_feed_urls(self):
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_feed("https://www.mdr.de/nachrichten/wissen/")
        with pytest.raises(http_mod.MdrError):
            http_mod.fetch_feed(
                "https://www.mdr.de/nachrichten/index.html"
            )


class TestServerEnvelope:
    def test_tools_return_json_envelope(self):
        # Offline: the tools hit the network, so only the error path
        # is exercised here — but the envelope shape is the same.
        from mdr_mcp import server as srv

        out = json.loads(srv.mdr_regional_news("bayern"))
        assert "error" in out
        assert out["source"] == "www.mdr.de"
        assert "fetched_at" in out
