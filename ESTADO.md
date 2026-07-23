# Estado del proyecto — bitácora de trabajo

Este archivo es el **punto de entrada para quien se incorpore al proyecto**.
Cuenta en qué punto está todo, qué falta, qué está roto y por qué se tomaron
ciertas decisiones. Para instalar desde cero, ve a [RASPBERRY.md](RASPBERRY.md).

**Última actualización:** 23 de julio de 2026

---

## 1. Qué es esto

MIA es una bartender por voz sobre una Raspberry Pi 3. El flujo completo:

```
palabra "Mia"  →  grabar  →  Groq Whisper (voz→texto)  →  Groq Llama (decidir)
               →  edge-tts / ElevenLabs (voz)  →  gpiozero (motor + bombas)
```

Todo corre como **un solo proceso de Python**. La pantalla del avatar es un
panel web opcional servido por Flask-SocketIO en el puerto 5000.

---

## 2. Estado de la Raspberry Pi

| Dato | Valor |
|---|---|
| Usuario | `ia` |
| Host | `IA` |
| Proyecto nuevo | `/home/ia/MiaBartender` |
| Proyecto **viejo** | `/home/ia/mia/mia` (no borrar sin avisar) |
| Sistema | Raspbian 13 (trixie), kernel 6.18, armv7l |
| Python | 3.13.5 |
| Pantalla | **DSI**, 800×480 (no es HDMI) |
| Audio USB | C-Media PCM2902, tarjeta 2 (entrada y salida) |

> La IP **cambia** según la red. Se ha visto en `192.168.25.60` y en
> `10.54.149.60`. Míralas en la propia pantalla de la Pi al arrancar, que las
> imprime en la consola.

### Ya instalado y funcionando

- Entorno virtual `.venv` con todas las librerías (vosk, groq, edge-tts,
  flask, flask-socketio, pyaudio, gpiozero).
- `rpi-lgpio` → el GPIO es **real**, no simulado.
- Modelo de voz Vosk en español descargado y **funcionando** (carga en 3,8 s).
- `.env` con la clave de Groq y la salida de audio `hw:2,0`.
- Acceso por **clave SSH** desde la laptop (sin contraseña).

### Todavía NO hecho

- El servicio `mia` de systemd **no está instalado** (`systemctl is-enabled
  mia` → *not-found*). MIA aún no arranca sola al encender.
- No se ha ejecutado nunca `main.py` de principio a fin en la Pi.
- Sin calibrar las bombas en el hardware actual.
- Modo quiosco de la pantalla sin montar.

---

## 3. Problemas abiertos

### 3.1 El micrófono no capta nada — SIN RESOLVER

Es el bloqueante principal. Sin micrófono no hay comando de voz.

**Síntoma:** la grabación produce una señal totalmente plana (rms ≈ 42,
constante). Ni siquiera golpeando el micrófono con el dedo aparece un pico.

**Ya descartado (todo el software está correcto):**

| Comprobación | Resultado |
|---|---|
| `arecord` genera el archivo | sí |
| Volumen de captura ALSA | 100 %, activado |
| Ganancia automática | activada |
| PipeWire (`wpctl`) | volumen 1.00, sin silenciar |
| El dispositivo declara terminal de micrófono | sí |

**Hipótesis pendientes de comprobar, por orden:**

1. El adaptador USB es un **C-Media con dos jacks de 3.5 mm**. Si el
   micrófono está en el jack de salida (verde) en vez del de entrada (rosa),
   el síntoma es exactamente este.
2. El micrófono tiene un **botón físico de silencio**. Confirmar el estado
   real, no solo pulsarlo.
3. **Bajo voltaje** (ver 3.2): los puertos USB pueden no dar corriente
   suficiente al adaptador.
4. Micrófono o cable defectuoso — probarlo en otra computadora.

### 3.2 Bajo voltaje en la Pi

```
vcgencmd get_throttled  →  0x50000
```

Significa que **hubo bajo voltaje** y **hubo limitación de CPU** desde el
arranque. En pantalla aparece `Undervoltage detected!`.

No está ocurriendo continuamente, pero la fuente va al límite. Con las bombas
y el motor conectados el consumo sube. Conviene una fuente de **5 V 3 A** o
alimentar el audio por un hub USB con corriente propia. Puede además ser la
causa del problema del micrófono.

