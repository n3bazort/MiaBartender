#!/usr/bin/env python3
# ============================================================
# MIA - PRUEBA WEB (avatar animado, sin Raspberry Pi)
# ============================================================
# Arranca el panel web usando el MICRÓFONO DEL NAVEGADOR: verás el avatar de
# MIA en la pantalla y le hablarás con el botón del micrófono (no hace falta
# el micro USB ni la GPIO). MIA responde con voz reproducida en el navegador y
# muestra la secuencia de dispensado simulada en la consola.
#
# Equivale a:  python main.py --web
#
# Dependencias:
#   pip install groq edge-tts gpiozero python-dotenv flask flask-socketio
#
# Requiere GROQ_API_KEY en .env. Luego abre la URL que se imprime en consola.
# En una plataforma web (Replit, etc.) usa la URL pública que te dé la plataforma.
# ============================================================
import os
import sys

# Forzar GPIO simulado y micrófono del navegador antes de importar el resto.
os.environ.setdefault("USE_MOCK_GPIO", "1")
os.environ["MIA_INPUT"] = "web"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

import server

if __name__ == "__main__":
    server.run(web_mic=True)
