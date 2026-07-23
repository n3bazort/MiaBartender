# MIA en la Raspberry Pi — manual de instalación y uso

Todo lo que necesitas para conectarte a la Pi, bajar el código y dejar a MIA
funcionando sola con su micrófono y parlantes USB.

**Resumen de un vistazo:**

```bash
ssh pi@raspberrypi.local                                    # 1. conectarte
git clone https://github.com/n3bazort/MiaBartender.git ~/mia && cd ~/mia # 2. bajar código
bash instalar.sh                                            # 3. instalar TODO
nano .env                                                   # 4. tu clave de Groq
.venv/bin/python calibrar_bombas.py                         # 5. centrar el vaso
sudo systemctl enable --now mia                             # 6. dejarla autónoma
```

---

## 1. Conectarte a la Pi

La Pi no necesita monitor ni teclado: entras por **SSH** desde la laptop.

### 1.1 Que la Pi tenga WiFi

**A) Ya la usaste antes en esta red** — se conecta sola al encenderla. Pasa al 1.2.

**B) Red nueva** — la forma más segura es regrabar la microSD con **Raspberry Pi
Imager**: en el engranaje de ajustes pones el WiFi, el usuario y la contraseña,
y activas SSH **antes** de grabar.

**C) Fuera de casa** — activa el hotspot del celular con el **mismo nombre y
contraseña** del WiFi que la Pi ya conoce. Se conecta sola, sin tocar nada.

### 1.2 Encontrar su IP

```bash
ping raspberrypi.local
```

Si responde, ya puedes usar ese nombre. Si no:

```bash
arp -a
```

Busca una IP tipo `192.168.x.x`. También sirve el panel del router
(`192.168.1.1`) o la app **Fing** desde el celular.

### 1.3 Entrar

```bash
ssh pi@raspberrypi.local
```

O con la IP: `ssh pi@192.168.1.45`. Si tu usuario no es `pi`, cámbialo.

> **Tip:** reserva la IP en el router (DHCP reservation) para que no cambie.

---

## 2. Bajar el código

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/n3bazort/MiaBartender.git ~/mia
cd ~/mia
```

Si ya lo tenías, para actualizar:

```bash
cd ~/mia && git pull
```

> Si `git pull` se queja de cambios locales, guarda lo tuyo con `git stash`.

---

## 3. Instalar — un solo comando

```bash
cd ~/mia
bash instalar.sh
```

Ese script hace **todo** y se puede repetir sin miedo:

| Paso | Qué hace |
|---|---|
| 1 | Paquetes del sistema (portaudio, mpg123, alsa-utils, git) |
| 2 | Crea el entorno virtual `.venv` |
| 3 | Instala las librerías de Python + el backend GPIO real |
| 4 | Descarga el modelo de voz offline (~40 MB, una sola vez) |
| 5 | Crea el `.env` a partir de la plantilla |
| 6 | Te lista los dispositivos de audio detectados |
| 7 | Deja instalado el servicio de arranque automático |

### Lo único que tienes que rellenar

```bash
nano .env
```

Pon tu **`GROQ_API_KEY`** (gratis, sin tarjeta, en https://console.groq.com).
Guarda con `Ctrl+O` y sal con `Ctrl+X`.

> **No necesitas cuenta de Picovoice.** La palabra "Mia" se reconoce con Vosk,
> un motor offline libre que no pide registro ni correo de empresa. El
> instalador ya bajó su modelo.
>
> El `.env` no viaja en el repositorio, así que hay que llenarlo en la Pi.

---

## 4. Micrófono y parlantes USB

Conecta los dos y comprueba que se ven:

```bash
.venv/bin/python listar_audio.py
```

Te dice qué micrófono va a usar MIA. **No hay que configurar nada:** detecta
sola el micro USB. Si eligiera el equivocado, fija el índice en `.env`:

```
MIC_DEVICE_INDEX=1
```

### Si no se oye por los parlantes USB

ALSA suele sacar el sonido por el jack de 3.5 mm. Mira las tarjetas:

```bash
aplay -l
```

Verás algo como `tarjeta 1: Device [USB Audio Device]`. Ese `1` va al `.env`:

```
AUDIO_OUTPUT_DEVICE=hw:1,0
```

Para dejar el USB como salida de todo el sistema, en `/etc/asound.conf`:

```
defaults.pcm.card 1
defaults.ctl.card 1
```

### Comprobar que el micro graba

```bash
arecord -d 5 -f cd prueba.wav   # graba 5 segundos
aplay prueba.wav                # y los reproduce
```

---

## 5. Calibrar las bombas

Esto define **dónde se para el vaso bajo cada bomba**. Hazlo una vez, con el
vaso puesto:

```bash
.venv/bin/python calibrar_bombas.py
```

Te lleva bomba por bomba y mueve el carro con comandos simples:

| Comando | Qué hace |
|---|---|
| `Enter` | avanza un paso fino (0.05 s) |
| `a` | retrocede un paso |
| `++` / `--` | paso grueso (0.20 s) |
| `ir 1.40` | va directo a esa posición |
| `test` | activa la bomba 1 s — para ver si cae dentro del vaso |
| `ok` | guarda esta posición y pasa a la siguiente |
| `f` | cambia el tamaño del paso |
| `home` | vuelve el carro al origen |
| `ver` | muestra todas las posiciones |
| `saltar` | deja esta bomba como estaba |
| `salir` | termina (pregunta si guardar) |

Al terminar guarda **`calibracion.json`**, y a partir de ahí *todo* lo lee de
ahí: el dispensado, el riel del panel web y las recetas. No hay que tocar el
código ni repetir los números en ningún otro sitio.

```bash
sudo systemctl restart mia    # para que MIA tome las posiciones nuevas
```

> Las posiciones se miden en **segundos de recorrido del motor** desde el
> origen, no en centímetros.

---

## 6. Arrancarla

### A mano (ves los mensajes mientras pruebas)

```bash
.venv/bin/python main.py
```

Di **"Mia"**, espera el "¿Sí?" y pídele un trago. `Ctrl+C` para parar.

### Con la pantalla del avatar (para la tablet)

```bash
ENABLE_WEB_PANEL=true .venv/bin/python main.py
```

Te imprime las URLs. Abre en la tablet la que lleva la IP de la Pi
(`http://192.168.1.45:5000`).

