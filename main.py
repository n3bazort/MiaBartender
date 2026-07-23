# ============================================================
# MIA - Punto de entrada
# ============================================================
# Asistente de voz autónomo para minibar en Raspberry Pi 3.
#   python main.py            -> modo voz local (sin panel web)
#   ENABLE_WEB_PANEL=true ... -> además arranca el panel web (avatar)
# ============================================================
import sys

# Consola UTF-8 en Windows (dev)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

import os

# --web: micrófono del navegador (pruebas desde la laptop, sin micro ni GPIO).
# Se fija ANTES de importar config para que INPUT_MODE lo recoja.
WEB_MIC = "--web" in sys.argv
if WEB_MIC:
    os.environ["MIA_INPUT"] = "web"
    os.environ["ENABLE_WEB_PANEL"] = "true"

from config import (ENABLE_WEB_PANEL, GROQ_API_KEY, WAKE_KEYWORD_DISPLAY,
                    VOSK_MODEL_PATH)


BANNER = """
    ==============================================
        MIA - Bartender por voz (Raspberry Pi)
    ----------------------------------------------
        Di '{wake}' para activarme.
        Ctrl+C para detener.
    ==============================================
"""


def _check_secrets():
    if not GROQ_API_KEY:
        print("[ERROR] Falta GROQ_API_KEY.")
        print("        Copia .env.example a .env y complétala.")
        return False

    # El wake word usa Vosk (libre): lo único que necesita es su modelo.
    if not WEB_MIC and not os.path.isdir(VOSK_MODEL_PATH):
        print("[ERROR] Falta el modelo de voz para la palabra 'Mia'.")
        print("        Descárgalo con:  python descargar_modelo.py")
        return False
    return True


def main():
    print(BANNER.format(wake=WAKE_KEYWORD_DISPLAY))
    if not _check_secrets():
        sys.exit(1)

    if ENABLE_WEB_PANEL:
        # El panel web arranca MIA internamente (server._start_mia_backend).
        print("[MAIN] Panel web ACTIVADO — iniciando servidor Flask-SocketIO.")
        if WEB_MIC:
            print("[MAIN] Entrada de voz: MICRÓFONO DEL NAVEGADOR "
                  "(no se abre el micro local).")
        import server
        server.run()
    else:
        from assistant import VoiceAssistant
        mia = VoiceAssistant()
        mia.run_forever()


if __name__ == "__main__":
    main()
