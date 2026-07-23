# ============================================================
# MIA - Cerebro (LLM en la nube con Groq, salida JSON estructurada)
# ============================================================
# Recibe el texto del usuario y devuelve un dict validado:
#   {accion, coctel, mensaje, dato_curioso, emocion}
#
# Decisiones de diseño:
#   - Llamada NO-streaming con response_format={"type":"json_object"}:
#     Groq devuelve el JSON completo de una vez, así que no hay ninguna
#     ventaja en el parsing incremental frágil del assistant.py original.
#   - El LLM identifica el cóctel; los TIEMPOS DE BOMBA los calcula el
#     hardware de forma determinista. El LLM nunca decide cantidades.
#   - Validación en Python (defensa en profundidad): no se confía solo en
#     que el prompt se respete.
# ============================================================
import json
import re
import unicodedata

from groq import Groq

from config import (
    GROQ_API_KEY, GROQ_LLM_MODEL, GROQ_STT_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS,
    MAX_HISTORY_TURNS, MIA_SYSTEM_PROMPT,
    RECETAS_COCTELES, BOMBAS_CONFIG,
    TTS_VOICE, PUMP_PINS, FLOW_RATE_ML_S, MAX_PUMP_SECONDS,
    PIN_MOTOR_IN1, PIN_MOTOR_IN2, PIN_MOTOR_ENA,
)

ACCIONES_VALIDAS = {"preparar", "responder", "no_disponible", "fuera_de_tema"}
EMOCIONES_VALIDAS = {"feliz", "guino", "pensando", "risa", "neutral"}

# --- Frases para entrar/salir del MODO AUDITOR (explica cómo funciona) ---
# Se comprueba SALIR antes que ENTRAR.
FRASES_SALIR_ADMIN = [
    "termina la auditoria", "termino la auditoria", "fin de la auditoria",
    "auditor fuera", "sal del modo auditor", "cierra la auditoria", "modo bar",
]
FRASES_ENTRAR_ADMIN = [
    "soy el auditor", "soy la auditora", "soy auditor", "modo auditor",
]


