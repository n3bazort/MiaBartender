#!/usr/bin/env bash
# ============================================================
# MIA - Instalador ÚNICO para Raspberry Pi
# ============================================================
# Un solo comando deja la Pi lista y funcionando sola:
#
#   bash instalar.sh
#
# Hace TODO: paquetes del sistema, entorno virtual, librerías de Python,
# modelo de voz offline, archivo .env, detección del audio USB y el
# servicio de arranque automático.
#
# Se puede volver a ejecutar sin miedo: detecta lo que ya está hecho.
# ============================================================
set -e

VERDE='\033[0;32m'; AMAR='\033[1;33m'; ROJO='\033[0;31m'; NC='\033[0m'
paso()  { echo -e "\n${VERDE}==> $1${NC}"; }
aviso() { echo -e "${AMAR}[!] $1${NC}"; }
error() { echo -e "${ROJO}[ERROR] $1${NC}"; }

PROYECTO="$(cd "$(dirname "$0")" && pwd)"
cd "$PROYECTO"

echo "============================================================"
echo "   MIA - Instalación en Raspberry Pi"
echo "   Proyecto: $PROYECTO"
echo "============================================================"

# ------------------------------------------------------------
paso "1/7  Paquetes del sistema"
# ------------------------------------------------------------
sudo apt update
sudo apt install -y \
    python3-venv python3-dev python3-pip \
    portaudio19-dev libportaudio2 \
    mpg123 alsa-utils \
    git curl unzip

# ------------------------------------------------------------
paso "2/7  Entorno virtual de Python"
# ------------------------------------------------------------
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "    Creado .venv"
else
    echo "    .venv ya existía"
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel --quiet

# ------------------------------------------------------------
paso "3/7  Librerías de Python"
# ------------------------------------------------------------
pip install -r requirements.txt

# Backend GPIO real (solo existe en la Pi). Si falla, MIA corre simulada.
if pip install rpi-lgpio 2>/dev/null; then
    echo "    Backend GPIO real instalado (rpi-lgpio)"
else
    aviso "No se pudo instalar rpi-lgpio: MIA funcionará en modo SIMULADO."
    aviso "Normal si no estás en una Raspberry Pi."
fi

# ------------------------------------------------------------
paso "4/7  Modelo de voz offline (palabra 'Mia')"
# ------------------------------------------------------------
python descargar_modelo.py

# ------------------------------------------------------------
paso "5/7  Archivo de claves (.env)"
# ------------------------------------------------------------
if [ ! -f ".env" ]; then
    cp .env.example .env
    aviso "Creado .env — FALTA poner tu GROQ_API_KEY."
    NECESITA_ENV=1
else
    echo "    .env ya existe (no se toca)"
    NECESITA_ENV=0
fi

# ------------------------------------------------------------
paso "6/7  Dispositivos de audio (micro y parlantes USB)"
# ------------------------------------------------------------
python listar_audio.py || aviso "No se pudieron listar los dispositivos."

# ------------------------------------------------------------
paso "7/7  Arranque automático (systemd)"
# ------------------------------------------------------------
USUARIO="$(whoami)"
SERVICIO="/etc/systemd/system/mia.service"

# El .service se genera con las rutas y el usuario REALES de esta Pi,
# así funciona aunque el proyecto no esté en /home/pi/mia.
sudo tee "$SERVICIO" > /dev/null <<EOF
[Unit]
Description=MIA - Bartender por voz
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$PROYECTO
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u "$USUARIO")
ExecStart=$PROYECTO/.venv/bin/python $PROYECTO/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "    Servicio instalado en $SERVICIO"

# ------------------------------------------------------------
echo
echo "============================================================"
echo -e "   ${VERDE}INSTALACIÓN TERMINADA${NC}"
echo "============================================================"

if [ "$NECESITA_ENV" = "1" ]; then
    echo
    aviso "ANTES DE ARRANCAR: pon tu clave de Groq (gratis en console.groq.com)"
    echo "     nano .env        <- rellena GROQ_API_KEY"
fi

cat <<EOF

  PROBAR A MANO (ves los mensajes en pantalla):
     .venv/bin/python main.py

  CALIBRAR LAS BOMBAS (dónde se para el vaso):
     .venv/bin/python calibrar_bombas.py

  DEJARLA AUTÓNOMA (arranca sola al encender la Pi):
     sudo systemctl enable --now mia
     journalctl -u mia -f          # ver qué hace en vivo

  CON PANTALLA DEL AVATAR (para la tablet):
     ENABLE_WEB_PANEL=true .venv/bin/python main.py

EOF
