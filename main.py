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

from config import ENABLE_WEB_PANEL, GROQ_API_KEY, PICOVOICE_ACCESS_KEY


BANNER = r"""
    ==============================================
        MIA - Bartender por voz (Raspberry Pi)
    ----------------------------------------------
        Di 'Mia' para activarme.
        Ctrl+C para detener.
    ==============================================
"""


def _check_secrets():
    missing = []
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not PICOVOICE_ACCESS_KEY:
        missing.append("PICOVOICE_ACCESS_KEY")
    if missing:
        print("[ERROR] Faltan variables de entorno: " + ", ".join(missing))
        print("        Copia .env.example a .env y complétalas.")
        return False
    return True


def main():
    print(BANNER)
    if not _check_secrets():
        sys.exit(1)

    if ENABLE_WEB_PANEL:
        # El panel web arranca MIA internamente (server.start_mia_backend).
        print("[MAIN] Panel web ACTIVADO — iniciando servidor Flask-SocketIO.")
        import server
        server.run()
    else:
        from assistant import VoiceAssistant
        mia = VoiceAssistant()
        mia.run_forever()


if __name__ == "__main__":
    main()
