#!/usr/bin/env python3
# ============================================================
# MIA - Probar la voz (genera un MP3 con el motor configurado)
# ============================================================
# Sintetiza una frase de prueba con el motor de voz actual (TTS_ENGINE en .env)
# y guarda 'prueba_voz.mp3' para que lo abras y escuches. Útil para verificar
# tu configuración de ElevenLabs sin montar todo el asistente.
#
#   python probar_voz.py
#   python probar_voz.py "La frase que tú quieras"
# ============================================================
import os
import sys

os.environ.setdefault("USE_MOCK_GPIO", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from config import TTS_ENGINE, ELEVENLABS_API_KEY
from voice import Voice

FRASE = ("¡Hola, bienvenido! Soy Mía, tu bartender. Marchando una Paloma bien fría. "
         "¿Te cuento un secreto mientras te la preparo?")


def main():
    texto = sys.argv[1] if len(sys.argv) > 1 else FRASE

    print(f"Motor configurado (TTS_ENGINE): {TTS_ENGINE}")
    if TTS_ENGINE == "elevenlabs" and not ELEVENLABS_API_KEY:
        print("[AVISO] No hay ELEVENLABS_API_KEY en .env -> se usará edge-tts de respaldo.")

    v = Voice()
    print("Sintetizando...")
    audio = v._synthesize(texto)
    if not audio:
        print("[ERROR] No se generó audio.")
        return

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_voz.mp3")
    with open(out, "wb") as f:
        f.write(audio)
    print(f"Listo. Abre este archivo para escuchar: {out}")
    v.stop()


if __name__ == "__main__":
    main()
