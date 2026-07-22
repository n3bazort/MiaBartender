#!/usr/bin/env python3
# ============================================================
# MIA - SIMULADOR WEB (avatar animado, sin Raspberry Pi ni micrófono)
# ============================================================
# Arranca el panel web en MODO SIMULADOR: verás el avatar de MIA en el
# navegador y le escribirás los comandos en un cuadro de texto (no hace falta
# micrófono). MIA responde con voz (reproducida en el navegador) y muestra la
# secuencia de dispensado simulada en la consola.
#
# Dependencias:
#   pip install groq edge-tts gpiozero python-dotenv flask flask-socketio
#
# Requiere GROQ_API_KEY en .env. Luego abre la URL que se imprime en consola.
# En una plataforma web (Replit, etc.) usa la URL pública que te dé la plataforma.
# ============================================================
import os
import sys

# Forzar GPIO simulado antes de importar cualquier módulo de hardware.
os.environ.setdefault("USE_MOCK_GPIO", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

import server

if __name__ == "__main__":
    server.run(simulator=True)
