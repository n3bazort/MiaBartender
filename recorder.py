# ============================================================
# MIA - Grabador de comandos (pyaudio + VAD por energía)
# ============================================================
# Tras el wake word, graba el comando del usuario y devuelve un WAV en
# memoria listo para enviar a Groq Whisper.
#
# La detección de fin de frase (VAD) es la misma idea del ear.py original
# (_listen_once): energía RMS por buffer + contador de silencio.
# ============================================================
import audioop
import io
import wave

import pyaudio

from audio_devices import resolve_input_device
from config import (
    MICROPHONE_DEVICE_INDEX,
    MIN_ENERGY_THRESHOLD,
    SILENCE_PAUSE_SECONDS,
    COMMAND_TIMEOUT,
    COMMAND_PHRASE_LIMIT,
)

SAMPLE_RATE = 16000     # 16 kHz es suficiente para voz y lo que espera Whisper
SAMPLE_WIDTH = 2        # 16-bit
CHUNK = 512             # frames por buffer


class Recorder:
    """Graba un comando de voz con detección de inicio y fin de habla."""

    def __init__(self):
        self._pa = pyaudio.PyAudio()
        # Resuelve "auto" al índice del micro USB de la Pi (o None = el del sistema).
        self._device_index = resolve_input_device(MICROPHONE_DEVICE_INDEX, self._pa)

    def record_command(self):
        """Graba hasta detectar silencio tras el habla.

        Devuelve los bytes de un archivo WAV completo (cabecera incluida),
        o None si el usuario no habló dentro de COMMAND_TIMEOUT.
        """
        stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK,
            input_device_index=self._device_index,
        )
        try:
            seconds_per_buffer = CHUNK / SAMPLE_RATE
            pause_buffers = int(SILENCE_PAUSE_SECONDS / seconds_per_buffer)
            timeout_buffers = int(COMMAND_TIMEOUT / seconds_per_buffer)

            audio_data = bytearray()
            listening = False       # ya empezó a hablar
            silent_count = 0
            elapsed = 0

            print("[REC] Grabando comando... habla ahora.")
            while True:
                buffer = stream.read(CHUNK, exception_on_overflow=False)
                elapsed += 1

                energy = audioop.rms(buffer, SAMPLE_WIDTH)
                is_speech = energy > MIN_ENERGY_THRESHOLD

                if not listening:
                    if is_speech:
                        listening = True
                        audio_data.extend(buffer)
                    elif elapsed > timeout_buffers:
                        print("[REC] Timeout: no se detectó voz.")
                        return None
                else:
                    audio_data.extend(buffer)
                    if is_speech:
                        silent_count = 0
                    else:
                        silent_count += 1
                        if silent_count > pause_buffers:
                            break   # fin de frase por silencio

                    # Corte defensivo por duración máxima
                    duration = len(audio_data) / (SAMPLE_RATE * SAMPLE_WIDTH)
                    if duration > COMMAND_PHRASE_LIMIT:
                        print("[REC] Límite de duración alcanzado.")
                        break

            print(f"[REC] Comando capturado "
                  f"({len(audio_data) / (SAMPLE_RATE * SAMPLE_WIDTH):.1f}s).")
            return self._to_wav(bytes(audio_data))
        finally:
            stream.stop_stream()
            stream.close()

    @staticmethod
    def _to_wav(pcm_bytes):
        """Envuelve PCM crudo en un contenedor WAV en memoria."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(SAMPLE_WIDTH)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def cleanup(self):
        try:
            self._pa.terminate()
        except Exception:
            pass
