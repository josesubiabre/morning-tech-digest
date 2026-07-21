"""Tests de validación de noticias: campos, oraciones incompletas y URLs."""

import unittest

from digest.selection import is_incomplete_sentence, is_valid_url, validate_noticias


def noticia(**kwargs):
    base = {
        "titulo": "Titular de prueba",
        "resumen": "Algo pasó y es relevante para la industria.",
        "link": "https://ejemplo.com/nota",
        "source": "TechCrunch",
    }
    base.update(kwargs)
    return base


class TestOracionesIncompletas(unittest.TestCase):
    def test_termina_abruptamente_en_por(self):
        self.assertTrue(is_incomplete_sentence(
            "El objetivo es construir reactores nucleares por"
        ))

    def test_termina_en_por_con_punto_tambien_es_incompleta(self):
        self.assertTrue(is_incomplete_sentence(
            "El objetivo es construir reactores nucleares por."
        ))

    def test_sin_puntuacion_de_cierre(self):
        self.assertTrue(is_incomplete_sentence("La empresa anunció un nuevo producto"))

    def test_oracion_completa(self):
        self.assertFalse(is_incomplete_sentence(
            "El objetivo es construir reactores nucleares portátiles sobre barcazas."
        ))

    def test_vacia_es_incompleta(self):
        self.assertTrue(is_incomplete_sentence(""))


class TestValidacionNoticias(unittest.TestCase):
    def test_descarta_resumen_cortado_en_por(self):
        valida = noticia()
        cortada = noticia(resumen="El objetivo es construir reactores nucleares por",
                          titulo="Bluecore Energy levanta 10 millones")
        result = validate_noticias([valida, cortada])
        self.assertEqual(result, [valida])

    def test_descarta_sin_url(self):
        result = validate_noticias([noticia(), noticia(link="")])
        self.assertEqual(len(result), 1)

    def test_descarta_url_invalida(self):
        self.assertFalse(is_valid_url("no-es-una-url"))
        self.assertFalse(is_valid_url("ftp://viejo.com/x"))
        self.assertTrue(is_valid_url("https://ejemplo.com/nota"))
        result = validate_noticias([noticia(), noticia(link="no-es-una-url")])
        self.assertEqual(len(result), 1)

    def test_descarta_campos_vacios(self):
        result = validate_noticias([
            noticia(),
            noticia(titulo=""),
            noticia(resumen="   "),
        ])
        self.assertEqual(len(result), 1)

    def test_todas_invalidas_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            validate_noticias([noticia(titulo=""), noticia(link="")])


if __name__ == "__main__":
    unittest.main()
