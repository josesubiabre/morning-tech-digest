"""Tests del sender CallMeBot: división en partes y límites de longitud."""

import unittest

from senders import callmebot
from config import CALLMEBOT_CHUNK_CHARS, CALLMEBOT_MAX_CHARS


class TestSplit(unittest.TestCase):
    def test_mensaje_corto_una_sola_parte(self):
        msg = "📰 *Resumen*\n\n*1. Noticia*\nresumen\nhttps://a.com"
        self.assertEqual(callmebot.split_whatsapp_message(msg), [msg])

    def test_partes_respetan_limite(self):
        blocks = [f"*{i}. Noticia {i}*\n" + ("relleno " * 40).strip() + f"\nhttps://e.com/{i}"
                  for i in range(8)]
        msg = "\n\n".join(blocks)
        chunks = callmebot.split_whatsapp_message(msg)
        self.assertGreater(len(chunks), 1)
        for i, c in enumerate(chunks, 1):
            self.assertLessEqual(len(c), CALLMEBOT_CHUNK_CHARS, f"parte {i} excede")
            self.assertLessEqual(len(c), CALLMEBOT_MAX_CHARS, f"parte {i} sobre tope duro")
            # Sin sufijo "Parte i/n": el contenido va limpio
            self.assertNotIn("_Parte", c)

    def test_no_parte_bloques_por_la_mitad(self):
        blocks = [f"*{i}. N{i}*\n" + ("x " * 100).strip() + f"\nhttps://e.com/{i}"
                  for i in range(4)]
        msg = "\n\n".join(blocks)
        chunks = callmebot.split_whatsapp_message(msg)
        for b in blocks:
            self.assertTrue(any(b in c for c in chunks), f"bloque partido: {b[:30]}")

    def test_bloque_gigante_cae_a_corte_por_caracteres(self):
        chunks = callmebot.split_whatsapp_message("x" * 2000)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), CALLMEBOT_CHUNK_CHARS)


class TestLimiteDuro(unittest.TestCase):
    def test_rechaza_texto_sobre_el_maximo_sin_llamar_a_la_red(self):
        # La verificación de longitud ocurre antes de cualquier HTTP, así que
        # este test no toca la red.
        with self.assertRaises(RuntimeError):
            callmebot.send_callmebot_message("x" * (CALLMEBOT_MAX_CHARS + 1),
                                             "56900000000", "clave")


class TestMascaraSecretos(unittest.TestCase):
    def test_mask_secrets(self):
        texto = "Message to: 56900000000 apikey=clave123 ok"
        masked = callmebot._mask_secrets(texto, "56900000000", "clave123")
        self.assertNotIn("56900000000", masked)
        self.assertNotIn("clave123", masked)


if __name__ == "__main__":
    unittest.main()
