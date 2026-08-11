# ============================================================
# MIA - Compresor de imágenes para el avatar
# ============================================================
# Reduce la resolución excesiva (de 2752px a max 1280px) y optimiza
# las imágenes en PNG, JPEG y WebP para acelerar la carga en la Pi 3.
# ============================================================
import glob
import os
from PIL import Image

AVATARS_DIR = os.path.join(os.path.dirname(__file__), "static", "avatars")
MAX_WIDTH = 1280  # Ancho máximo ideal para 800x480 y 1280x800
QUALITY = 82      # Calidad de compresión visualmente idéntica


def comprimir():
    files = glob.glob(os.path.join(AVATARS_DIR, "*.*"))
    if not files:
        print("No se encontraron imágenes en static/avatars")
        return

    print("=" * 60)
    print("Iniciando compresión de imágenes de avatar...")
    print("=" * 60)

    total_antes = 0
    total_despues = 0

    for filepath in sorted(files):
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in (".png", ".jpeg", ".jpg", ".webp"):
            continue

        size_antes = os.path.getsize(filepath)
        total_antes += size_antes

        with Image.open(filepath) as img:
            w, h = img.size
            # Redimensionar si supera el ancho máximo
            if w > MAX_WIDTH:
                new_h = int(h * (MAX_WIDTH / w))
                img = img.resize((MAX_WIDTH, new_h), Image.Resampling.LANCZOS)

            # Re-guardar optimizando la imagen original
            if ext in (".jpg", ".jpeg"):
                img.convert("RGB").save(filepath, "JPEG", optimize=True, quality=QUALITY)
            elif ext == ".png":
                # Convertir a RGBA si tiene transparencia, sino RGB
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img.save(filepath, "PNG", optimize=True)
                else:
                    img.convert("RGB").save(filepath, "PNG", optimize=True)

            # Generar también versión .webp para máximo rendimiento
            webp_path = os.path.splitext(filepath)[0] + ".webp"
            img.save(webp_path, "WEBP", quality=QUALITY, optimize=True)

        size_despues = os.path.getsize(filepath)
        total_despues += size_despues
        size_webp = os.path.getsize(webp_path)

        ahorro_pct = (1 - (size_despues / size_antes)) * 100
        print(f"OK {os.path.basename(filepath)}: {size_antes/1024:.0f} KB -> {size_despues/1024:.0f} KB ({ahorro_pct:.1f}% menor) | WebP: {size_webp/1024:.0f} KB")

    total_ahorro = (1 - (total_despues / total_antes)) * 100
    print("=" * 60)
    print(f"RESULTADO TOTAL:")
    print(f"Antes:   {total_antes / (1024*1024):.2f} MB")
    print(f"Después: {total_despues / (1024*1024):.2f} MB")
    print(f"Ahorro de espacio: {total_ahorro:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    comprimir()
