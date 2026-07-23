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

La Pi no necesita monitor ni teclado: entras por **SSH** desde la laptop, por
la red WiFi.

> **Red configurada:** la Pi tiene guardadas las credenciales del WiFi del
> **período académico 2026-1**. En esa red arranca y se conecta sola. Para
> usarla en otra red hay que **sacar la microSD** y configurarla desde otra
> computadora (ver **1.1 C**), porque sin pantalla ni teclado no se puede
> cambiar el WiFi desde la propia Pi.

### 1.1 Que la Pi tenga WiFi

**A) Estás en la red del período 2026-1** — se conecta sola al encenderla.
Pasa al 1.2.

**B) Fuera de esa red, sobre la marcha** — activa el hotspot del celular
poniéndole **el mismo nombre y la misma contraseña** que el WiFi del período
2026-1. La Pi cree que es la red de siempre y se conecta sin tocar nada. Es la
salida más rápida para una demostración fuera del aula.

**C) Cambiar la red de forma permanente** — hay que **sacar la microSD** y
configurarla desde otra computadora. La Pi no tiene pantalla ni teclado, así
que no se puede cambiar el WiFi estando ella sola.

Apaga primero con `sudo poweroff` y espera a que se apaguen los LED antes de
sacar la tarjeta. Luego métela en una computadora con lector y elige una de
las dos vías:

**C.1 — Añadir la red nueva (NO borra nada). Prueba esta primero.**

Al meter la SD, Windows te muestra una partición llamada `bootfs`. Crea ahí un
archivo de texto llamado **`wpa_supplicant.conf`** con esto dentro:

```
country=EC
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="NOMBRE_DEL_WIFI_NUEVO"
    psk="CONTRASEÑA_DEL_WIFI_NUEVO"
}
```

Crea también un archivo **vacío** llamado `ssh`, sin extensión, en esa misma
partición. Devuelve la SD a la Pi y enciéndela: conserva MIA, la calibración
y las claves intactas.

**C.2 — Regrabar la tarjeta (sí borra todo). Solo si C.1 falla.**

Graba de nuevo con **Raspberry Pi Imager**. En el **engranaje de ajustes**,
*antes* de grabar, pon el WiFi nuevo, el usuario y la contraseña de la Pi, y
**activa SSH**.

> Regrabar **borra la tarjeta entera**: habrá que repetir el `git clone`, el
> `bash instalar.sh`, el `.env` y **toda la calibración de las bombas**.
>
> Por eso, **antes de sacar la SD**, guarda una copia de los dos archivos que
> no se pueden recuperar solos (desde la laptop, con la Pi encendida):
>
> ```bash
> scp pi@raspberrypi.local:~/mia/calibracion.json .
> scp pi@raspberrypi.local:~/mia/.env .
> ```
>
> Después de reinstalar, los devuelves con `scp` al revés y te ahorras volver
> a calibrar bomba por bomba.

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

**Esa es la única clave que MIA necesita para funcionar entera.** El resto
(hablar y despertar con "Mia") ya está resuelto con servicios libres que no
piden cuenta. Los detalles están en la sección 4.

> El `.env` no viaja en el repositorio, así que hay que llenarlo en la Pi.

---

## 4. Las claves de API: cuáles usa MIA y dónde sacarlas

MIA es un sistema **por voz**, así que las cuatro funciones de abajo son
todas imprescindibles: si falta una, MIA no sirve. Lo que cambia es que
**solo una de ellas necesita que tú saques una clave**; las demás ya vienen
resueltas con servicios gratuitos que no piden cuenta.

| Función | ¿Se puede quitar? | Quién la hace | ¿Necesita clave tuya? |
|---|---|---|---|
| **Oír** (voz → texto) | No | Groq (Whisper) | **Sí — `GROQ_API_KEY`** |
| **Pensar** (qué responder) | No | Groq (Llama) | Sí — la **misma** clave |
| **Hablar** (texto → voz) | No | edge-tts (Microsoft) | No, es libre |
| **Despertar** ("Mia") | No en la Pi | Vosk (offline) | No, es libre |

Es decir: **con una sola clave, la de Groq, MIA funciona entera.**

Además hay dos **mejoras opcionales**. Estas sí se pueden quitar sin que nada
deje de funcionar, porque solo sustituyen a algo que ya está resuelto:

| Mejora opcional | Sustituye a | Qué aporta | Coste |
|---|---|---|---|
| **ElevenLabs** | edge-tts | Voz más natural y con emoción | Gratis ~10 min/mes |
| **Picovoice** | Vosk | Gasta menos CPU en la Pi | Exige correo de empresa |

> **En resumen:** solo necesitas registrarte en **Groq**. Si además quieres la
> voz bonita, registrarte también en ElevenLabs. Nada más.

### GROQ_API_KEY — la única clave que tienes que sacar

Hace dos de las cuatro funciones: convierte tu voz en texto (Whisper) y decide
qué responder (Llama). **Sin esta clave MIA no arranca**, y te lo dice al
intentarlo.

