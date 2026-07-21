"""Tests del módulo Gemini: parseo de JSON válido/inválido y reintento único."""

import json
import unittest
from unittest import mock

from config import MIN_NEWS, MAX_NEWS
from summarizers import gemini
from utils import normalize_link

ITEMS = [
    {"source": "TechCrunch", "title": "OpenAI launches GPT-6",
     "link": "https://techcrunch.com/2026/07/21/gpt6/"},
    {"source": "The Verge", "title": "Google cloud outage",
     "link": "https://www.theverge.com/2026/07/21/goog"},
]
BY_NORM = {normalize_link(i["link"]): i for i in ITEMS}


def gemini_api_response(text):
    """Envuelve un texto en la estructura que devuelve la API de Gemini."""
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class FakeResp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestParseDigestJson(unittest.TestCase):
    def test_json_valido(self):
        raw = json.dumps({
            "encabezado": "Hoy domina: OpenAI",
            "noticias": [
                {"titulo": "GPT-6 llegó", "resumen": "OpenAI lanzó GPT-6.",
                 "link": "https://techcrunch.com/2026/07/21/gpt6"},
            ],
        })
        encabezado, noticias = gemini.parse_digest_json(raw, BY_NORM)
        self.assertEqual(encabezado, "Hoy domina: OpenAI")
        self.assertEqual(len(noticias), 1)
        self.assertEqual(noticias[0]["link"], "https://techcrunch.com/2026/07/21/gpt6/")
        self.assertEqual(noticias[0]["source"], "TechCrunch")

    def test_json_invalido_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            gemini.parse_digest_json("esto no es json {", BY_NORM)

    def test_json_sin_noticias_validas_lanza_valueerror(self):
        raw = json.dumps({"encabezado": "x", "noticias": [
            {"titulo": "Inventada", "resumen": "r.", "link": "https://fake.com/no"},
        ]})
        with self.assertRaises(ValueError):
            gemini.parse_digest_json(raw, BY_NORM)


class TestPromptExtra(unittest.TestCase):
    def test_prompt_normal_pide_mezcla(self):
        prompt = gemini.build_prompt(ITEMS, [], "2026-07-21")
        self.assertIn(f"entre {MIN_NEWS} y {MAX_NEWS} noticias", prompt)
        self.assertIn("mezcla", prompt)

    def test_prompt_extra_pide_adicionales_sin_mezcla(self):
        prompt = gemini.build_prompt(ITEMS, [], "2026-07-21",
                                     min_news=3, max_news=3, extra=True)
        self.assertIn("exactamente 3 noticias adicionales", prompt)
        self.assertIn("También hoy:", prompt)
        self.assertNotIn("mezcla", prompt)


class TestReintentoJsonInvalido(unittest.TestCase):
    def test_maximo_un_segundo_intento_por_modelo(self):
        """Con JSON inválido: reintenta UNA vez el mismo modelo y luego pasa
        al siguiente."""
        valido = json.dumps({"encabezado": "ok", "noticias": [
            {"titulo": "GPT-6 llegó", "resumen": "OpenAI lanzó GPT-6.",
             "link": "https://techcrunch.com/2026/07/21/gpt6/"},
        ]})
        respuestas = [
            gemini_api_response("no-es-json {"),   # modelo-a, intento 1
            gemini_api_response("sigue sin ser"),  # modelo-a, reintento único
            gemini_api_response(valido),           # modelo-b, intento 1
        ]
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req.full_url)
            return FakeResp(respuestas[len(calls) - 1])

        with mock.patch.object(gemini, "rank_gemini_models",
                               return_value=["modelo-a", "modelo-b"]), \
             mock.patch.object(gemini.urllib.request, "urlopen", fake_urlopen):
            encabezado, noticias = gemini.summarize_with_gemini(
                ITEMS, "fake-key", [], BY_NORM, "2026-07-21"
            )

        self.assertEqual(len(calls), 3)
        self.assertEqual(sum("modelo-a" in c for c in calls), 2)
        self.assertEqual(sum("modelo-b" in c for c in calls), 1)
        self.assertEqual(encabezado, "ok")
        self.assertEqual(len(noticias), 1)


if __name__ == "__main__":
    unittest.main()
