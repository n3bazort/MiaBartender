# ============================================================
# MIA - Lista los micrófonos y parlantes que ve el sistema
# ============================================================
# Ejecuta esto en la Raspberry Pi después de conectar el micro USB y los
# parlantes USB para saber qué índice usar:
#
#   python listar_audio.py
# ============================================================
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from audio_devices import main

if __name__ == "__main__":
    main()
