# ============================================================
# MIA - STT (Voz a Texto) con Groq Whisper
# ============================================================
# Transcripción en la nube con el modelo Whisper de Groq.
# whisper-large-v3-turbo: el de menor latencia (clave para UX de voz).
# ============================================================
from groq import Groq

from config import GROQ_API_KEY, GROQ_STT_MODEL, STT_LANGUAGE

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def transcribe(wav_bytes):
    """Transcribe un WAV (bytes) a texto en español.

    Devuelve el texto transcrito, o None si el audio no produjo texto
    o hubo un error de red/API.
    """
    if not wav_bytes:
        return None

    try:
        client = _get_client()
        result = client.audio.transcriptions.create(
            model=GROQ_STT_MODEL,
            # (nombre, bytes) — el nombre solo indica el formato al API
            file=("comando.wav", wav_bytes),
            language=STT_LANGUAGE,
            response_format="text",
        )
        # Con response_format="text" el SDK devuelve un str directamente
        text = result.strip() if isinstance(result, str) else str(result).strip()
        if not text:
            return None
        print(f"[STT] Transcrito: \"{text}\"")
        return text
    except Exception as e:
        print(f"[STT][ERROR] Falló la transcripción con Groq: {e}")
        return None
