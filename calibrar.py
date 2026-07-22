#!/usr/bin/env python3
# ============================================================
# MIA - Calibración y diagnóstico de hardware (gpiozero)
# ============================================================
# Herramienta CLI para ajustar y probar el hardware SIN pasar por voz/IA.
# Reemplaza a los antiguos test_motor.py / test_hardware_bebida.py.
#
# Úsala en la Raspberry Pi para medir:
#   - Segundos de recorrido del motor entre posiciones (BOMBAS_CONFIG["seg"]).
#   - Caudal real de las bombas (config.FLOW_RATE_ML_S = mL por segundo).
#
# En una máquina sin GPIO corre en modo simulado (MockFactory) y solo
# imprime la secuencia (útil para validar la lógica).
# ============================================================
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from config import BOMBAS_CONFIG, RECETAS_COCTELES, PUMP_PINS
from hardware import Bartender


def menu():
    print("\n" + "=" * 55)
    print("       MIA - CALIBRACIÓN / DIAGNÓSTICO DE HARDWARE")
    print("=" * 55)
    print("  1. Mover el carro a una posición (segundos)")
    print("  2. Activar una bomba por X mL")
    print("  3. Preparar un cóctel completo del menú")
    print("  4. Purga de limpieza (activar todas las bombas)")
    print("  5. Ver configuración de bombas")
    print("  0. Salir")
    print("=" * 55)


def ver_config():
    print("\n--- Bombas configuradas ---")
    for key, info in BOMBAS_CONFIG.items():
        pin = PUMP_PINS.get(key, "N/A")
        print(f"  {key} (GPIO {pin}) @ {info['seg']:.2f}s : {info['ingrediente']}")
    print("\n--- Cócteles del menú ---")
    for name, recipe in RECETAS_COCTELES.items():
        ings = ", ".join(f"{ing} {ml}mL" for ing, ml in recipe.items())
        print(f"  {name}: {ings}")


def main():
    bar = Bartender()
    try:
        while True:
            menu()
            opc = input("Opción: ").strip()

            if opc == "0":
                break
            elif opc == "1":
                seg = float(input("Posición destino (segundos de recorrido): "))
                bar.move_to(seg)
            elif opc == "2":
                print("Bombas:", ", ".join(PUMP_PINS.keys()))
                pump = input("ID de bomba (ej. pump_1): ").strip()
                ml = float(input("mL a servir: "))
                bar.dispense(pump, ml)
            elif opc == "3":
                print("Cócteles:", ", ".join(RECETAS_COCTELES.keys()))
                coctel = input("Nombre del cóctel: ").strip()
                bar.preparar(coctel)
            elif opc == "4":
                ml = float(input("mL de purga por bomba (ej. 50): ") or "50")
                for pump_key, info in sorted(BOMBAS_CONFIG.items(),
                                             key=lambda kv: kv[1]["seg"]):
                    bar.move_to(info["seg"])
                    bar.dispense(pump_key, ml)
                bar.move_to(0.0)
            elif opc == "5":
                ver_config()
            else:
                print("Opción inválida.")
    except KeyboardInterrupt:
        print("\nCancelado por el usuario.")
    finally:
        bar.cleanup()


if __name__ == "__main__":
    main()
