# ============================================================
# MIA - Wake Word local ("Mia"), 100% GRATIS y sin cuenta
# ============================================================
# Escucha pasiva OFFLINE de la palabra "Mia". Dos motores:
#
#   1. VOSK (por defecto) — libre, sin claves, sin registro. Usa un modelo
#      pequeño de español (~40 MB) que se descarga una sola vez. Reconoce con
#      una GRAMÁTICA RESTRINGIDA a la palabra clave, así que es preciso y
#      ligero incluso en una Raspberry Pi 3.
#
#   2. PORCUPINE (opcional) — solo si defines PICOVOICE_ACCESS_KEY en el .env.
#      Consume menos CPU, pero exige cuenta en Picovoice.
#
# El motor se elige solo: si hay clave de Picovoice la usa, si no, Vosk.
# ============================================================
import json
import os
import struct
import unicodedata


def _sin_acentos(texto):
    """minúsculas y sin tildes, para comparar la palabra de activación.

    Vosk transcribe fonéticamente: "Mia" puede salir como "mia" o "mía" según
    cómo se pronuncie. Comparando sin acentos no hay que listar cada variante.
    """
    texto = (texto or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")

import pyaudio

from audio_devices import resolve_input_device
from config import (
    PICOVOICE_ACCESS_KEY,
    PICOVOICE_KEYWORD_PATH,
    PICOVOICE_SENSITIVITY,
    MICROPHONE_DEVICE_INDEX,
    WAKE_KEYWORD,
    WAKE_KEYWORD_DISPLAY,
    WAKE_ENGINE,
    VOSK_MODEL_PATH,
    VOSK_WAKE_VARIANTS,
)


def elegir_motor():
    """Decide qué motor de wake word usar según la configuración disponible."""
    if WAKE_ENGINE in ("vosk", "porcupine"):
        return WAKE_ENGINE            # forzado por el .env
    if PICOVOICE_ACCESS_KEY:
        return "porcupine"            # hay clave: usar el motor más ligero
    return "vosk"                     # por defecto: gratis y sin cuenta


class _MotorVosk:
    """Detector de palabra clave con Vosk (reconocimiento libre en español).

    Por qué reconocimiento LIBRE y no una gramática de una sola palabra:
    con el vocabulario completo, Vosk distingue "Mia" de palabras parecidas
    y muy comunes como "mira" o "milagro". Con gramática restringida esas dos
    activaban a MIA por error (comprobado). El modelo pequeño de español corre
    de sobra en tiempo real en una Pi 3.

    Solo se miran los resultados FINALES: los parciales de Vosk son
    especulativos y cambian de opinión a mitad de frase.
    """

    sample_rate = 16000
    frame_length = 4000        # 0.25 s por bloque

    def __init__(self):
        from vosk import Model, KaldiRecognizer, SetLogLevel

        SetLogLevel(-1)        # silenciar el log interno de Kaldi

        if not os.path.isdir(VOSK_MODEL_PATH):
            raise FileNotFoundError(
                f"No encuentro el modelo de Vosk en '{VOSK_MODEL_PATH}'.\n"
                f"        Descárgalo con:  python descargar_modelo.py"
            )

        self._model = Model(VOSK_MODEL_PATH)
        self._rec = KaldiRecognizer(self._model, self.sample_rate)
        self._variantes = {_sin_acentos(v) for v in VOSK_WAKE_VARIANTS}

    def procesar(self, pcm_bytes):
        """True si en la frase recién cerrada se dijo la palabra clave."""
        if not self._rec.AcceptWaveform(pcm_bytes):
            return False
        texto = json.loads(self._rec.Result()).get("text", "")
        if not texto:
            return False
        palabras = {_sin_acentos(p) for p in texto.split()}
        return bool(palabras & self._variantes)

    def reset(self):
        self._rec.Reset()

    def cleanup(self):
        pass


class _MotorPorcupine:
    """Detector con Picovoice Porcupine (requiere PICOVOICE_ACCESS_KEY)."""

    def __init__(self):
        import pvporcupine

        if PICOVOICE_KEYWORD_PATH and os.path.exists(PICOVOICE_KEYWORD_PATH):
            self._pp = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keyword_paths=[PICOVOICE_KEYWORD_PATH],
                sensitivities=[PICOVOICE_SENSITIVITY],
            )
        else:
            self._pp = pvporcupine.create(
                access_key=PICOVOICE_ACCESS_KEY,
                keywords=[WAKE_KEYWORD],
                sensitivities=[PICOVOICE_SENSITIVITY],
            )
        self.sample_rate = self._pp.sample_rate
        self.frame_length = self._pp.frame_length

    def procesar(self, pcm_bytes):
        samples = struct.unpack_from("h" * self.frame_length, pcm_bytes)
        return self._pp.process(samples) >= 0

    def reset(self):
        pass

    def cleanup(self):
        try:
            self._pp.delete()
        except Exception:
            pass


class WakeWordListener:
    """Bloquea en wait_for_wake() hasta que se detecta la palabra clave.

    Abre y cierra su propio stream de pyaudio en cada espera, para no
    chocar con el stream del grabador de comandos (recorder.py).
    """

    def __init__(self, mute_check=None):
        # Anti-eco: función que retorna True cuando hay que ignorar el micrófono
        # (ej. mientras MIA está hablando por el parlante).
        self._mute_check = mute_check

        motor = elegir_motor()
        if motor == "porcupine":
            self._motor = _MotorPorcupine()
        else:
            self._motor = _MotorVosk()
        self.engine = motor
        self.keyword = WAKE_KEYWORD_DISPLAY

        self._pa = pyaudio.PyAudio()
        self._device_index = resolve_input_device(MICROPHONE_DEVICE_INDEX, self._pa)
        self._running = True

        print(f"[WAKE] Motor '{motor}' listo — palabra de activación: "
              f"'{self.keyword}' (rate={self._motor.sample_rate}Hz).")

    def set_mute_check(self, check_fn):
        self._mute_check = check_fn

    def _is_muted(self):
        return self._mute_check() if self._mute_check else False

    def wait_for_wake(self):
        """Bloquea hasta detectar la palabra clave. Devuelve True al detectarla,
        False si el listener fue detenido con stop()."""
        stream = self._pa.open(
            rate=self._motor.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._motor.frame_length,
            input_device_index=self._device_index,
        )
        self._motor.reset()
        try:
            print(f"[WAKE] Escucha pasiva — di '{self.keyword}' para activarme.")
            while self._running:
                pcm = stream.read(self._motor.frame_length,
                                  exception_on_overflow=False)
                # Si MIA está hablando, descartamos el audio (anti-eco).
                if self._is_muted():
                    continue

                if self._motor.procesar(pcm):
                    print("[WAKE] ¡Palabra clave detectada!")
                    self._motor.reset()
                    return True
            return False
        finally:
            stream.stop_stream()
            stream.close()

    def stop(self):
        self._running = False

    def cleanup(self):
        self._running = False
        self._motor.cleanup()
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
