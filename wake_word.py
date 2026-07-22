# ============================================================
# MIA - Wake Word local con Porcupine (Picovoice)
# ============================================================
# Escucha pasiva 100% OFFLINE de la palabra "Mia". No consume internet
# ni CPU significativa en reposo (motor optimizado para ARM).
#
# Requiere:
#   - PICOVOICE_ACCESS_KEY en .env (gratis en https://console.picovoice.ai)
#   - Un modelo .ppn de la palabra "Mia" entrenado en Picovoice Console:
#       * Plataforma "Raspberry Pi" para la Pi 3.
#       * Plataforma "Windows" para desarrollo en la laptop.
#     Ruta configurada en PICOVOICE_KEYWORD_PATH.
# ============================================================
import struct

import pvporcupine
import pyaudio

from config import (
    PICOVOICE_ACCESS_KEY,
    PICOVOICE_KEYWORD_PATH,
    PICOVOICE_SENSITIVITY,
    MICROPHONE_DEVICE_INDEX,
)


class WakeWordListener:
    """Bloquea en wait_for_wake() hasta que se detecta la palabra clave.

    Abre y cierra su propio stream de pyaudio en cada espera, para no
    chocar con el stream del grabador de comandos (recorder.py).
    """

    def __init__(self, mute_check=None):
        # Anti-eco: función que retorna True cuando hay que ignorar el micrófono
        # (ej. mientras MIA está hablando por el parlante).
        self._mute_check = mute_check

        self._porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[PICOVOICE_KEYWORD_PATH],
            sensitivities=[PICOVOICE_SENSITIVITY],
        )
        self._pa = pyaudio.PyAudio()
        self._running = True

        print(f"[WAKE] Porcupine listo (frame={self._porcupine.frame_length}, "
              f"rate={self._porcupine.sample_rate}Hz).")

    def set_mute_check(self, check_fn):
        self._mute_check = check_fn

    def _is_muted(self):
        return self._mute_check() if self._mute_check else False

    def wait_for_wake(self):
        """Bloquea hasta detectar la palabra clave. Devuelve True al detectarla,
        False si el listener fue detenido con stop()."""
        stream = self._pa.open(
            rate=self._porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._porcupine.frame_length,
            input_device_index=MICROPHONE_DEVICE_INDEX,
        )
        try:
            print("[WAKE] Escucha pasiva — di 'Mia' para activarme.")
            while self._running:
                pcm = stream.read(self._porcupine.frame_length,
                                  exception_on_overflow=False)
                # Si MIA está hablando, descartamos el audio (anti-eco).
                if self._is_muted():
                    continue

                samples = struct.unpack_from(
                    "h" * self._porcupine.frame_length, pcm
                )
                if self._porcupine.process(samples) >= 0:
                    print("[WAKE] ¡Palabra clave detectada!")
                    return True
            return False
        finally:
            stream.stop_stream()
            stream.close()

    def stop(self):
        self._running = False

    def cleanup(self):
        self._running = False
        try:
            self._porcupine.delete()
        except Exception:
            pass
        try:
            self._pa.terminate()
        except Exception:
            pass
        print("[WAKE] Recursos liberados.")


if __name__ == "__main__":
    # Prueba manual: detectar la palabra clave una vez.
    listener = WakeWordListener()
    try:
        listener.wait_for_wake()
        print("Detectado. Fin de la prueba.")
    finally:
        listener.cleanup()
