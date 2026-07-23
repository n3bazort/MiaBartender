# ============================================================
# MIA - Panel Web OPCIONAL (Flask-SocketIO, avatar animado)
# ============================================================
# Visor pasivo del asistente de voz local: muestra el estado (escuchando,
# pensando, preparando) y reproduce el audio de MIA en el navegador,
# animando el avatar. NO controla el hardware ni el micrófono; MIA sigue
# funcionando por voz local. Solo se arranca si ENABLE_WEB_PANEL=True.
#
# Se podó la lógica antigua de auto-descubrimiento de IP del celular (S25)
# y de visión por cámara: ya no aplican a la arquitectura de un solo proceso.
# ============================================================
import sys
import threading
import time

import glob
import os

from flask import Flask, render_template
from flask_socketio import SocketIO

from assistant import VoiceAssistant
from config import (
    WEB_PANEL_PORT, MUSIC_DIR, MUSIC_VOLUME, VOICE_VOLUME, BOMBAS_CONFIG,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

mia = None


# True = modo simulador: NO se abre el micrófono ni el wake word; los comandos
# llegan escritos desde el navegador (evento 'sim_command'). Ideal para probar
# en una plataforma web sin hardware.
SIMULATOR_MODE = False


def _start_mia_backend():
    """Instancia MIA y conecta sus estados/audio al Socket.IO."""
    global mia
    mia = VoiceAssistant(socketio)

    def on_state_change(new_state, data=None):
        if new_state == "emotion":
            socketio.emit("emotion_update", {"emotion": data or "neutral"})
        else:
            socketio.emit("state_update", {
                "state": new_state,
                "text": data if isinstance(data, str) else "",
            })

    mia.on_state_change = on_state_change

    # Espejar el audio de MIA hacia el navegador (además del parlante local).
    def push_audio(text, audio_b64):
        socketio.emit("play_audio_chunk", {"text": text, "audio_b64": audio_b64})

    mia.voice.on_audio_ready = push_audio

    if SIMULATOR_MODE:
        # Sin parlante local (el navegador reproduce el audio) y sin bucle de voz.
        mia.voice.local_playback = False
        print("[SERVER] Modo SIMULADOR: escribe los comandos desde el navegador.")
    else:
        # Modo real: arranca el bucle de voz (wake word + micrófono).
        mia.start()


@socketio.on("sim_command")
def handle_sim_command(data):
    """Comando de texto escrito desde el navegador (modo simulador)."""
    if not mia:
        return
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    print(f"[SERVER] Comando simulado: {text}")
    # Procesar en un hilo para no bloquear el servidor de sockets.
    threading.Thread(target=mia.handle_text, args=(text,), daemon=True).start()


@app.route("/")
def index():
    # Lista de pistas de música disponibles (para el reproductor del navegador).
    tracks = [
        "/static/music/" + os.path.basename(p)
        for p in sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")))
    ]
    # Layout de las bombas para dibujar el riel del recorrido del vaso.
    pumps = [
        {"pump": k, "seg": v["seg"], "ingrediente": v["ingrediente"]}
        for k, v in sorted(BOMBAS_CONFIG.items(), key=lambda kv: kv[1]["seg"])
    ]
    max_seg = max(v["seg"] for v in BOMBAS_CONFIG.values())
    return render_template(
        "index.html",
        music_tracks=tracks,
        music_volume=MUSIC_VOLUME,
        voice_volume=VOICE_VOLUME,
        pumps=pumps,
        max_seg=max_seg,
    )


@socketio.on("request_state")
def handle_request_state():
    if mia:
        socketio.emit("state_update", {"state": mia.state, "text": ""})
    else:
        socketio.emit("state_update", {"state": "idle", "text": ""})


@socketio.on("audio_finished")
def handle_audio_finished():
    # El navegador terminó su cola de audio. No bloqueamos el flujo local por
    # esto (la reproducción principal es el parlante), así que solo lo registramos.
    pass


def run(simulator=False):
    """Arranca MIA + el servidor web. Bloquea hasta Ctrl+C.

    simulator=True: sin micrófono; los comandos se escriben en el navegador.
    """
    global SIMULATOR_MODE
    SIMULATOR_MODE = simulator

    backend = threading.Thread(target=_start_mia_backend, daemon=True)
    backend.start()
    time.sleep(1)

    print("\n" + "=" * 50)
    print("PANEL WEB DE MIA INICIADO")
    print(f"Abre http://[IP_DE_LA_PI]:{WEB_PANEL_PORT} en tu navegador.")
    print("=" * 50 + "\n")

    socketio.run(app, host="0.0.0.0", port=WEB_PANEL_PORT,
                 debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run()
