# MIA — Bartender por voz (Raspberry Pi 3)

Asistente de voz autónomo que escucha por micrófono, entiende lenguaje natural
en la nube y controla físicamente un minibar de 4 bombas dispensadoras. Todo
corre en **un solo proceso en la Raspberry Pi 3**.

## Arquitectura (híbrida Local + Nube)

```
Micrófono → Wake word "Mia" (Porcupine, LOCAL/offline)
          → Grabar comando (pyaudio, LOCAL)
          → Voz a texto (Groq Whisper, NUBE)
          → Lógica + JSON (Groq Llama, NUBE)
          → Texto a voz (edge-tts + mpg123, LOCAL)
          → Bombas + motor (gpiozero, LOCAL GPIO)
```

Flujo de uso: dices **"Mia"**, pides un cóctel del menú, MIA confirma y te
cuenta un dato curioso **mientras dispensa** la bebida.

> **MIA solo habla de cócteles.** Cualquier pregunta ajena a la barra la declina
> con cortesía (validado tanto en el prompt como en código).

## Módulos

| Archivo         | Responsabilidad |
|-----------------|-----------------|
| `main.py`       | Punto de entrada. Verifica secretos y arranca el bucle (o el panel web). |
| `config.py`     | Configuración central: pines, modelos, recetas, prompt, calibración. |
| `wake_word.py`  | Escucha pasiva offline de "Mia" con Porcupine. |
| `recorder.py`   | Graba el comando con detección de silencio (VAD por energía). |
| `stt.py`        | Transcripción con Groq Whisper. |
| `brain.py`      | LLM Groq en modo JSON → `{accion, coctel, mensaje, dato_curioso}`. |
| `voice.py`      | Síntesis edge-tts + reproducción local con mpg123. |
| `hardware.py`   | Motor L298N + 4 bombas por relé con gpiozero (tiempos deterministas). |
| `assistant.py`  | Orquestador del bucle completo. |
| `server.py`     | Panel web opcional con avatar (Flask-SocketIO), apagado por defecto. |
| `calibrar.py`   | CLI de calibración/diagnóstico de hardware. |

## Seguridad de dispensado

El LLM **identifica** el cóctel; **nunca** decide los tiempos de bomba. Python
calcula la activación de cada bomba de forma determinista desde
`RECETAS_COCTELES` (`mL / FLOW_RATE_ML_S`) y aplica un tope de seguridad
`MAX_PUMP_SECONDS`. Una bomba dispensa alcohol: esta separación evita
sobre-servidos por errores del modelo.

## Instalación

### 1. Dependencias del sistema (Raspberry Pi OS)

```bash
sudo apt update && sudo apt install -y mpg123 portaudio19-dev python3-pyaudio libatlas-base-dev
```

### 2. Dependencias de Python

```bash
pip install -r requirements.txt
pip install rpi-lgpio    # backend GPIO en la Pi (Bookworm). NO en Windows.
```

### 3. Secretos

```bash
cp .env.example .env
```

Completa en `.env`:
- `GROQ_API_KEY` — gratis en https://console.groq.com
- `PICOVOICE_ACCESS_KEY` — gratis en https://console.picovoice.ai

### 4. Wake word "Mia" (paso manual único)

"Mia" no es una palabra nativa de Porcupine. En
[Picovoice Console](https://console.picovoice.ai):
1. Crea una palabra clave personalizada: **Mia**.
2. Plataforma: **Raspberry Pi (Cortex-A)** para la Pi (o **Windows** para dev).
3. Descarga el archivo `.ppn` y apunta `PICOVOICE_KEYWORD_PATH` a su ruta.

## Uso

```bash
python main.py
```

Di **"Mia"**, espera el "¿Sí?" y pide tu cóctel (ej. *"prepárame una Paloma"*).

Con panel web (opcional, pesado en la Pi 3):

```bash
ENABLE_WEB_PANEL=true python main.py
```

Luego abre `http://[IP_DE_LA_PI]:5000` en un navegador de la misma red.

## Calibración del hardware

```bash
python calibrar.py
```

Permite mover el carro a una posición, activar una bomba por X mL, preparar un
cóctel o purgar. Con esto se miden y ajustan en `config.py`:
- `BOMBAS_CONFIG[...]["seg"]` — segundos de recorrido del motor a cada bomba.
- `FLOW_RATE_ML_S` — caudal real de las bombas (mL/segundo).

## Desarrollo sin Raspberry Pi

En una PC sin GPIO, `config.py` auto-activa el backend **MockFactory** de
gpiozero: el hardware se simula y se registra por consola. Fuerza el modo con
`USE_MOCK_GPIO=1`. Así puedes probar la lógica de `hardware.py`, `brain.py`
(con tu `GROQ_API_KEY`), `stt.py` y `voice.py` antes de desplegar en la Pi.
