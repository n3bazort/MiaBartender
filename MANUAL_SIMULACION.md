# Manual de simulación e intervención (sin Raspberry Pi)

Este manual es para **ti**. Explica, paso a paso, cómo probar MIA **sin tener la
Raspberry Pi ni el hardware**, usando un simulador. Hay dos formas:

- **A) Simulador de consola** (`simulador.py`): escribes comandos y ves qué
  decide MIA y la secuencia de bombas. Lo más rápido.
- **B) Simulador web con avatar** (`simulador_web.py`): abres una página en el
  navegador, le escribes a MIA, **ves el avatar animado y escuchas su voz**.

En ambos casos **el cerebro es real** (Groq decide de verdad) y **solo el
hardware es simulado** (se imprime lo que harían el motor y las bombas).

---

## PASO 0 — Lo único imprescindible: la API key de Groq (gratis)

1. Entra a **https://console.groq.com** y crea una cuenta (gratis).
2. Ve a **API Keys → Create API Key** y copia la clave.
3. En la carpeta del proyecto, copia el archivo de ejemplo:

   ```bash
   cp .env.example .env
   ```

4. Abre `.env` con un editor y pega tu clave:

   ```
   GROQ_API_KEY=gsk_tu_clave_aqui
   ```

   > Para la **simulación NO necesitas** la clave de Picovoice ni el archivo
   > `.ppn`. Eso solo hace falta para el wake word "Mia" en la Raspberry Pi real.

---

## OPCIÓN A — Simulador de consola (lo más simple)

### En tu PC (Windows)

1. Instala solo lo necesario (no requiere micrófono ni audio):

   ```bash
   pip install groq gpiozero python-dotenv
   ```

2. Ejecuta:

   ```bash
   python simulador.py
   ```

3. Escribe comandos como si le hablaras a MIA. Prueba estos:

   | Escribes | Qué deberías ver |
   |----------|------------------|
   | `preparame una paloma` | MIA confirma + dato curioso + secuencia motor/bombas |
   | `que cocteles tienes?` | MIA lista el menú (no dispensa) |
   | `recomiendame algo` | MIA recomienda del menú |
   | `preparame un mojito` | MIA se disculpa (no está en el menú) y ofrece otro |
   | `cuanto es 2 mas 2?` | MIA lo **rechaza** (fuera de tema) |

4. Escribe `salir` para terminar.

Así compruebas la **lógica completa** y que las restricciones de seguridad y de
dominio funcionan.

---

## OPCIÓN B — Simulador web con avatar (para "verlo")

Con esto ves el avatar de MIA en el navegador, le escribes en un cuadro de texto,
y **la escuchas hablar** (el audio se reproduce en el navegador).

### En tu PC (Windows)

1. Instala las dependencias (incluye las del panel web):

   ```bash
   pip install groq edge-tts gpiozero python-dotenv flask flask-socketio
   ```

2. Ejecuta:

   ```bash
   python simulador_web.py
   ```

3. Abre en tu navegador: **http://localhost:5000**
4. **Toca/haz clic en la pantalla una vez** (desbloquea el audio del navegador).
5. Escribe en el cuadro de abajo, por ejemplo `preparame una paloma`, y pulsa
   **Enviar**. Verás el avatar cambiar de estado (PENSANDO → PREPARANDO) y oirás
   la voz de MIA. La secuencia de bombas se imprime en la consola.

### 🎵 Música de espera y controles de volumen

Cuando MIA prepara un cóctel, **suena música de espera** mientras las bombas
sirven (y se detiene al terminar). En la interfaz web tienes:

- **🔊 Botón de silencio (mute)** de la música.
- **Slider "Música"**: volumen de la música de espera (en vivo).
- **Slider "Voz"**: volumen de la voz de MIA.

Puedes cambiar las pistas poniendo tus propios `.mp3` en la carpeta
`static/music/` (se eligen al azar). Valores por defecto en `.env`
(`MUSIC_VOLUME`, `VOICE_VOLUME`, `MUSIC_ENABLED`).

> En la Raspberry Pi real (modo voz, sin panel), la música suena por el parlante
> con `mpg123`; su volumen inicial se fija con `MUSIC_VOLUME` en `.env`.

---

## OPCIÓN C — Probar en una plataforma web (Replit) sin instalar nada

Si no quieres instalar nada en tu PC, usa **Replit** (gratis):

### Qué archivos subir

Sube **toda la carpeta del proyecto** (o al menos estos archivos y carpetas):

```
config.py   brain.py   hardware.py   voice.py   assistant.py
stt.py      server.py  simulador.py  simulador_web.py
requirements.txt
templates/   (carpeta completa)
static/      (carpeta completa)
```

> No hace falta subir `wake_word.py` ni `recorder.py` para la simulación (son
> del micrófono real), pero no estorban si los subes.

### Pasos en Replit

1. Entra a **https://replit.com**, crea un repl de tipo **Python**.
2. Sube los archivos (arrastrar y soltar, o "Upload folder").
3. En el panel **Secrets** (candado 🔒), añade un secreto:
   - Clave: `GROQ_API_KEY`
   - Valor: tu clave de Groq
4. En la pestaña **Shell**, instala dependencias:

   ```bash
   pip install groq edge-tts gpiozero python-dotenv flask flask-socketio
   ```

5. Ejecuta el que quieras:

   - **Consola**: `python simulador.py`
   - **Web con avatar**: `python simulador_web.py` → Replit abrirá una ventana
     de navegador (Webview) con la página de MIA. Escribe los comandos ahí.

> En una plataforma web no hay parlante del servidor, por eso el modo simulador
> reproduce el audio **en el navegador** (no en la consola).

---

## PASO SIGUIENTE — Cuando ya tengas la Raspberry Pi

La simulación NO toca hardware. Cuando tengas la Pi, tu intervención será:

1. **Wake word "Mia"**: en https://console.picovoice.ai crea la palabra clave
   "Mia" (plataforma *Raspberry Pi*), descarga el `.ppn` y ponlo en `.env`:
   `PICOVOICE_ACCESS_KEY=...` y `PICOVOICE_KEYWORD_PATH=./mia.ppn`.
2. **Dependencias del sistema en la Pi**:
   ```bash
   sudo apt install -y mpg123 portaudio19-dev python3-pyaudio libatlas-base-dev
   pip install -r requirements.txt
   pip install rpi-lgpio
   ```
3. **Conexiones físicas** (numeración BCM, ver `config.py`):
   - Motor L298N: `IN1=GPIO16`, `IN2=GPIO20`, `ENA=GPIO21`.
   - Bombas (relés): `pump_1=GPIO19`, `pump_2=GPIO6`, `pump_3=GPIO13`, `pump_4=GPIO5`.
4. **Calibrar** con `python calibrar.py`:
   - Ajusta en `config.py` los segundos de recorrido del motor a cada bomba
     (`BOMBAS_CONFIG[...]["seg"]`) y el caudal real de las bombas
     (`FLOW_RATE_ML_S`, en mL por segundo).
5. **Ejecutar**: `python main.py` y di **"Mia"**.

---

## Preguntas frecuentes

- **"Falta GROQ_API_KEY"** → no creaste el `.env` o no pegaste la clave (Paso 0).
- **No suena la voz en el navegador** → haz clic una vez en la página para
  desbloquear el audio (los navegadores bloquean el audio automático).
- **¿Gasto dinero?** → Groq y Picovoice tienen capa gratuita suficiente para
  pruebas. edge-tts es gratis.
- **¿Puedo cambiar los cócteles?** → sí, edita `RECETAS_COCTELES` y
  `BOMBAS_CONFIG` en `config.py`.
