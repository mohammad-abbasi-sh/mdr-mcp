"""Live tests — hit the real www.mdr.de RSS feeds and article pages.
Cautious: few requests.

Run:  pytest tests/test_live.py -v
Skip: pytest -m "not live"  (or set MDR_SKIP_LIVE=1)
"""
import json
import os
import pathlib
import sys
import unittest

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from mdr_mcp import server as srv

pytestmark = pytest.mark.live
SKIP = os.environ.get("MDR_SKIP_LIVE") == "1"


@pytest.mark.skipif(SKIP, reason="MDR_SKIP_LIVE=1")
class TestLive(unittest.TestCase):
    def test_headlines_live(self):
        out = json.loads(srv.mdr_headlines(limit=3))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["title"] and i["description"] for i in out["items"]))
        print(f"\nLIVE headlines: {out['count']} items, first: {out['items'][0]['title']}")

    def test_regional_live(self):
        out = json.loads(srv.mdr_regional_news("sachsen", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["region"], "sachsen")
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["link"].endswith(".html") for i in out["items"]))
        print(f"\nLIVE sachsen: {out['total_results']} items")

    def test_local_live(self):
        out = json.loads(srv.mdr_local_news("leipzig", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["city"], "leipzig")
        self.assertGreaterEqual(out["count"], 1)
        print(f"\nLIVE leipzig: {out['total_results']} items")

    def test_section_live(self):
        out = json.loads(srv.mdr_section_news("sport", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["section"], "sport")
        self.assertGreaterEqual(out["count"], 1)
        print(f"\nLIVE sport: {out['total_results']} items")

    def test_search_live(self):
        out = json.loads(srv.mdr_search_news("Leipzig", limit=3))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(
            "leipzig" in (i["title"] + i["description"]).casefold()
            for i in out["items"]
        ))
        print(f"\nLIVE search 'Leipzig': {out['total_results']} hits")

    def test_get_article_live(self):
        # A regional article from the current feed: real JSON-LD
        # articleBody expected (MDR pages carry one). The feed's
        # first item can be a .html topic page (e.g. "Schwerpunkt
        # Carolabrücke") with no article text — try the first few
        # items until one parses as an article.
        feed = json.loads(srv.mdr_regional_news("sachsen", limit=10))
        self.assertNotIn("error", feed)
        self.assertGreater(len(feed["items"]), 0)
        out = None
        tried = []
        for item in feed["items"][:5]:
            tried.append(item["link"])
            out = json.loads(srv.mdr_get_article(item["link"]))
            if "error" not in out:
                break
        self.assertNotIn("error", out, f"no article parsed from {tried}")
        self.assertFalse(out["paywalled"])
        self.assertIn(out["kind"], ("article", "live-ticker", "video"))
        self.assertGreater(out["word_count"], 50)
        print(f"\nLIVE article: {out['word_count']} words, {out['title'][:60]}")

    def test_health_live(self):
        out = json.loads(srv.mdr_health())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["http_status"], 200)


if __name__ == "__main__":
    unittest.main()
