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
import base64
import re
import sys
import threading
import time
import unicodedata

import glob
import os

from flask import Flask, render_template
from flask_socketio import SocketIO

from assistant import VoiceAssistant
from config import (
    WEB_PANEL_PORT, MUSIC_DIR, MUSIC_VOLUME, VOICE_VOLUME, BOMBAS_CONFIG,
    RECETAS_COCTELES, INPUT_MODE, WAKE_KEYWORD, WAKE_KEYWORD_DISPLAY,
    VOSK_WAKE_VARIANTS,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

mia = None


# "local" = micrófono USB + wake word en la Pi (audio por los parlantes de la Pi).
# "web"   = el navegador captura el micrófono y reproduce la voz de MIA. No se
#           abre ningún micrófono local: ideal para probar desde la laptop.
WEB_MIC_MODE = (INPUT_MODE == "web")


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

    if WEB_MIC_MODE:
        # El navegador captura el micro y reproduce la voz: no se abre el
        # micrófono local ni el wake word, y no suena el parlante de esta máquina.
        mia.voice.local_playback = False
        print("[SERVER] Modo MICRÓFONO WEB: habla desde el navegador "
              "(botón del micrófono).")
    else:
        # Modo Raspberry Pi: wake word "Mia" + micrófono USB local.
        mia.start()


def quitar_wake_word(texto):
    """Comprueba la palabra de activación y devuelve el pedido sin ella.

    Devuelve None si no se nombró a MIA (hay que ignorar el clip), o el texto
    restante (posiblemente vacío si solo se dijo "Mia").
    """
    norm = unicodedata.normalize("NFD", (texto or "").lower())
    norm = "".join(c for c in norm if unicodedata.category(c) != "Mn")

    variantes = {v for v in VOSK_WAKE_VARIANTS} | {WAKE_KEYWORD}
    variantes = {
        "".join(c for c in unicodedata.normalize("NFD", v)
                if unicodedata.category(c) != "Mn")
        for v in variantes
    }

    palabras = re.findall(r"[a-z0-9]+", norm)
    if not (set(palabras) & variantes):
        return None

    # Quitar la palabra de activación (y la coma/vocativo que suele seguirla).
    resto = re.sub(r"\b(" + "|".join(re.escape(v) for v in variantes) + r")\b",
                   " ", norm)
    resto = re.sub(r"\s+", " ", resto).strip(" ,.:;-¿?¡!")

    # Devolver el tramo equivalente del texto ORIGINAL (con acentos y signos)
    # cuando se pueda; si no, el normalizado ya sirve para el LLM.
    return resto


@socketio.on("sim_command")
def handle_sim_command(data):
    """Comando de texto (herramienta de depuración; la UI ya no lo usa)."""
    if not mia:
        return
    text = (data or {}).get("text", "").strip()
    if not text:
        return
    print(f"[SERVER] Comando de texto: {text}")
    # Procesar en un hilo para no bloquear el servidor de sockets.
    threading.Thread(target=mia.handle_text, args=(text,), daemon=True).start()


@socketio.on("voice_command")
def handle_voice_command(data):
    """Audio grabado con el micrófono del NAVEGADOR.

    El navegador manda el clip en base64 (WebM/Opus). Aquí se transcribe con
    Groq Whisper y se procesa igual que un comando dicho por el micro de la Pi.
    """
    if not mia:
        return

    payload = data or {}
    audio_b64 = payload.get("audio_b64") or ""
    if not audio_b64:
        return

    ext = (payload.get("ext") or "webm").lower()
    # Micrófono ABIERTO: el clip debe empezar por la palabra de activación.
    # Botón "pulsar para hablar": la intención ya es explícita, no hace falta.
    requiere_wake = bool(payload.get("requiere_wake"))

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as e:
        print(f"[SERVER][ERROR] Audio del navegador inválido: {e}")
        return

    print(f"[SERVER] Audio recibido del navegador ({len(audio_bytes) / 1024:.0f} KB, "
          f"wake={'sí' if requiere_wake else 'no'}).")

    def _procesar():
        # Pase lo que pase, el navegador tiene que recibir una respuesta: si
        # este hilo muere en silencio, el botón del micrófono se queda
        # bloqueado en "Procesando..." para siempre.
        try:
            from stt import transcribe

            # Con micrófono ABIERTO no se muestra NADA todavía: mientras no se
            # sepa si la nombraron, MIA no debe reaccionar. La transcripción se
            # hace en segundo plano y la pantalla sigue como si nada.
            if not requiere_wake:
                socketio.emit("state_update", {"state": "thinking", "text": "Transcribiendo..."})

            text = transcribe(audio_bytes, filename=f"comando.{ext}")
            if not text:
                if not requiere_wake:
                    socketio.emit("mic_error", {"message": "No te escuché bien, ¿me repites?"})
                    socketio.emit("state_update", {"state": "idle", "text": ""})
                else:
                    socketio.emit("mic_idle", {})
                return

            if requiere_wake:
                limpio = quitar_wake_word(text)
                if limpio is None:
                    # Se habló, pero sin nombrar a MIA: se ignora por completo.
                    # Ni animación, ni subtítulo, ni cambio de estado: para la
                    # pantalla es como si nadie hubiera hablado.
                    print(f"[SERVER] Sin palabra de activación, ignorado: {text!r}")
                    socketio.emit("mic_idle", {})
                    return
                # Ya sabemos que la nombraron: AHORA sí reacciona.
                text = limpio or "¿Qué me recomiendas?"
                socketio.emit("state_update", {"state": "thinking", "text": text})

            socketio.emit("user_said", {"text": text})
            mia.handle_text(text)
        except Exception as e:
            import traceback
            print(f"[SERVER][ERROR] Falló el procesado de voz: {e}")
            traceback.print_exc()
            socketio.emit("mic_error", {"message": "Se me trabó algo, inténtalo otra vez"})
            socketio.emit("state_update", {"state": "idle", "text": ""})

    threading.Thread(target=_procesar, daemon=True).start()


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
    # La carta se genera desde RECETAS_COCTELES: así la pantalla nunca queda
    # desincronizada con las recetas reales.
    drinks = [
        {"nombre": nombre, "ingredientes": list(receta.keys())}
        for nombre, receta in RECETAS_COCTELES.items()
    ]
    return render_template(
        "index.html",
        music_tracks=tracks,
        music_volume=MUSIC_VOLUME,
        voice_volume=VOICE_VOLUME,
        pumps=pumps,
        max_seg=max_seg,
        drinks=drinks,
        web_mic=WEB_MIC_MODE,
        wake_word=WAKE_KEYWORD_DISPLAY,
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


def _local_urls():
    """URLs por las que se puede abrir el panel (útil para saber la IP de la Pi)."""
    import socket as _socket

    urls = [f"http://localhost:{WEB_PANEL_PORT}"]
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))          # no envía nada: solo resuelve la IP local
        ip = s.getsockname()[0]
        s.close()
        urls.append(f"http://{ip}:{WEB_PANEL_PORT}")
    except Exception:
        pass
    return urls


def run(web_mic=None):
    """Arranca MIA + el servidor web. Bloquea hasta Ctrl+C.

    web_mic=True: el micrófono lo pone el navegador (pruebas desde la laptop).
    web_mic=False: micrófono USB local + wake word (Raspberry Pi).
    """
    global WEB_MIC_MODE
    if web_mic is not None:
        WEB_MIC_MODE = web_mic

    backend = threading.Thread(target=_start_mia_backend, daemon=True)
    backend.start()
    time.sleep(1)

    entrada = "micrófono del NAVEGADOR" if WEB_MIC_MODE else "micrófono LOCAL + wake word 'Mia'"
    print("\n" + "=" * 56)
    print("PANEL WEB DE MIA INICIADO")
    print(f"Entrada de voz: {entrada}")
    for url in _local_urls():
        print(f"  Abre  {url}")
    print("=" * 56 + "\n")

    socketio.run(app, host="0.0.0.0", port=WEB_PANEL_PORT,
                 debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run()
