# ============================================================
# MIA - Descarga del modelo de voz offline (Vosk)
# ============================================================
# Baja una sola vez el modelo pequeño de español que usa la palabra de
# activación "Mia". Son unos 40 MB comprimidos (~58 MB descomprimidos).
#
#   python descargar_modelo.py
#
# No hace falta cuenta, clave ni registro en ningún sitio.
# ============================================================
import os
import shutil
import sys
import urllib.request
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from config import VOSK_MODEL_PATH, VOSK_MODEL_URL


def _barra(bloques, tam_bloque, total):
    if total <= 0:
        return
    pct = min(100, bloques * tam_bloque * 100 // total)
    hechos = pct // 2
    sys.stdout.write(f"\r  [{'#' * hechos}{'.' * (50 - hechos)}] {pct}%")
    sys.stdout.flush()


def main():
    if os.path.isdir(VOSK_MODEL_PATH):
        print(f"[OK] El modelo ya está en:\n     {VOSK_MODEL_PATH}")
        print("     Borra esa carpeta si quieres volver a bajarlo.")
        return 0

    destino_dir = os.path.dirname(VOSK_MODEL_PATH)
    os.makedirs(destino_dir, exist_ok=True)
    zip_path = os.path.join(destino_dir, "_modelo_tmp.zip")

    print("=" * 60)
    print("  Descargando el modelo de voz en español (una sola vez)")
    print("=" * 60)
    print(f"  Origen : {VOSK_MODEL_URL}")
    print(f"  Destino: {VOSK_MODEL_PATH}\n")

    try:
        urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path, _barra)
        print("\n  Descomprimiendo...")
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(destino_dir)
    except Exception as e:
        print(f"\n[ERROR] No se pudo descargar el modelo: {e}")
        print("        Revisa la conexión a internet y vuelve a intentarlo.")
        return 1
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    if not os.path.isdir(VOSK_MODEL_PATH):
        # El zip trae la carpeta con su nombre de versión; si no coincide con
        # lo esperado, renombramos la única carpeta de modelo que haya salido.
        candidatos = [
            d for d in os.listdir(destino_dir)
            if d.startswith("vosk-model") and os.path.isdir(os.path.join(destino_dir, d))
        ]
        if len(candidatos) == 1:
            shutil.move(os.path.join(destino_dir, candidatos[0]), VOSK_MODEL_PATH)

    if os.path.isdir(VOSK_MODEL_PATH):
        print(f"\n[OK] Modelo listo en:\n     {VOSK_MODEL_PATH}")
        print("\n     Ya puedes usar la palabra de activación 'Mia'.")
        return 0

    print("\n[ERROR] El modelo no quedó en la ruta esperada.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
