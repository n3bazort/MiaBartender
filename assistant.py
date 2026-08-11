# ============================================================
# MIA - Orquestador del asistente de voz
# ============================================================
# Bucle principal en un solo proceso:
#   wake word (Porcupine) -> "¿Sí?" -> grabar comando (pyaudio) ->
#   STT (Groq Whisper) -> LLM (Groq JSON) -> hablar (edge-tts) ->
#   si accion=="preparar": dispensar (gpiozero) diciendo un dato curioso
#   MIENTRAS se sirve la bebida.
# ============================================================
import threading
import time
import unicodedata

from config import ENABLE_WEB_PANEL, WAKE_KEYWORD_DISPLAY

# Frases que activan el cambio de proveedor de voz.
FRASES_CAMBIAR_VOZ = [
    "cambia de voz", "cambiar de voz", "cambia la voz", "cambiar la voz",
    "cambia tu voz", "cambiame la voz", "otra voz", "siguiente voz",
    "cambia de proveedor", "cambia el proveedor", "cambiar voz",
]


def _normalizar(text):
    """minúsculas + sin acentos, para comparar comandos de voz."""
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


class VoiceAssistant:
    """Coordina wake word, grabación, STT, cerebro, voz y hardware."""

    def __init__(self, socketio=None):
        print("=" * 50)
        print("Inicializando MIA...")
        print("=" * 50)

        self.socketio = socketio

        # Importaciones perezosas: así el panel web o los tests pueden usar
        # solo lo que necesiten sin exigir todo el stack de audio/hardware.
        from voice import Voice
        from brain import Brain
        from hardware import Bartender
        from music import MusicPlayer

        self.voice = Voice()
        self.brain = Brain()
        self.hardware = Bartender()
        self.music = MusicPlayer()

        # Reenviar el progreso físico del hardware al panel web (riel + llenado).
        if self.socketio:
            self.hardware.on_event = lambda event, data: self.socketio.emit(event, data)

        # El wake word y el grabador solo se crean al arrancar el bucle de voz
        # (start), para que el panel web pueda instanciar MIA sin abrir el micro.
        self.wake = None
        self.recorder = None

        self.is_running = False

        # Estado para la UI web (opcional)
        self.state = "idle"
        self.on_state_change = None

        # Anti-eco: el wake word se silencia mientras MIA habla.
        self._speaking = threading.Event()

        print("=" * 50)
        print("MIA lista.")
        print("=" * 50)

    # ------------------------------------------------------------------
    # Estado (para el panel web y control de música)
    # ------------------------------------------------------------------

    def set_state(self, new_state, data=None):
        self.state = new_state
        self._update_music_for_state(new_state)
        if self.on_state_change:
            self.on_state_change(new_state, data)

    def _update_music_for_state(self, state):
        """Actualiza el modo de música y la atenuación según el estado actual."""
        mode = "idle"
        ducked = False

        if state == "idle":
            mode = "idle"
            ducked = False
        elif state in ("listening", "thinking", "speaking"):
            # Mientras escucha o habla MIA, atenuamos un 30% (-30%) la música
            mode = "prep" if self.state == "preparing_drink" else "idle"
            ducked = True
        elif state == "preparing_drink":
            mode = "prep"
            ducked = False

        # Parlante local (Pi)
        if hasattr(self, "music") and self.voice and getattr(self.voice, "local_playback", True):
            self.music.set_ducked(ducked)
            self.music.play(mode=mode)

        # Panel web (Navegador)
        if self.socketio:
            self.socketio.emit("music_state", {"mode": mode, "ducked": ducked})

    # ------------------------------------------------------------------
    # Procesamiento de un comando (texto -> respuesta -> acción)
    # ------------------------------------------------------------------

    def handle_text(self, user_text):
        """Procesa un comando ya transcrito. Reutilizable desde el panel web."""
        if not user_text:
            return

        # Comando especial: cambiar de proveedor de voz (y salir del modo admin).
        if self._maybe_switch_voice(user_text):
            return

        self.set_state("thinking", data=user_text)
        result = self.brain.respond(user_text)

        accion = result["accion"]
        mensaje = result["mensaje"]
        dato = result["dato_curioso"]
        coctel = result["coctel"]

        if ENABLE_WEB_PANEL:
            self.set_state("emotion", data=result.get("emocion", "neutral"))

        # Hablar el mensaje principal (confirmación / respuesta / rechazo).
        self.set_state("speaking", data=mensaje)
        self._speak_blocking(mensaje)

        # Solo se dispensa cuando la acción es "preparar" y hay cóctel válido.
        if accion == "preparar" and coctel:
            self.set_state("preparing_drink", data=coctel)

            # Dispensar en un hilo aparte.
            dispense_thread = threading.Thread(
                target=self.hardware.preparar, args=(coctel,), daemon=True
            )
            dispense_thread.start()

            # Si hay dato curioso, MIA lo dice (música atenuada mientras habla)
            if dato:
                self.set_state("speaking", data=dato)
                self._speak_blocking(dato)

            # Mientras el motor y las bombas trabajan, suena la música de preparación
            if dispense_thread.is_alive():
                self.set_state("preparing_drink", data=coctel)
                dispense_thread.join()
            else:
                dispense_thread.join()

            cierre = f"¡Tu {coctel} está listo! Disfrútalo."
            self.set_state("speaking", data=cierre)
            self._speak_blocking(cierre)

        self.set_state("idle")

    def _music_start(self, mode="idle"):
        """Arranca la música: parlante local (Pi) y/o navegador (web)."""
        if self.voice.local_playback:
            self.music.play(mode=mode)
        if self.socketio:
            self.socketio.emit("music_state", {"mode": mode, "ducked": False})

    def _music_stop(self):
        self.music.stop()
        if self.socketio:
            self.socketio.emit("music_state", {"stopped": True})

    def _maybe_switch_voice(self, user_text):
        """Si el comando pide cambiar de voz, cicla al siguiente proveedor.

        Anuncia el cambio CON la voz nueva y sale del modo admin. Devuelve True
        si manejó el comando (no debe seguir al cerebro).
        """
        norm = _normalizar(user_text)
        if not any(f in norm for f in FRASES_CAMBIAR_VOZ):
            return False

        from voice import ENGINE_NAMES

        # Salir del modo admin automáticamente.
        if getattr(self.brain, "admin_mode", False):
            self.brain.admin_mode = False

        disponibles = self.voice.available_engines()
        if len(disponibles) <= 1:
            nombre = ENGINE_NAMES.get(self.voice.engine, self.voice.engine)
            msg = (f"Por ahora solo tengo disponible la voz de {nombre}. "
                   f"Para tener otra, configura la clave de ElevenLabs.")
            self.set_state("speaking", data=msg)
            self._speak_blocking(msg)
            self.set_state("idle")
            return True

        # Cambiar al siguiente proveedor y anunciarlo YA con la voz nueva.
        nuevo = self.voice.next_engine()
        self.voice.set_engine(nuevo)
        nombre = ENGINE_NAMES.get(nuevo, nuevo)
        msg = f"Muy bien, desde ahora usaré la voz de {nombre}."
        self.set_state("speaking", data=msg)
        self._speak_blocking(msg)
        self.set_state("idle")
        return True

    def _speak_blocking(self, text):
        """Habla y espera a que termine, manteniendo el anti-eco activo."""
        self._speaking.set()
        try:
            self.voice.speak(text)
            self.voice.wait_until_done()
        finally:
            self._speaking.clear()

    # ------------------------------------------------------------------
    # Bucle de voz (wake word -> comando)
    # ------------------------------------------------------------------

    def _voice_loop(self):
        try:
            from wake_word import WakeWordListener
            from recorder import Recorder

            self.wake = WakeWordListener(mute_check=lambda: self._speaking.is_set()
                                         or self.voice.is_speaking)
            self.recorder = Recorder()
        except (ImportError, ModuleNotFoundError) as e:
            print(f"[ASSISTANT] PyAudio no disponible ({e}). Modo web / navegador activo.")
            return
        except Exception as e:
            print(f"[ASSISTANT][AVISO] No se pudo iniciar la escucha de voz local: {e}")
            return

        print(f"\nMIA activa — di '{WAKE_KEYWORD_DISPLAY}' para hablarme.\n")

        while self.is_running:
            try:
                # 1. Esperar el wake word
                self.set_state("idle")
                if not self.wake.wait_for_wake():
                    break

                # 2. Confirmación auditiva
                self.set_state("listening")
                self._speak_blocking("¿Sí?")

                # 3. Grabar el comando
                wav = self.recorder.record_command()
                if not wav:
                    continue

                # 4. STT en la nube
                from stt import transcribe
                text = transcribe(wav)
                if not text:
                    from config import obtener_frase_no_entendido
                    self._speak_blocking(obtener_frase_no_entendido())
                    continue

                # 5. Cerebro + voz + hardware
                self.handle_text(text)

            except Exception as e:
                print(f"[ASSISTANT][ERROR] {e}")
                time.sleep(1)

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        t = threading.Thread(target=self._voice_loop, daemon=True, name="MIA-Voice")
        t.start()
        self._voice_thread = t

    def run_forever(self):
        """Arranca el bucle de voz y bloquea hasta Ctrl+C."""
        self.start()
        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nInterrupción del usuario.")
        finally:
            self.stop()

    def stop(self):
        print("\nDeteniendo MIA...")
        self.is_running = False
        if self.wake:
            self.wake.stop()
        self.music.stop()
        self.voice.stop()
        if self.wake:
            self.wake.cleanup()
        if self.recorder:
            self.recorder.cleanup()
        self.hardware.cleanup()
        print("MIA desactivada.\n")