### 3.3 La interfaz no encaja en 800×480

La pantalla es de 800×480 pero el diseño se hizo para 1280×800. A esa
resolución el diseño colapsa al modo apilado: **el avatar queda en 210×118 px**
y el menú se convierte en una barra horizontal que come altura.

Hay que rehacer los puntos de corte para una pantalla **apaisada y pequeña**:
avatar grande en el centro, menú estrecho, subtítulos compactos.

### 3.4 Varias personas trabajando sobre la misma Pi

Se han visto **6 sesiones SSH a la vez**, y a alguien ejecutando el proyecto
viejo (`sudo python3 bartender_pi.py`) mientras se trabajaba en el nuevo.

Las sesiones SSH no chocan entre sí, pero **el micrófono, los pines GPIO, el
motor y el puerto 5000 son únicos**. Dos procesos a la vez se pelean por ellos.

**Norma:** solo una persona ejecuta MIA a la vez. Antes de lanzar nada:

```bash
who                                        # quién está conectado
ps aux | grep -E "python|main.py" | grep -v grep
systemctl status mia --no-pager            # ¿corre el servicio?
```

Si el servicio está activo, párralo antes de probar a mano:

```bash
sudo systemctl stop mia
```

---

## 4. Decisiones tomadas y por qué

Entender esto evita deshacer trabajo por error.

**Vosk en lugar de Picovoice para la palabra "Mia".** Picovoice exige un
correo de empresa y rechaza Gmail. Vosk es libre, offline y no pide cuenta.

**Reconocimiento libre, no gramática de una palabra.** Con una gramática
restringida a "mia", las palabras "mira" y "milagro" activaban a MIA por
error (comprobado). Con el vocabulario completo, el modelo las distingue.

**Solo se miran los resultados finales de Vosk**, nunca los parciales: los
parciales son especulativos y cambian de opinión a mitad de frase.

**`arreglar_vosk.py` existe por una razón.** La librería nativa de Vosk viene
marcada pidiendo pila ejecutable y los kernels 6.x se niegan a cargarla. El
script limpia ese bit de la cabecera ELF. **Sin él, MIA no arranca en esta
Pi.** El instalador lo ejecuta solo.

**La calibración vive en `calibracion.json`, no en el código.** `config.py` lo
carga al arrancar y pisa los valores de `BOMBAS_CONFIG`. Así el dispensado, el
riel de la pantalla y las recetas leen todos las mismas coordenadas.

**El micrófono abierto exige nombrar a MIA; el botón de pulsar no.** Tocar el
botón ya es intención explícita. En modo abierto, lo que no la nombra se
descarta **sin ninguna reacción en pantalla**: ni estado, ni subtítulo, ni
animación.

**Groq es la única clave imprescindible.** Hablar (edge-tts) y despertar
(Vosk) funcionan sin cuenta. ElevenLabs y Picovoice solo son mejoras
opcionales de algo ya resuelto.

---

## 5. Lo siguiente, por orden

1. **Arreglar el micrófono** (ver 3.1). Bloquea todo lo demás.
2. Conseguir una fuente de alimentación mejor (ver 3.2).
3. Rehacer la interfaz para 800×480 (ver 3.3).
4. Ejecutar `main.py` entero en la Pi y ver el flujo completo.
5. Calibrar las bombas con `calibrar_bombas.py`, con el vaso puesto.
6. Instalar el servicio systemd para que arranque sola.
7. Montar el modo quiosco: Chromium a pantalla completa en la pantalla DSI.
   Ya están `xserver-xorg`, `xinit` y `chromium`; faltan `unclutter` y un
   gestor de ventanas ligero.

> Dato para calibrar: el proyecto **viejo** usaba `pump_3: 1.25` y
> `pump_4: 1.85`, mientras que el nuevo trae `1.40` y `2.30`. Puede que los
> viejos se midieran con el hardware real; sirven como punto de partida.

---

## 6. Cómo ponerse al día

Todo el "por qué" de cada cambio está en el historial de git, con mensajes
largos y explicados:

```bash
git log --format='%h %s%n%b' | less
```

Y el manual de instalación completo, también en PDF para imprimir:

```bash
python hacer_pdf.py      # genera RASPBERRY.pdf
```
