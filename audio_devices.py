# ============================================================
# MIA - Detección de dispositivos de audio (micro y parlantes USB)
# ============================================================
# En la Raspberry Pi el micrófono USB y los parlantes USB no siempre reciben
# el mismo índice al arrancar (depende del orden de enumeración del kernel).
# Este módulo resuelve el índice correcto en caliente, prefiriendo los
# dispositivos USB, para que MIA funcione sin editar la configuración.
#
# Uso como script:   python listar_audio.py
# ============================================================
import re

# Palabras que suelen aparecer en el nombre de un micro USB.
_USB_HINTS = ("usb", "webcam", "camera", "microphone", "micrófono", "mic")

# Dispositivos "virtuales" de ALSA que aceptan cualquier formato pero suelen
# dar problemas de latencia o de canales; se dejan como última opción.
_LOW_PRIORITY = ("sysdefault", "surround", "spdif", "hdmi", "null", "samplerate",
                 "speexrate", "upmix", "vdownmix", "dmix", "lavrate")


def _score_input(name):
    """Puntúa un dispositivo de entrada: más alto = mejor candidato."""
    low = name.lower()
    score = 0
    if any(h in low for h in _USB_HINTS):
        score += 100
    if low.startswith("default"):
        score += 20
    if any(bad in low for bad in _LOW_PRIORITY):
        score -= 60
    return score


def list_devices(pa=None):
    """Devuelve (entradas, salidas) como listas de dicts {index, name, channels, rate}."""
    import pyaudio

    own = pa is None
    if own:
        pa = pyaudio.PyAudio()
    try:
        entradas, salidas = [], []
        for i in range(pa.get_device_count()):
            try:
                info = pa.get_device_info_by_index(i)
            except Exception:
                continue
            item = {
                "index": i,
                "name": info.get("name", "?"),
                "in": int(info.get("maxInputChannels", 0)),
                "out": int(info.get("maxOutputChannels", 0)),
                "rate": int(info.get("defaultSampleRate", 0)),
            }
            if item["in"] > 0:
                entradas.append(item)
            if item["out"] > 0:
                salidas.append(item)
        return entradas, salidas
    finally:
        if own:
            try:
                pa.terminate()
            except Exception:
                pass


def find_input_device(pa=None):
    """Índice del mejor micrófono disponible, o None para usar el del sistema.

    Prefiere un dispositivo USB; si no hay ninguno, devuelve None y pyaudio
    usará el predeterminado del sistema.
    """
    try:
        entradas, _ = list_devices(pa)
    except Exception as e:
        print(f"[AUDIO][AVISO] No se pudieron listar los dispositivos: {e}")
        return None

    if not entradas:
        print("[AUDIO][AVISO] No se encontró ningún micrófono.")
        return None

    mejor = max(entradas, key=lambda d: _score_input(d["name"]))
    if _score_input(mejor["name"]) <= 0:
        # Ninguno destaca: que decida el sistema.
        return None

    print(f"[AUDIO] Micrófono detectado: [{mejor['index']}] {mejor['name']}")
    return mejor["index"]


def resolve_input_device(configured, pa=None):
    """Traduce el valor de config (int / None / 'auto') a un índice real."""
    if configured == "auto":
        return find_input_device(pa)
    return configured


def alsa_output_hint():
    """Sugerencia de dispositivo ALSA de salida para mpg123 (solo informativo)."""
    try:
        import subprocess
        out = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
        tarjetas = re.findall(r"tarjeta (\d+): (\S+)|card (\d+): (\S+)", out.stdout)
        for t in tarjetas:
            num = t[0] or t[2]
            nombre = t[1] or t[3]
            if "usb" in nombre.lower():
                return f"hw:{num},0"
    except Exception:
        pass
    return ""


def audio_status():
    """Estado del audio para avisar en la pantalla de la Raspberry Pi.

    Devuelve un dict con lo que la pantalla necesita saber:
        {ok, mic, altavoz, mic_nombre, altavoz_nombre, mensaje, detalle}

    'ok' es False si falta el micrófono o los parlantes, que es justo el caso
    en el que MIA parece estar rota sin decir por qué.
    """
    estado = {
        "ok": False, "mic": False, "altavoz": False,
        "mic_nombre": "", "altavoz_nombre": "",
        "mensaje": "", "detalle": "",
    }

    try:
        entradas, salidas = list_devices()
    except Exception as e:
        estado["mensaje"] = "No se puede acceder al audio"
        estado["detalle"] = f"pyaudio no arrancó ({e}). ¿Falta portaudio19-dev?"
        return estado

    if entradas:
        idx = find_input_device()
        elegida = next((d for d in entradas if d["index"] == idx), entradas[0])
        estado["mic"] = True
        estado["mic_nombre"] = elegida["name"]

    if salidas:
        # Preferimos enseñar un USB si lo hay: es lo que el usuario espera ver.
        usb = next((d for d in salidas
                    if any(h in d["name"].lower() for h in _USB_HINTS)), None)
        elegida = usb or salidas[0]
        estado["altavoz"] = True
        estado["altavoz_nombre"] = elegida["name"]

    estado["ok"] = estado["mic"] and estado["altavoz"]

    if not estado["mic"] and not estado["altavoz"]:
        estado["mensaje"] = "No hay micrófono ni parlantes"
        estado["detalle"] = "Conéctalos por USB y reinicia MIA."
    elif not estado["mic"]:
        estado["mensaje"] = "No se detecta el micrófono"
        estado["detalle"] = "Conecta el micrófono USB y reinicia MIA."
    elif not estado["altavoz"]:
        estado["mensaje"] = "No se detectan los parlantes"
        estado["detalle"] = "Conecta los parlantes USB y reinicia MIA."

    return estado


def main():
    """Imprime todos los dispositivos de audio del sistema."""
    print("=" * 62)
    print("DISPOSITIVOS DE AUDIO DETECTADOS")
    print("=" * 62)

    try:
        entradas, salidas = list_devices()
    except Exception as e:
        print(f"[ERROR] No se pudo abrir pyaudio: {e}")
        print("        En la Pi:  sudo apt install portaudio19-dev && pip install pyaudio")
        return

    print("\n--- ENTRADAS (micrófonos) ---")
    if not entradas:
        print("  (ninguna)")
    for d in entradas:
        print(f"  [{d['index']:>2}] {d['name']}  ({d['in']} canales, {d['rate']} Hz)")

    print("\n--- SALIDAS (parlantes) ---")
    if not salidas:
        print("  (ninguna)")
    for d in salidas:
        print(f"  [{d['index']:>2}] {d['name']}  ({d['out']} canales, {d['rate']} Hz)")

    elegido = find_input_device()
    print("\n" + "=" * 62)
    if elegido is None:
        print("MIA usará el micrófono PREDETERMINADO del sistema.")
    else:
        print(f"MIA usará automáticamente el micrófono con índice {elegido}.")
    print("Para fijar otro, pon en tu .env:   MIC_DEVICE_INDEX=<número>")

    hint = alsa_output_hint()
    if hint:
        print(f"\nParlantes USB detectados en ALSA. Si no se escucha, pon en .env:")
        print(f"   AUDIO_OUTPUT_DEVICE={hint}")
    print("=" * 62)


if __name__ == "__main__":
    main()
