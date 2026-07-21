"""Tests del collector RSS: parseo desde bytes ya descargados y feeds caídos."""

import unittest
from unittest import mock

from collectors import rss

FEED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Feed de prueba</title>
<item>
<title>Titular uno</title>
<link>https://ejemplo.com/uno</link>
<description>Descripcion &lt;b&gt;con html&lt;/b&gt; y texto</description>
</item>
<item>
<title>Titular dos</title>
<link>https://ejemplo.com/dos</link>
<description>Descripcion dos</description>
</item>
</channel></rss>
"""


def fetch_with(feeds, fake_get):
    with mock.patch.object(rss, "RSS_FEEDS", feeds), \
         mock.patch.object(rss, "http_get_bytes", side_effect=fake_get):
        return rss.fetch_rss_items()


class TestFetchRssItems(unittest.TestCase):
    def test_parsea_feed_descargado(self):
        items = fetch_with({"Prueba": "https://ejemplo.com/feed"},
                           lambda url, timeout=None: FEED_XML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["source"], "Prueba")
        self.assertEqual(items[0]["title"], "Titular uno")
        self.assertEqual(items[0]["link"], "https://ejemplo.com/uno")
        self.assertNotIn("<", items[0]["excerpt"])  # el html viene limpio
        self.assertIn("con html", items[0]["excerpt"])

    def test_feed_caido_no_aborta_los_demas(self):
        def fake_get(url, timeout=None):
            if "caido" in url:
                raise OSError("timeout simulado")
            return FEED_XML

        items = fetch_with(
            {"Caido": "https://caido.com/feed", "Sana": "https://sana.com/feed"},
            fake_get,
        )
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i["source"] == "Sana" for i in items))

    def test_feed_ilegible_se_descarta(self):
        items = fetch_with({"Basura": "https://ejemplo.com/feed"},
                           lambda url, timeout=None: b"<html>esto no es rss</html>")
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
