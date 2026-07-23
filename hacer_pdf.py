# ============================================================
# MIA - Exportar el manual a PDF (para imprimir)
# ============================================================
#   python hacer_pdf.py
#
# Convierte RASPBERRY.md en RASPBERRY.pdf con estilos pensados para papel:
# sin colores de fondo que gasten tinta, comandos en recuadro, tablas con
# líneas finas y cada sección grande empezando en página nueva.
#
# Usa el Chrome/Edge ya instalado en el sistema (modo headless), así que no
# hace falta LaTeX ni pandoc.
# ============================================================
import os
import subprocess
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(AQUI, "RASPBERRY.md")
SALIDA = os.path.join(AQUI, "RASPBERRY.pdf")

NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }

* { box-sizing: border-box; }

body {
    font-family: "Segoe UI", Calibri, Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #16181d;
    margin: 0;
}

/* --- Portada (página completa) --- */
.portada {
    height: 252mm;                 /* alto útil de un A4 con estos márgenes */
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    page-break-after: always;
}

.portada .copa { font-size: 46pt; line-height: 1; margin-bottom: 8mm; }

.portada .filo {
    width: 34mm;
    border-top: 2.5pt solid #16181d;
    margin: 0 0 8mm;
}

.portada h1 {
    font-size: 40pt;
    margin: 0 0 3mm;
    padding: 0;
    border: none;
    letter-spacing: -1pt;
    font-weight: 800;
}

.portada .lema {
    font-size: 13pt;
    color: #4a5058;
    font-style: italic;
    margin-bottom: 14mm;
}

.portada .sub {
    font-size: 15pt;
    font-weight: 600;
    color: #16181d;
    border-top: .8pt solid #c8ccd2;
    border-bottom: .8pt solid #c8ccd2;
    padding: 4mm 10mm;
    margin-bottom: 14mm;
}

.portada .repo {
    font-family: Consolas, "Courier New", monospace;
    font-size: 10.5pt;
    color: #16181d;
    border: 1pt solid #c8ccd2;
    border-radius: 3pt;
    padding: 3mm 7mm;
}

