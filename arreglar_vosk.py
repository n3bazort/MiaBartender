# ============================================================
# MIA - Arreglo de libvosk.so en kernels nuevos (Raspberry Pi)
# ============================================================
# La librería nativa de Vosk viene marcada pidiendo "pila ejecutable"
# (PT_GNU_STACK con el bit X). Los kernels de Linux 6.x ya no lo permiten y
# al importar vosk revienta con:
#
#   OSError: cannot load library '.../libvosk.so':
#            cannot enable executable stack as shared object requires
#
# Vosk no necesita esa pila para nada: es un resto del proceso de compilación.
# Aquí se limpia ese bit directamente en la cabecera ELF, que es lo mismo que
# haría `execstack -c`, pero sin instalar nada ni pedir sudo.
#
#   python arreglar_vosk.py
#
# Deja una copia .bak al lado por si acaso. Se puede repetir sin problema.
# ============================================================
import os
import shutil
import struct
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

PT_GNU_STACK = 0x6474E551
PF_X = 0x1


def localizar_libvosk():
    """Ruta de libvosk.so dentro del entorno actual, o None."""
    try:
        import vosk
        ruta = os.path.join(os.path.dirname(vosk.__file__), "libvosk.so")
        return ruta if os.path.exists(ruta) else None
    except ImportError:
        return None
    except Exception:
        # vosk puede fallar al importar justo por este problema: buscamos a mano.
        for base in sys.path:
            ruta = os.path.join(base, "vosk", "libvosk.so")
            if os.path.exists(ruta):
                return ruta
        return None


def limpiar_pila_ejecutable(ruta):
    """Quita el bit ejecutable de PT_GNU_STACK. Devuelve True si tocó algo."""
    datos = bytearray(open(ruta, "rb").read())
    if datos[:4] != b"\x7fELF":
        raise ValueError(f"{ruta} no es un binario ELF")

    es_32 = datos[4] == 1
    endian = "<" if datos[5] == 1 else ">"

    if es_32:
        phoff = struct.unpack_from(endian + "I", datos, 0x1C)[0]
        phentsize = struct.unpack_from(endian + "H", datos, 0x2A)[0]
        phnum = struct.unpack_from(endian + "H", datos, 0x2C)[0]
        desplazamiento_flags = 24
    else:
        phoff = struct.unpack_from(endian + "Q", datos, 0x20)[0]
        phentsize = struct.unpack_from(endian + "H", datos, 0x36)[0]
        phnum = struct.unpack_from(endian + "H", datos, 0x38)[0]
        desplazamiento_flags = 4

    cambiado = False
    for i in range(phnum):
        base = phoff + i * phentsize
        if struct.unpack_from(endian + "I", datos, base)[0] != PT_GNU_STACK:
            continue
        pos = base + desplazamiento_flags
        flags = struct.unpack_from(endian + "I", datos, pos)[0]
        if flags & PF_X:
            struct.pack_into(endian + "I", datos, pos, flags & ~PF_X)
            cambiado = True

    if cambiado:
        shutil.copy2(ruta, ruta + ".bak")
        open(ruta, "wb").write(datos)
    return cambiado


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else localizar_libvosk()

    if not ruta:
        print("[i] No encuentro libvosk.so. ¿Está instalado vosk en este entorno?")
        return 0                      # no es un error: quizá aún no toca

    try:
        if limpiar_pila_ejecutable(ruta):
            print(f"[OK] libvosk.so arreglado (pila no ejecutable).\n     {ruta}")
        else:
            print("[i] libvosk.so ya estaba bien, no hacía falta tocarlo.")
    except Exception as e:
        print(f"[AVISO] No se pudo arreglar libvosk.so: {e}")
        print("        Si al arrancar MIA falla con 'executable stack',")
        print("        prueba:  sudo apt install execstack && "
              "execstack -c <ruta a libvosk.so>")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