- **Sácala en:** https://console.groq.com
- Crea cuenta con Gmail (acepta correo personal, **no** pide tarjeta).
- Entra en **API Keys → Create API Key** y cópiala.
- Empieza por `gsk_...`

```
GROQ_API_KEY=gsk_tu_clave_aqui
```

> Ojo: la clave solo se muestra **una vez** al crearla. Si la pierdes, borra
> esa y crea otra.

### Hablar — siempre funciona, con o sin clave

**Hablar no es opcional**: es un bartender por voz. Lo que sí es opcional es
*con qué voz* habla.

Por defecto usa **edge-tts** de Microsoft: gratis, ilimitado y **sin cuenta ni
clave**. Ya viene instalado y funciona solo. Con eso MIA habla perfectamente,
solo que con una entonación algo más plana.

**ELEVENLABS_API_KEY** solo mejora esa voz: la hace más natural y con emoción.

Si pones `TTS_ENGINE=elevenlabs` pero te falta la clave, MIA **no se rompe**:
avisa por consola y sigue con edge-tts. Lo mismo si se te agotan los minutos.

- **Sácala en:** https://elevenlabs.io
- Cuenta gratis con Gmail, sin tarjeta.
- **Perfil (arriba a la derecha) → API Keys**
- La capa gratis da unos **10 minutos de audio al mes**. Cuando se agota, MIA
  deja de hablar con esa voz: cambia `TTS_ENGINE=edge` y sigue funcionando.

```
TTS_ENGINE=elevenlabs
ELEVENLABS_API_KEY=tu_clave_aqui
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

Para usar solo la voz gratis, sin cuenta de ElevenLabs:

```
TTS_ENGINE=edge
```

### La palabra "Mia" — obligatoria en la Pi, pero sin clave

En la Pi **hace falta sí o sí**: es la única forma de activarla, porque no hay
botón que pulsar. (En la tablet, con el modo *Pulsar*, no se necesita.)

La buena noticia es que **no requiere ninguna clave**. La reconoce **Vosk**, un
motor offline libre: el instalador baja su modelo (~40 MB) una vez y funciona
sin internet y sin registrarse en ningún sitio.

Existe una alternativa (**Picovoice**) que gasta menos CPU, pero su registro
**exige un correo de empresa** y rechaza Gmail. No hace falta para nada; solo
si algún día quieres probarla:

- https://console.picovoice.ai → `PICOVOICE_ACCESS_KEY=...` en el `.env`

### Cómo llevar tus claves a la Pi

Lo más rápido es copiar el `.env` desde la laptop (un solo comando, desde la
laptop, **no** desde la Pi):

```bash
scp .env pi@raspberrypi.local:~/mia/.env
```

O escribirlas a mano en la Pi:

```bash
nano .env
```

> **Nunca subas el `.env` a GitHub.** Ya está en `.gitignore` para que no pase
> por accidente. Si alguna vez se te escapa una clave, bórrala en la web del
> servicio y crea una nueva.

---

## 5. Micrófono y parlantes USB

Conecta los dos y comprueba que se ven:

```bash
.venv/bin/python listar_audio.py
```

Te dice qué micrófono va a usar MIA. **No hay que configurar nada:** detecta
sola el micro USB.

> La pantalla de la Pi **avisa sola** si falta el micrófono o los parlantes:
> sale un aviso rojo arriba. Comprueba cada 15 segundos, así que al
> enchufar el USB desaparece solo, sin recargar la tablet.

Si eligiera el micrófono equivocado, fija el índice en `.env`:

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

## 6. Calibrar las bombas

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

## 7. Arrancarla

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

## 8. Que arranque sola al encender

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

## 9. Si algo falla

| Síntoma | Qué mirar |
|---|---|
| No entra por SSH | ¿Pi y laptop en la **misma** red? Prueba con la IP en vez de `raspberrypi.local`. |
| La Pi no se conecta al WiFi | Solo conoce la red del período **2026-1**. Usa el hotspot con ese mismo nombre y contraseña, o cambia la red sacando la SD (**1.1 C**). |
| `No module named pyaudio` | `sudo apt install portaudio19-dev && pip install --force-reinstall pyaudio` |
| Falta el modelo de voz | `.venv/bin/python descargar_modelo.py` |
| Sale un aviso rojo arriba en la pantalla | Falta el micro o los parlantes. Enchúfalos por USB: el aviso se va solo en unos segundos. |
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

## 10. Dónde se cambia cada cosa

| Qué quieres cambiar | Dónde |
|---|---|
| Personalidad de MIA, marcas de las botellas | `MIA_SYSTEM_PROMPT` en `config.py` |
| Recetas de los cócteles | `RECETAS_COCTELES` en `config.py` |
| Qué ingrediente hay en cada bomba | `BOMBAS_CONFIG` en `config.py` |
| Posición física de cada bomba | `calibrar_bombas.py` (guarda en `calibracion.json`) |
| Claves y dispositivos de audio | `.env` |
| Palabra de activación | `WAKE_KEYWORD` en `.env` |