class Brain:
    """Genera la respuesta estructurada de MIA a partir del texto del usuario."""

    def __init__(self):
        self._client = Groq(api_key=GROQ_API_KEY)
        self._history = []   # [{"role": "user"/"assistant", "content": ...}]
        self._menu_context = self._build_menu_context()
        # Modo auditor: cuando está activo (frase "soy el auditor"), MIA puede
        # explicar su propia arquitectura técnica (fuera de la restricción "solo bar").
        self.admin_mode = False
        print(f"[BRAIN] Groq listo (modelo {GROQ_LLM_MODEL}).")

    # ------------------------------------------------------------------
    # Contexto del menú
    # ------------------------------------------------------------------

    def _build_menu_context(self):
        """Texto con el menú real para inyectar en el system prompt."""
        lines = []
        for name, recipe in RECETAS_COCTELES.items():
            ings = ", ".join(recipe.keys())
            lines.append(f"- {name}: {ings}")
        ingredientes = ", ".join(b["ingrediente"] for b in BOMBAS_CONFIG.values())
        return (
            f"Ingredientes conectados en la barra: {ingredientes}\n"
            f"Cócteles del menú (SOLO estos se pueden preparar):\n"
            + "\n".join(lines)
        )

    # ------------------------------------------------------------------
    # Modo administrador (desarrollador)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text):
        """minúsculas + sin acentos, para comparar frases de activación."""
        text = (text or "").lower().strip()
        text = unicodedata.normalize("NFD", text)
        return "".join(c for c in text if unicodedata.category(c) != "Mn")

    def _detect_admin_toggle(self, user_text):
        """Devuelve 'enter', 'exit' o None según las frases de modo admin."""
        norm = self._normalize(user_text)
        if any(p in norm for p in FRASES_SALIR_ADMIN):
            return "exit"
        if any(p in norm for p in FRASES_ENTRAR_ADMIN):
            return "enter"
        return None

    @staticmethod
    def _strip_admin_trigger(user_text):
        """Quita la muletilla de activación para dejar la pregunta real."""
        cleaned = user_text
        for phrase in ["mia", "soy el auditor", "soy la auditora", "soy auditor",
                       "modo auditor"]:
            cleaned = re.sub(phrase, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" ,.:;-–").strip()

    def _admin_prompt(self):
        """System prompt del modo admin: datos técnicos REALES desde la config."""
        pines_bombas = ", ".join(f"{k}=GPIO{v}" for k, v in PUMP_PINS.items())
        return (
            "Eres MIA atendiendo a un AUDITOR TÉCNICO. En este modo, además "
            "de seguir siendo bartender, PUEDES explicar tu propia arquitectura "
            "técnica con total transparencia y de forma didáctica. Habla en español.\n\n"
            "FORMATO: responde SIEMPRE con un ÚNICO objeto JSON con las claves "
            '"accion", "coctel", "mensaje", "dato_curioso", "emocion". Para '
            'explicaciones técnicas usa accion="responder" y coctel=null; pon la '
            'explicación en "mensaje". Si te piden preparar un cóctel del menú, '
            'sigues usando accion="preparar" con normalidad.\n\n'
            "DATOS TÉCNICOS REALES DE TU SISTEMA (explícalos si te preguntan cómo "
            "funcionas, dónde está tu cerebro, qué servicios usas, cómo te conectas "
            "a la Raspberry Pi o cómo controlas las bombas):\n"
            f"- Corres como UN SOLO proceso en Python sobre una Raspberry Pi 3.\n"
            f"- Palabra de activación ('Mia'): se detecta LOCALMENTE y sin internet "
            f"con Porcupine (Picovoice).\n"
            f"- Tu oído (voz→texto / STT): modelo Whisper '{GROQ_STT_MODEL}' en la "
            f"NUBE de Groq.\n"
            f"- Tu cerebro (razonamiento / LLM): modelo '{GROQ_LLM_MODEL}' (familia "
            f"Llama) en la NUBE de Groq, respondiendo en JSON.\n"
            f"- Tu voz (texto→voz / TTS): edge-tts de Microsoft (voz '{TTS_VOICE}'), "
            f"reproducida localmente con mpg123.\n"
            f"- Control físico: librería gpiozero. Un motor DC con driver L298N "
            f"(pines GPIO IN1={PIN_MOTOR_IN1}, IN2={PIN_MOTOR_IN2}, ENA={PIN_MOTOR_ENA}) "
            f"mueve el vaso entre las bombas.\n"
            f"- 4 bombas por relé (activos en LOW): {pines_bombas}.\n"
            f"- Los tiempos de cada bomba NO los decide el LLM: se calculan de la "
            f"receta (mililitros ÷ caudal de {FLOW_RATE_ML_S} mL/s) con un límite de "
            f"seguridad de {MAX_PUMP_SECONDS} s por bomba.\n"
            "- No guardas memoria a largo plazo: solo un historial corto en RAM.\n\n"
            "Sé claro y concreto. Si no sabes un detalle, dilo; no inventes."
        )

    # ------------------------------------------------------------------
    # Historial corto (en memoria, sin base de datos)
    # ------------------------------------------------------------------

    def _add_history(self, role, content):
        self._history.append({"role": role, "content": content})
        max_msgs = MAX_HISTORY_TURNS * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

    # ------------------------------------------------------------------
    # Generación de respuesta
    # ------------------------------------------------------------------

    def respond(self, user_text):
        """Devuelve un dict validado {accion, coctel, mensaje, dato_curioso, emocion}."""
        # --- Conmutación de MODO ADMIN (antes de llamar al LLM) ---
        toggle = self._detect_admin_toggle(user_text)
        if toggle == "exit":
            self.admin_mode = False
            self._history.clear()
            print("[BRAIN] MODO AUDITOR desactivado.")
            return {
                "accion": "responder", "coctel": None,
                "mensaje": "Auditoría finalizada. Vuelvo a ser tu bartender "
                           "y solo hablo de cócteles. ¿Qué te preparo?",
                "dato_curioso": None, "emocion": "guino",
            }
        if toggle == "enter":
            self.admin_mode = True
            print("[BRAIN] MODO AUDITOR activado.")
            # Quitar la muletilla para dejar la pregunta real (si la hay).
            user_text = self._strip_admin_trigger(user_text)
            if not user_text:
                user_text = ("Saluda al auditor y explícale de forma breve cómo "
                             "funcionas y qué puede preguntarte aquí.")

        # --- Elegir el system prompt según el modo ---
        if self.admin_mode:
            system_content = self._admin_prompt()
        else:
            system_content = f"{MIA_SYSTEM_PROMPT}\n\n=== MENÚ ACTUAL ===\n{self._menu_context}"

        messages = [{"role": "system", "content": system_content}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_text})

        try:
            completion = self._client.chat.completions.create(
                model=GROQ_LLM_MODEL,
                messages=messages,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[BRAIN][ERROR] JSON inválido del LLM: {e}")
            return self._fallback("Perdón, no te entendí bien. ¿Me repites qué cóctel quieres?")
        except Exception as e:
            print(f"[BRAIN][ERROR] Falló la llamada a Groq: {e}")
            return self._fallback("Uy, se me trabó el cerebro un segundo. ¿Lo intentamos de nuevo?")

        result = self._validate(data)

        # Guardar en historial (guardamos el mensaje hablado, no el JSON entero)
        self._add_history("user", user_text)
        self._add_history("assistant", result["mensaje"])

        print(f"[BRAIN] accion={result['accion']} coctel={result['coctel']}")
        return result

    # ------------------------------------------------------------------
    # Validación (defensa en profundidad)
    # ------------------------------------------------------------------

    def _validate(self, data):
        """Normaliza el dict del LLM y aplica reglas de seguridad de dominio."""
        if not isinstance(data, dict):
            return self._fallback("¿Me repites qué te preparo?")

        accion = str(data.get("accion", "")).strip().lower()
        coctel = data.get("coctel")
        mensaje = (data.get("mensaje") or "").strip()
        dato_curioso = data.get("dato_curioso")
        emocion = str(data.get("emocion", "neutral")).strip().lower()

        if accion not in ACCIONES_VALIDAS:
            accion = "responder"
        if emocion not in EMOCIONES_VALIDAS:
            emocion = "neutral"

        if isinstance(coctel, str):
            coctel = coctel.strip() or None
        else:
            coctel = None

        if isinstance(dato_curioso, str):
            dato_curioso = dato_curioso.strip() or None
        else:
            dato_curioso = None

        # Regla clave: si dice "preparar", el cóctel DEBE existir en el menú.
        if accion == "preparar":
            matched = self._match_coctel(coctel)
            if matched:
                coctel = matched   # nombre canónico exacto del menú
            else:
                # El LLM marcó preparar pero el cóctel no está en el menú:
                # degradar a no_disponible y NO dispensar nada.
                accion = "no_disponible"
                coctel = None
                if not mensaje:
                    mensaje = "Ese no lo tengo en la carta, pero puedo ofrecerte otro. ¿Te muestro el menú?"

        # Fuera de tema / no disponible / responder nunca dispensan.
        if accion != "preparar":
            coctel = None
        if accion == "fuera_de_tema":
            dato_curioso = None

        if not mensaje:
            mensaje = "¿Qué cóctel te preparo?"

        return {
            "accion": accion,
            "coctel": coctel,
            "mensaje": mensaje,
            "dato_curioso": dato_curioso,
            "emocion": emocion,
        }

    @staticmethod
    def _match_coctel(coctel):
        """Devuelve el nombre canónico del menú si hay match difuso, o None."""
        if not coctel or not isinstance(coctel, str):
            return None
        target = coctel.lower().strip()
        for name in RECETAS_COCTELES:
            if name.lower() == target or name.lower() in target or target in name.lower():
                return name
        return None

    @staticmethod
    def _fallback(mensaje):
        return {
            "accion": "responder",
            "coctel": None,
            "mensaje": mensaje,
            "dato_curioso": None,
            "emocion": "neutral",
        }
