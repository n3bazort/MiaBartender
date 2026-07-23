# ============================================================
# MIA - Calibrador de posiciones de las bombas
# ============================================================
# Ajusta a mano dónde se detiene el vaso bajo cada bomba y guarda esas
# posiciones en calibracion.json. Todo el resto del sistema (hardware.py,
# el riel del panel web, las recetas) lee de ahí automáticamente.
#
#   python calibrar_bombas.py
#
# Las posiciones se miden en SEGUNDOS de recorrido del motor desde el
# origen (el extremo donde arranca el carro), no en centímetros.
# ============================================================
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from config import BOMBAS_CONFIG, CALIBRACION_PATH, guardar_calibracion

AYUDA = """
------------------------------------------------------------
  COMANDOS
------------------------------------------------------------
  [Enter]      avanzar 0.05 s  (ajuste fino hacia adelante)
  a            atrás 0.05 s
  ++  /  --    avanzar / retroceder 0.20 s (paso grueso)
  f            fino: cambiar el tamaño del paso
  ir X.XX      mover directo al segundo X.XX desde el origen
  ok           guardar esta posición y pasar a la siguiente bomba
  test         activar esta bomba 1 s (comprobar que cae en el vaso)
  home         volver el carro al origen
  saltar       dejar esta bomba como está
  ver          mostrar todas las posiciones actuales
  salir        terminar (pregunta si guardar)
------------------------------------------------------------
"""


def _leer(prompt):
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "salir"


class Calibrador:
    def __init__(self):
        from hardware import Bartender

        self.bar = Bartender()
        self.paso = 0.05
        self.pos = 0.0          # posición actual del carro, en segundos
        # Copia de trabajo: {pump: seg}
        self.posiciones = {k: v["seg"] for k, v in BOMBAS_CONFIG.items()}

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------

    def home(self):
        """Devuelve el carro al origen."""
        print("  -> volviendo al origen...")
        self.bar.move_to(0.0)
        self.pos = 0.0

    def mover_a(self, destino):
        """Mueve el carro hasta 'destino' segundos desde el origen."""
        destino = max(0.0, round(destino, 3))
        if abs(destino - self.pos) < 0.005:
            return
        self.bar.move_to(destino)
        self.pos = destino
        print(f"  posición actual: {self.pos:.2f} s")

    # ------------------------------------------------------------------
    # Bucle por bomba
    # ------------------------------------------------------------------

    def calibrar_bomba(self, pump):
        ingrediente = BOMBAS_CONFIG[pump]["ingrediente"]
        actual = self.posiciones[pump]

        print("\n" + "=" * 60)
        print(f"  {pump.upper()}  —  {ingrediente}")
        print(f"  posición guardada: {actual:.2f} s")
        print("=" * 60)
        print("  Coloca el vaso y usa los comandos para centrarlo bajo la boquilla.")
        print("  Escribe 'ayuda' si no recuerdas los comandos.")

        self.mover_a(actual)

        while True:
            cmd = _leer(f"[{pump} @ {self.pos:.2f}s] > ")

            if cmd == "":
                self.mover_a(self.pos + self.paso)
            elif cmd == "a":
                self.mover_a(self.pos - self.paso)
            elif cmd == "++":
                self.mover_a(self.pos + 0.20)
            elif cmd == "--":
                self.mover_a(self.pos - 0.20)
            elif cmd == "f":
                v = _leer("  nuevo paso en segundos (ej. 0.02): ")
                try:
                    self.paso = max(0.005, float(v))
                    print(f"  paso = {self.paso:.3f} s")
                except ValueError:
                    print("  [!] valor inválido")
            elif cmd.startswith("ir "):
                try:
                    self.mover_a(float(cmd.split(maxsplit=1)[1]))
                except (ValueError, IndexError):
                    print("  [!] usa por ejemplo:  ir 1.40")
            elif cmd == "test":
                self.bar.pulse_pump(pump, 1.0)
            elif cmd == "home":
                self.home()
            elif cmd == "ver":
                self.mostrar()
            elif cmd in ("ayuda", "help", "?"):
                print(AYUDA)
            elif cmd == "ok":
                self.posiciones[pump] = round(self.pos, 3)
                print(f"  [OK] {pump} queda en {self.pos:.2f} s")
                return True
            elif cmd == "saltar":
                print(f"  {pump} se queda en {actual:.2f} s")
                return True
            elif cmd == "salir":
                return False
            else:
                print("  [!] comando desconocido (escribe 'ayuda')")

    def mostrar(self):
        print("\n  --- posiciones actuales ---")
        for p, seg in sorted(self.posiciones.items(), key=lambda kv: kv[1]):
            ing = BOMBAS_CONFIG[p]["ingrediente"]
            print(f"    {p:8} {seg:5.2f} s   {ing}")
        print()

    # ------------------------------------------------------------------
    # Flujo principal
    # ------------------------------------------------------------------

    def run(self):
        print("=" * 60)
        print("  CALIBRACIÓN DE BOMBAS DE MIA")
        print("=" * 60)
        print(AYUDA)
        self.home()

        orden = sorted(BOMBAS_CONFIG, key=lambda p: BOMBAS_CONFIG[p]["seg"])
        completo = True
        for pump in orden:
            if not self.calibrar_bomba(pump):
                completo = False
                break

        self.mostrar()
        self.home()

        if not completo:
            if _leer("¿Guardar los cambios hechos hasta ahora? (s/n): ") != "s":
                print("Nada guardado.")
                return

        guardar_calibracion(self.posiciones)
        print(f"\n[OK] Guardado en {CALIBRACION_PATH}")
        print("     hardware.py y el panel web ya usan estas posiciones.")
        print("     Reinicia MIA para aplicarlas:  sudo systemctl restart mia\n")

    def cleanup(self):
        try:
            self.bar.cleanup()
        except Exception:
            pass


def main():
    cal = Calibrador()
    try:
        cal.run()
    finally:
        cal.cleanup()


if __name__ == "__main__":
    main()