.portada .fecha { margin-top: 8mm; font-size: 9.5pt; color: #6b7280; }

/* --- Índice --- */
.indice { page-break-after: always; }
.indice h2 {
    page-break-before: avoid;
    margin-top: 0;
    font-size: 15pt;
}
.indice ol {
    list-style: none;
    padding: 0;
    margin: 5mm 0 0;
    font-size: 11pt;
}
.indice li {
    padding: 2.2mm 0;
    border-bottom: .5pt dotted #c8ccd2;
}
.indice li span {
    display: inline-block;
    width: 9mm;
    font-weight: 700;
}

h1, h2, h3 { line-height: 1.25; page-break-after: avoid; }

h1 {
    font-size: 17pt;
    margin: 0 0 4mm;
    padding-bottom: 2mm;
    border-bottom: 1.5pt solid #16181d;
}

h2 {
    font-size: 13.5pt;
    margin: 8mm 0 3mm;
    padding-bottom: 1.5mm;
    border-bottom: .8pt solid #b9bec6;
    page-break-before: always;
}
/* La primera sección no fuerza salto (ya viene tras la portada) */
h2:first-of-type { page-break-before: avoid; }

h3 { font-size: 11.5pt; margin: 5mm 0 2mm; color: #2b3038; }

p { margin: 0 0 2.5mm; orphans: 3; widows: 3; }

ul, ol { margin: 0 0 3mm; padding-left: 6mm; }
li { margin-bottom: 1.2mm; }

/* --- Comandos --- */
code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9.5pt;
    background: #f2f3f5;
    border: .5pt solid #d8dbe0;
    border-radius: 2pt;
    padding: .3mm 1.2mm;
}

pre {
    background: #f7f8f9;
    border: .8pt solid #ccd0d6;
    border-left: 2.5pt solid #16181d;
    border-radius: 2pt;
    padding: 3mm 4mm;
    margin: 0 0 3.5mm;
    overflow-wrap: break-word;
    white-space: pre-wrap;
    page-break-inside: avoid;
}
pre code {
    background: none;
    border: none;
    padding: 0;
    font-size: 9.5pt;
    line-height: 1.45;
}

/* --- Tablas --- */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 4mm;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
th {
    background: #eceef1;
    text-align: left;
    font-weight: 700;
    border: .6pt solid #b9bec6;
    padding: 1.8mm 2.5mm;
}
td {
    border: .6pt solid #ccd0d6;
    padding: 1.8mm 2.5mm;
    vertical-align: top;
}

/* --- Avisos --- */
blockquote {
    margin: 0 0 3.5mm;
    padding: 2.5mm 4mm;
    border-left: 2.5pt solid #6b7280;
    background: #f5f6f7;
    color: #2b3038;
    page-break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }

hr { display: none; }

a { color: #16181d; text-decoration: underline; }

strong { font-weight: 700; }
"""

PORTADA = """
<div class="portada">
  <div class="copa">&#127864;</div>
  <div class="filo"></div>
  <h1>MIA</h1>
  <div class="lema">Bartender por voz</div>
  <div class="sub">Manual de instalaci&oacute;n y uso<br>en Raspberry Pi</div>
  <div class="repo">github.com/n3bazort/MiaBartender</div>
  <div class="fecha">{fecha}</div>
</div>
"""


def main():
    import re
    from datetime import date

    import markdown

    if not os.path.exists(ENTRADA):
        print(f"[ERROR] No encuentro {ENTRADA}")
        return 1

    texto = open(ENTRADA, encoding="utf-8").read()

    # El título y el subtítulo van en la portada, no repetidos en el cuerpo.
    texto = re.sub(r"^# .*?\n+(?:Todo lo que necesitas.*?\n)*", "", texto, count=1)

    cuerpo = markdown.markdown(
        texto, extensions=["tables", "fenced_code", "sane_lists"]
    )

    # Índice a partir de los títulos de sección (##) del propio manual, para
    # que no haya que mantenerlo a mano cuando se añadan secciones.
    secciones = re.findall(r"^## +(.+?)\s*$", texto, re.M)
    filas = []
    for s in secciones:
        s = re.sub(r"[*`]", "", s).strip()
        m = re.match(r"^([\w\s]{1,7}?)\.\s+(.*)$", s)
        if m:
            filas.append(f"<li><span>{m.group(1)}.</span>{m.group(2)}</li>")
        else:
            filas.append(f"<li><span></span>{s}</li>")
    indice = ("<div class='indice'><h2>Contenido</h2><ol>"
              + "".join(filas) + "</ol></div>") if filas else ""

    meses = ("enero febrero marzo abril mayo junio julio agosto "
             "septiembre octubre noviembre diciembre").split()
    hoy = date.today()
    fecha = f"{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"

    html = (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<title>MIA - Manual Raspberry Pi</title>"
        f"<style>{CSS}</style></head><body>"
        + PORTADA.format(fecha=fecha)
        + indice
        + cuerpo
        + "</body></html>"
    )

    tmp = os.path.join(tempfile.gettempdir(), "mia_manual.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)

    navegador = next((n for n in NAVEGADORES if os.path.exists(n)), None)
    if not navegador:
        print("[ERROR] No encontré Chrome ni Edge para generar el PDF.")
        print(f"        El HTML quedó en: {tmp}")
        print("        Ábrelo y usa Ctrl+P -> Guardar como PDF.")
        return 1

    print(f"Convirtiendo con {os.path.basename(navegador)}...")
    if os.path.exists(SALIDA):
        os.remove(SALIDA)

    subprocess.run([
        navegador,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={SALIDA}",
        "--virtual-time-budget=10000",
        tmp,
    ], check=False, capture_output=True, timeout=120)

    if os.path.exists(SALIDA):
        kb = os.path.getsize(SALIDA) / 1024
        print(f"\n[OK] PDF generado: {SALIDA}  ({kb:.0f} KB)")
        return 0

    print("[ERROR] El PDF no se generó.")
    print(f"        Abre {tmp} en el navegador y usa Ctrl+P.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
