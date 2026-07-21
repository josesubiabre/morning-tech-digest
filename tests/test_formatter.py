"""Tests del formato del mensaje: construcción exacta y sanitización."""

import datetime
import unittest
from unittest import mock

from digest import formatter

NOW = datetime.datetime(2026, 7, 21, 8, 0)

NOTICIAS = [
    {"titulo": "Google lanza Gemini 3.6 Flash", "source": "TechCrunch",
     "resumen": "Google liberó nuevos modelos flash.",
     "link": "https://techcrunch.com/2026/07/21/google/"},
    {"titulo": "Nvidia presenta Vera Rubin", "source": "Wired",
     "resumen": "Nvidia combina CPUs y GPUs en un solo sistema.",
     "link": "https://www.wired.com/story/nvidia/"},
]


class TestConstruccionMensaje(unittest.TestCase):
    def test_mensaje_exacto(self):
        with mock.patch.object(formatter, "digest_file_url", return_value=None):
            msg = formatter.build_whatsapp_message(
                "Hoy domina: la IA", NOTICIAS, NOW, "2026-07-21"
            )
        esperado = (
            "📰 *Resumen tech - 21-07-2026*\n"
            "\n"
            "_Hoy domina: la IA_\n"
            "\n"
            "*1. Google lanza Gemini 3.6 Flash* — TechCrunch\n"
            "Google liberó nuevos modelos flash.\n"
            "https://techcrunch.com/2026/07/21/google/\n"
            "\n"
            "*2. Nvidia presenta Vera Rubin* — Wired\n"
            "Nvidia combina CPUs y GPUs en un solo sistema.\n"
            "https://www.wired.com/story/nvidia/"
        )
        self.assertEqual(msg, esperado)

    def test_numeracion_y_fuente_presentes(self):
        with mock.patch.object(formatter, "digest_file_url", return_value=None):
            msg = formatter.build_whatsapp_message("", NOTICIAS, NOW, "2026-07-21")
        self.assertIn("*1. ", msg)
        self.assertIn("*2. ", msg)
        self.assertIn("— TechCrunch", msg)
        self.assertIn("— Wired", msg)

    def test_sin_separadores_de_underscores(self):
        sucias = [dict(NOTICIAS[0],
                       resumen="Antes __________ después de la ronda de 10 millones.")]
        with mock.patch.object(formatter, "digest_file_url", return_value=None):
            msg = formatter.build_whatsapp_message(
                "Encabezado ______ con basura", sucias, NOW, "2026-07-21"
            )
        self.assertNotIn("___", msg)
        self.assertNotIn("__________", msg)

    def test_sanitize(self):
        self.assertEqual(
            formatter.sanitize_whatsapp_text("hola __________ mundo"),
            "hola mundo",
        )
        self.assertEqual(
            formatter.sanitize_whatsapp_text("línea ------ cortada"),
            "línea cortada",
        )
        self.assertEqual(formatter.sanitize_whatsapp_text(None), "")


if __name__ == "__main__":
    unittest.main()
