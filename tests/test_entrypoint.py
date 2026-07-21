"""Tests del punto de entrada: news_digest.py debe seguir funcionando por CLI."""

import os
import subprocess
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_entrypoint(*args):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GEMINI_API_KEY", "CALLMEBOT_PHONE", "CALLMEBOT_API_KEY")}
    return subprocess.run(
        [sys.executable, "news_digest.py", *args],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120,
    )


class TestEntryPoint(unittest.TestCase):
    """Sin las variables de entorno, el script debe salir ordenadamente con
    código 1 y un mensaje claro — sin tocar la red ni enviar nada. Esto
    verifica que `python news_digest.py` y `--force` siguen funcionando."""

    def test_sin_argumentos(self):
        result = run_entrypoint()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Faltan variables de entorno", result.stderr)

    def test_con_force(self):
        result = run_entrypoint("--force")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Faltan variables de entorno", result.stderr)


if __name__ == "__main__":
    unittest.main()
