"""Tests del estado: cobertura reciente con y sin el día actual."""

import unittest

from state import recent_coverage

STATE = {
    "sent": {},
    "history": {
        "2026-07-20": [
            {"titulo": "Noticia de ayer", "link": "ayer.com/a",
             "source_title": "yesterday news"},
        ],
        "2026-07-21": [
            {"titulo": "Noticia de hoy", "link": "hoy.com/h",
             "source_title": "today news"},
        ],
    },
}


class TestRecentCoverage(unittest.TestCase):
    def test_excluye_hoy_por_defecto(self):
        """Un reenvío con --force no debe filtrarse a sí mismo."""
        topics, links, titles = recent_coverage(STATE, "2026-07-21")
        self.assertIn("Noticia de ayer", topics)
        self.assertIn("ayer.com/a", links)
        self.assertNotIn("Noticia de hoy", topics)
        self.assertNotIn("hoy.com/h", links)
        self.assertNotIn("today news", titles)

    def test_incluye_hoy_para_noticias_extra(self):
        """El modo --more no debe repetir lo del digest de la mañana."""
        topics, links, titles = recent_coverage(STATE, "2026-07-21",
                                                include_today=True)
        self.assertIn("Noticia de hoy", topics)
        self.assertIn("hoy.com/h", links)
        self.assertIn("today news", titles)


if __name__ == "__main__":
    unittest.main()
