#!/usr/bin/env python3
# ============================================================
# MIA - SIMULADOR (sin Raspberry Pi, sin micrófono)
# ============================================================
# Prueba TODO el cerebro y la secuencia de hardware ESCRIBIENDO los comandos
# en vez de hablarlos. Ideal para probar en tu PC o en una plataforma web
# (Replit, Google Colab, etc.) SIN hardware físico.
#
# Qué es real y qué se simula aquí:
#   - REAL : la lógica del LLM (Groq) que decide qué hacer y qué responder.
#   - REAL : el cálculo de tiempos de bomba y el clamp de seguridad.
#   - SIMULADO: el GPIO (motor + bombas) vía MockFactory de gpiozero; se
#     imprime paso a paso lo que HARÍA la máquina física.
#   - OMITIDO: wake word ("Mia") y grabación de voz (aquí se escribe el texto).
#
# Dependencias mínimas (NO requiere pyaudio/porcupine/mpg123):
#   pip install groq gpiozero python-dotenv
#
# Requiere GROQ_API_KEY en .env (o variable de entorno).
# ============================================================
import os
import sys

# Forzar modo simulado de GPIO ANTES de importar config/hardware.
os.environ.setdefault("USE_MOCK_GPIO", "1")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from config import GROQ_API_KEY, RECETAS_COCTELES
from brain import Brain
from hardware import Bartender


BANNER = """
============================================================
        MIA - SIMULADOR DE ESCRITORIO (sin hardware)
------------------------------------------------------------
  Escribe lo que le dirías a MIA y pulsa Enter.
  Ejemplos:
     preparame una paloma
     que cocteles tienes?
     recomiendame algo
     preparame un mojito        (no está en el menú)
     cuanto es 2 + 2?           (fuera de tema: lo rechaza)
     mia modo admin, explicame como funcionas   (modo desarrollador)
     mia admin fuera            (vuelve al modo bar)
  Escribe 'salir' para terminar.
============================================================
"""


def imprimir_decision(result):
    """Muestra de forma legible lo que decidió el cerebro."""
    print("\n  ┌─ MIA decide ──────────────────────────────")
    print(f"  │ acción      : {result['accion']}")
    print(f"  │ cóctel      : {result['coctel']}")
    print(f"  │ emoción     : {result['emocion']}")
    print(f"  │ 💬 mensaje  : {result['mensaje']}")
    if result["dato_curioso"]:
        print(f"  │ ✨ dato     : {result['dato_curioso']}")
    print("  └───────────────────────────────────────────\n")


def main():
    print(BANNER)

    if not GROQ_API_KEY:
        print("[ERROR] Falta GROQ_API_KEY. Copia .env.example a .env y complétala.")
        print("        (Consíguela gratis en https://console.groq.com)")
        sys.exit(1)

    print("Menú cargado:", ", ".join(RECETAS_COCTELES.keys()), "\n")

    brain = Brain()
    bar = Bartender()

    try:
        while True:
            try:
                texto = input("👤 Tú > ").strip()
            except EOFError:
                break

            if not texto:
                continue
            if texto.lower() in ("salir", "exit", "quit"):
                break

            # 1. El cerebro (Groq) decide
            result = brain.respond(texto)
            imprimir_decision(result)

            # 2. Si toca preparar, se ejecuta la secuencia (simulada)
            if result["accion"] == "preparar" and result["coctel"]:
                print("  🍹 [Simulando dispensado físico...]")
                print("  🎵 [Aquí sonaría la música de espera mientras se sirve]")
                bar.preparar(result["coctel"])
                print(f"  ✅ MIA: ¡Tu {result['coctel']} está listo! Disfrútalo.\n")

    except KeyboardInterrupt:
        pass
    finally:
        bar.cleanup()
        print("\n¡Hasta luego! 👋")


if __name__ == "__main__":
    main()