### Los dos modos de micrófono

En la pantalla, junto al botón del micrófono, hay un interruptor:

| Modo | Cómo se usa | ¿Hace falta decir "Mia"? |
|---|---|---|
| **Pulsar** | tocas el botón y hablas | **No** — tocar ya es la intención |
| **Abierto** | el micrófono queda escuchando solo | **Sí** — empieza tu frase con "Mia" |

En modo **Abierto**, MIA ignora en silencio todo lo que no la nombre, así que
la charla del bar no la activa. Ejemplo: *"Mia, prepárame una paloma dulce"*.

---

## 7. Que arranque sola al encender

El instalador ya dejó el servicio listo con las rutas de **tu** Pi. Solo
actívalo:

```bash
sudo systemctl enable --now mia
```

Día a día:

```bash
sudo systemctl status mia     # ¿está corriendo?
journalctl -u mia -f          # ver qué dice en vivo
sudo systemctl restart mia    # reiniciar tras cambiar algo
sudo systemctl stop mia       # pararla
sudo systemctl disable mia    # que no arranque sola nunca más
```

Ya puedes desconectar la laptop: la Pi enciende, se conecta al WiFi, levanta
MIA y responde por voz. Si se cae, systemd la revive a los 5 segundos.

### Actualizar el código después

```bash
cd ~/mia && git pull && sudo systemctl restart mia
```

---

## 8. Si algo falla

| Síntoma | Qué mirar |
|---|---|
| No entra por SSH | ¿Pi y laptop en la **misma** red? Prueba con la IP en vez de `raspberrypi.local`. |
| `No module named pyaudio` | `sudo apt install portaudio19-dev && pip install --force-reinstall pyaudio` |
| Falta el modelo de voz | `.venv/bin/python descargar_modelo.py` |
| No detecta el micro | `listar_audio.py`. Si no sale, otro puerto USB o revisa `lsusb`. |
| No se oye nada | `aplay -l` y fija `AUDIO_OUTPUT_DEVICE=hw:X,0` en `.env`. |
| No reacciona a "Mia" | Habla más cerca y claro. Añade variantes en `.env`: `VOSK_WAKE_VARIANTS=mia,mía,mía mía` |
| Se activa sola | Quita variantes: `VOSK_WAKE_VARIANTS=mia` |
| Va lenta al escuchar | La Pi 3 va justa. Usa el modo **Pulsar** en la tablet, que no necesita wake word. |
| Oye pero no responde | Sin internet: STT y LLM son en la nube. `ping google.com` |
| Corta la frase muy pronto | Sube `SILENCE_PAUSE_SECONDS` en `config.py`. |
| No oye si hablas bajo | Baja `MIN_ENERGY_THRESHOLD` en `config.py` (por defecto 3500). |
| El vaso no queda centrado | `.venv/bin/python calibrar_bombas.py` |
| Las bombas no giran | ¿Se instaló `rpi-lgpio`? Sin él MIA corre en modo simulado. |

---

## 9. Dónde se cambia cada cosa

| Qué quieres cambiar | Dónde |
|---|---|
| Personalidad de MIA, marcas de las botellas | `MIA_SYSTEM_PROMPT` en `config.py` |
| Recetas de los cócteles | `RECETAS_COCTELES` en `config.py` |
| Qué ingrediente hay en cada bomba | `BOMBAS_CONFIG` en `config.py` |
| Posición física de cada bomba | `calibrar_bombas.py` (guarda en `calibracion.json`) |
| Claves y dispositivos de audio | `.env` |
| Palabra de activación | `WAKE_KEYWORD` en `.env` |
