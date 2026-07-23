# ============================================================
# MIA - Voz (TTS configurable: ElevenLabs o edge-tts)
# ============================================================
# Genera el MP3 de la voz y lo reproduce por el parlante local de la Raspberry
# Pi con mpg123 (ruta PRINCIPAL).
#
# Motor de voz (config.TTS_ENGINE):
#   - "elevenlabs": voz muy natural y con emoción (requiere ELEVENLABS_API_KEY).
#   - "edge":       edge-tts de Microsoft, gratis y sin cuenta (más robótica).
# Si ElevenLabs falla (sin key, sin crédito o sin red), cae automáticamente a edge.
#
# Si el panel web está activo, además emite el MP3 en base64 vía el callback
# on_audio_ready para que el navegador lo reproduzca y anime el avatar.
# ============================================================
import asyncio
import base64
import json
import os
import subprocess
import tempfile
import threading
import urllib.request
from queue import Queue

import edge_tts

from config import (
    TTS_ENGINE, TTS_VOICE, AUDIO_PLAYER_CMD,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL,
)


class Voice:
    """Síntesis de voz en un worker de cola. speak() encola, no bloquea."""

    def __init__(self):
        self._queue = Queue()
        self.is_speaking = False
        self._running = True

        # Motor de voz activo. Si se pidió ElevenLabs sin API key, avisa y usa edge.
        self._engine = TTS_ENGINE
        if self._engine == "elevenlabs" and not ELEVENLABS_API_KEY:
            print("[VOICE][AVISO] TTS_ENGINE=elevenlabs pero falta ELEVENLABS_API_KEY. "
                  "Usando edge-tts. Pon tu clave en .env para la voz natural.")
            self._engine = "edge"
        print(f"[VOICE] Motor de voz: {self._engine}")

        # Reproducción por el parlante local (mpg123). Se puede desactivar en
        # el simulador web, donde el audio se reproduce solo en el navegador.
        self.local_playback = True

        # Callback opcional para el panel web: on_audio_ready(texto, audio_b64).
        self.on_audio_ready = None

        self._worker = threading.Thread(
            target=self._process_queue, daemon=True, name="VoiceWorker"
        )
        self._worker.start()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def speak(self, text):
        """Encola texto para hablar (no bloquea)."""
        if text and text.strip():
            self._queue.put(text.strip())

    def wait_until_done(self):
        """Bloquea hasta que la cola de voz se haya procesado por completo."""
        self._queue.join()

    def clear_queue(self):
        """Vacía la cola (para interrupciones)."""
        with self._queue.mutex:
            self._queue.queue.clear()

    def stop(self):
        self._running = False
        self._queue.put(None)

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _process_queue(self):
        while self._running:
            try:
                text = self._queue.get(timeout=1)
            except Exception:
                continue
            if text is None:
                self._queue.task_done()
                break
            try:
                self._speak_sync(text)
            finally:
                self._queue.task_done()

    def _speak_sync(self, text):
        self.is_speaking = True
        print(f"[VOICE] MIA dice: {text}")
        try:
            audio_bytes = self._synthesize(text)
            if not audio_bytes:
                print("[VOICE][AVISO] edge-tts no devolvió audio.")
                return

            # Ruta principal: reproducir localmente por el parlante.
            if self.local_playback:
                self._play_local(audio_bytes)

            # Ruta secundaria: emitir al navegador si hay un cliente escuchando.
            if self.on_audio_ready:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                self.on_audio_ready(text, audio_b64)
        except Exception as e:
            print(f"[VOICE][ERROR] Falló la síntesis/reproducción: {e}")
        finally:
            self.is_speaking = False

    def _synthesize(self, text):
        """Genera el MP3 en memoria con el motor activo (con respaldo a edge-tts)."""
        if self._engine == "elevenlabs":
            try:
                audio = self._synthesize_elevenlabs(text)
                if audio:
                    return audio
                print("[VOICE][AVISO] ElevenLabs no devolvió audio; uso edge-tts.")
            except Exception as e:
                print(f"[VOICE][AVISO] Falló ElevenLabs ({e}); uso edge-tts.")
        return self._synthesize_edge(text)

    @staticmethod
    def _synthesize_edge(text):
        """Genera el MP3 en memoria con edge-tts (Microsoft, gratis)."""
        async def _run():
            communicate = edge_tts.Communicate(text, TTS_VOICE)
            audio = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            return audio
        return asyncio.run(_run())

    @staticmethod
    def _synthesize_elevenlabs(text):
        """Genera el MP3 en memoria con la API de ElevenLabs (voz natural)."""
        url = (f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
               f"?output_format=mp3_44100_128")
        body = json.dumps({
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            # Ajustes de expresividad: algo de variación y estilo para que no sea plana.
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            # Mostrar el detalle real de ElevenLabs (clave inválida vs sin permiso, etc.)
            try:
                detail = e.read().decode("utf-8", "ignore")[:300]
            except Exception:
                detail = ""
            raise RuntimeError(f"HTTP {e.code} — {detail}") from None

    @staticmethod
    def _play_local(audio_bytes):
        """Reproduce el MP3 con mpg123 desde un archivo temporal."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            subprocess.run(
                [AUDIO_PLAYER_CMD, "-q", tmp_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            print(f"[VOICE][ERROR] '{AUDIO_PLAYER_CMD}' no está instalado "
                  f"(en la Pi: sudo apt install mpg123).")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


if __name__ == "__main__":
    # Prueba manual: sintetizar y reproducir una frase.
    v = Voice()
    v.speak("Hola, soy MIA, tu bartender. ¿Qué te preparo hoy?")
    v.wait_until_done()
    v.stop()
