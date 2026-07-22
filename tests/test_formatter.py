"""Tests del formato del mensaje: construcción exacta y sanitización."""

import datetime
import unittest

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
        msg = formatter.build_whatsapp_message("Hoy domina: la IA", NOTICIAS, NOW)
        esperado = (
            "📰 *Resumen tech - 21-07-2026*\n"
            "\n"
            "_Hoy domina: la IA_\n"
            "\n"
            "*1. Google lanza Gemini 3.6 Flash*\n"
            "Google liberó nuevos modelos flash.\n"
            "https://techcrunch.com/2026/07/21/google/\n"
            "\n"
            "*2. Nvidia presenta Vera Rubin*\n"
            "Nvidia combina CPUs y GPUs en un solo sistema.\n"
            "https://www.wired.com/story/nvidia/"
        )
        self.assertEqual(msg, esperado)

    def test_numeracion_presente_sin_fuente(self):
        msg = formatter.build_whatsapp_message("", NOTICIAS, NOW)
        self.assertIn("*1. ", msg)
        self.assertIn("*2. ", msg)
        self.assertNotIn("— TechCrunch", msg)
        self.assertNotIn("— Wired", msg)

    def test_sin_separadores_de_underscores(self):
        sucias = [dict(NOTICIAS[0],
                       resumen="Antes __________ después de la ronda de 10 millones.")]
        msg = formatter.build_whatsapp_message(
            "Encabezado ______ con basura", sucias, NOW
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
