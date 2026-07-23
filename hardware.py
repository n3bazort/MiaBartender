# ============================================================
# MIA - Control de Hardware (gpiozero)
# ============================================================
# Fusiona el antiguo robot_control.py (cliente HTTP) + bartender_pi.py
# (servidor Flask con RPi.GPIO) en un ÚNICO módulo en proceso, ya que ahora
# todo corre en la misma Raspberry Pi.
#
# Mecanismo físico (heredado, se conserva):
#   - Un motor DC (driver L298N) desplaza el carro/vaso a lo largo de un riel.
#   - Las posiciones de las 4 bombas están calibradas en SEGUNDOS de recorrido
#     del motor desde el origen (no en cm físicos).
#   - En cada posición se activa el relé de la bomba correspondiente el tiempo
#     necesario para servir los mL de la receta (tiempo = mL / FLOW_RATE_ML_S),
#     con un clamp de seguridad MAX_PUMP_SECONDS.
#
# Los tiempos de bomba se calculan de forma DETERMINISTA desde RECETAS_COCTELES.
# El LLM nunca decide tiempos ni cantidades.
# ============================================================
import time
import threading

from config import (
    USE_MOCK_GPIO,
    PIN_MOTOR_IN1, PIN_MOTOR_IN2, PIN_MOTOR_ENA,
    PWM_FREQ, VELOCIDAD, FACTOR_CALIBRACION,
    PUMP_PINS, FLOW_RATE_ML_S, MAX_PUMP_SECONDS,
    BOMBAS_CONFIG, RECETAS_COCTELES,
)

# --- Backend de gpiozero: real o simulado (MockFactory) ---
# MockFactory permite ejercitar toda la lógica en una máquina sin GPIO.
if USE_MOCK_GPIO:
    from gpiozero import Device, OutputDevice, PWMOutputDevice
    from gpiozero.pins.mock import MockFactory, MockPWMPin
    # MockPWMPin soporta PWM (el MockPin por defecto no), necesario para el ENA del motor.
    Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    print("[HARDWARE] Modo SIMULADO (MockFactory) — sin GPIO físico.")
else:
    from gpiozero import OutputDevice, PWMOutputDevice
    print("[HARDWARE] Modo REAL — controlando GPIO físico.")


class Bartender:
    """Controla el motor del carro y las 4 bombas por relé con gpiozero.

    Uso:
        bar = Bartender()
        bar.preparar("Paloma")   # bloqueante; mueve, sirve y regresa al origen
        bar.cleanup()
    """

    def __init__(self):
        # Motor DC (L298N): dos pines de dirección + un pin de habilitación con PWM.
        # Se modela con primitivas (no gpiozero.Motor) porque el L298N usa IN1/IN2
        # para dirección y ENA separado para velocidad, un mapeo más claro así.
        self._dir1 = OutputDevice(PIN_MOTOR_IN1)
        self._dir2 = OutputDevice(PIN_MOTOR_IN2)
        self._ena = PWMOutputDevice(PIN_MOTOR_ENA, frequency=PWM_FREQ, initial_value=0)

        # Bombas: relés activos en LOW.
        #   active_high=False -> .on() pone el pin en LOW (relé/bomba ON)
        #                        .off() pone el pin en HIGH (relé/bomba OFF)
        #   initial_value=False -> arranca apagada.
        self._pumps = {
            key: OutputDevice(pin, active_high=False, initial_value=False)
            for key, pin in PUMP_PINS.items()
        }

        # Posición actual del carro, en SEGUNDOS de recorrido desde el origen.
        self._position_seg = 0.0
        self.busy = False
        self._lock = threading.Lock()

        # Callback opcional para reportar el progreso físico en tiempo real
        # (lo usa el panel web para dibujar el recorrido y el llenado del vaso).
        # Firma: on_event(nombre_evento: str, datos: dict).
        self.on_event = None

        print("[HARDWARE] Bartender inicializado. Bombas apagadas, carro en origen.")

    def _emit(self, event, data):
        if self.on_event:
            try:
                self.on_event(event, data)
            except Exception as e:
                print(f"[HARDWARE][AVISO] Falló on_event: {e}")

    # ------------------------------------------------------------------
    # Motor
    # ------------------------------------------------------------------

    def _stop_motor(self):
        self._ena.value = 0
        self._dir1.off()
        self._dir2.off()

    def _move_to(self, target_seg):
        """Mueve el carro a `target_seg` (segundos de recorrido desde el origen)."""
        if abs(target_seg - self._position_seg) < 1e-6:
            return

        distance = target_seg - self._position_seg
        travel_time = abs(distance) * FACTOR_CALIBRACION

        direction = "adelante" if distance > 0 else "atrás"
        print(f"[MOTOR] Moviendo {direction} a {target_seg:.2f}s "
              f"(tiempo estimado {travel_time:.2f}s)...")

        if distance > 0:
            # Adelante (invertido físicamente respecto al driver, como en el original)
            self._dir1.off()
            self._dir2.on()
        else:
            # Atrás
            self._dir1.on()
            self._dir2.off()

        self._ena.value = VELOCIDAD / 100.0
        time.sleep(travel_time)
        self._stop_motor()

        self._position_seg = target_seg
        print(f"[MOTOR] En posición {target_seg:.2f}s.")

    # ------------------------------------------------------------------
    # Bombas
    # ------------------------------------------------------------------

    def _dispense(self, pump_key, amount_ml):
        """Activa una bomba el tiempo necesario para servir `amount_ml`.

        El tiempo se calcula de forma determinista y se limita por seguridad.
        """
        pump = self._pumps.get(pump_key)
        if pump is None:
            print(f"[BOMBA] '{pump_key}' no existe — omitida.")
            return
        if amount_ml <= 0:
            return

        raw_time = amount_ml / FLOW_RATE_ML_S
        pour_time = min(raw_time, MAX_PUMP_SECONDS)
        if pour_time < raw_time:
            print(f"[BOMBA][SEGURIDAD] Tiempo recortado de {raw_time:.2f}s "
                  f"a {pour_time:.2f}s (MAX_PUMP_SECONDS).")

        print(f"[BOMBA] {pump_key} ON — sirviendo {amount_ml}mL ({pour_time:.2f}s)...")
        pump.on()
        try:
            time.sleep(pour_time)
        finally:
            pump.off()
        print(f"[BOMBA] {pump_key} OFF.")

    # ------------------------------------------------------------------
    # Preparación de cócteles
    # ------------------------------------------------------------------

    def _build_steps(self, recipe):
        """Convierte una receta {ingrediente: ml} en pasos ordenados por posición.

        Cada paso: {pump, ingrediente, amount_ml, seg}. Ordenados por 'seg'
        (de izquierda a derecha) para minimizar el recorrido del motor.
        """
        steps = []
        for ingrediente, amount_ml in recipe.items():
            pump_key = None
            target_seg = None
            for pk, info in BOMBAS_CONFIG.items():
                if info["ingrediente"].lower() == ingrediente.lower():
                    pump_key = pk
                    target_seg = info["seg"]
                    break
            if pump_key is None:
                print(f"[HARDWARE][AVISO] '{ingrediente}' no está asignado a ninguna bomba.")
                continue
            steps.append({
                "pump": pump_key,
                "ingrediente": ingrediente,
                "amount_ml": amount_ml,
                "seg": target_seg,
            })
        steps.sort(key=lambda s: s["seg"])
        return steps

    def resolve_recipe(self, coctel):
        """Busca la receta por nombre (match difuso). Devuelve (nombre, receta) o (None, None).

        Exacta primero y luego difusa con los nombres MÁS LARGOS primero, para
        que "Paloma Dulce" no caiga en su prefijo "Paloma".
        """
        if not coctel:
            return None, None
        target = coctel.lower().strip()

        for name, recipe in RECETAS_COCTELES.items():
            if name.lower() == target:
                return name, recipe

        for name in sorted(RECETAS_COCTELES, key=len, reverse=True):
            low = name.lower()
            if low in target or target in low:
                return name, RECETAS_COCTELES[name]
        return None, None

    def preparar(self, coctel):
        """Prepara un cóctel del menú (bloqueante). Devuelve True si se sirvió.

        Mueve el carro a cada bomba, sirve el volumen de la receta y al final
        regresa al origen. Seguro ante llamadas concurrentes (busy flag).
        """
        name, recipe = self.resolve_recipe(coctel)
        if not recipe:
            print(f"[HARDWARE][ERROR] '{coctel}' no está en el recetario.")
            return False

        with self._lock:
            if self.busy:
                print("[HARDWARE][AVISO] Ocupada preparando otra bebida.")
                return False
            self.busy = True

        try:
            steps = self._build_steps(recipe)
            if not steps:
                print(f"[HARDWARE][ERROR] No hay bombas configuradas para '{name}'.")
                return False

            # Datos del plan para que el panel web dibuje el riel y el llenado.
            total_ml = sum(s["amount_ml"] for s in steps)
            max_seg = max([s["seg"] for s in steps] + [max(
                b["seg"] for b in BOMBAS_CONFIG.values())])
            self._emit("drink_start", {
                "coctel": name,
                "total_ml": total_ml,
                "max_seg": max_seg,
                "steps": [{"pump": s["pump"], "ingrediente": s["ingrediente"],
                           "amount_ml": s["amount_ml"], "seg": s["seg"]} for s in steps],
            })

            print(f"\n[HARDWARE] Preparando '{name}' ({len(steps)} ingredientes)...")
            servido_ml = 0
            for i, step in enumerate(steps, 1):
                print(f"[PASO {i}/{len(steps)}] {step['ingrediente']} "
                      f"({step['amount_ml']}mL) en {step['pump']} @ {step['seg']:.2f}s")

                # Emitir el movimiento CON su duración, para que la animación del
                # vaso vaya sincronizada con el motor real.
                travel = abs(step["seg"] - self._position_seg) * FACTOR_CALIBRACION
                self._emit("move", {"to_seg": step["seg"], "max_seg": max_seg,
                                    "duration": travel, "pump": step["pump"], "index": i - 1})
                self._move_to(step["seg"])
                time.sleep(0.5)  # estabilizar antes de servir

                # Emitir el servido: el vaso se llena de servido_ml a servido_ml+amount.
                pour_time = min(step["amount_ml"] / FLOW_RATE_ML_S, MAX_PUMP_SECONDS)
                self._emit("pour_start", {
                    "pump": step["pump"], "ingrediente": step["ingrediente"],
                    "amount_ml": step["amount_ml"], "duration": pour_time,
                    "from_ml": servido_ml, "to_ml": servido_ml + step["amount_ml"],
                    "total_ml": total_ml, "index": i - 1,
                })
                self._dispense(step["pump"], step["amount_ml"])
                servido_ml += step["amount_ml"]
                self._emit("pour_end", {"pump": step["pump"], "index": i - 1,
                                        "servido_ml": servido_ml, "total_ml": total_ml})
                time.sleep(0.5)  # evitar goteo antes de moverse

            # Regresar al origen
            travel = abs(self._position_seg) * FACTOR_CALIBRACION
            self._emit("move", {"to_seg": 0.0, "max_seg": max_seg,
                                "duration": travel, "pump": None, "index": -1})
            self._move_to(0.0)
            self._emit("drink_done", {"coctel": name})
            print(f"[HARDWARE] '{name}' listo. Carro en origen.\n")
            return True

        except Exception as e:
            print(f"[HARDWARE][ERROR] Falló la preparación: {e}")
            self._all_pumps_off()
            self._stop_motor()
            return False
        finally:
            self.busy = False

    # ------------------------------------------------------------------
    # Utilidades / limpieza
    # ------------------------------------------------------------------

    def _all_pumps_off(self):
        for pump in self._pumps.values():
            pump.off()

    def move_to(self, target_seg):
        """Movimiento manual del carro (para calibración)."""
        self._move_to(float(target_seg))

    def dispense(self, pump_key, amount_ml):
        """Activación manual de una bomba (para calibración/diagnóstico)."""
        self._dispense(pump_key, float(amount_ml))

    def pulse_pump(self, pump_key, seconds=1.0):
        """Activa una bomba un tiempo fijo (para calibrar dónde cae el chorro)."""
        pump = self._pumps.get(pump_key)
        if pump is None:
            print(f"[BOMBA] '{pump_key}' no existe.")
            return
        seconds = max(0.1, min(float(seconds), MAX_PUMP_SECONDS))
        print(f"[BOMBA] {pump_key} activa {seconds:.1f}s...")
        pump.on()
        try:
            time.sleep(seconds)
        finally:
            pump.off()

    @property
    def position(self):
        """Posición actual del carro en segundos desde el origen."""
        return self._position_seg

    def cleanup(self):
        """Apaga todo y libera los pines GPIO."""
        try:
            self._all_pumps_off()
            self._stop_motor()
            for pump in self._pumps.values():
                pump.close()
            self._dir1.close()
            self._dir2.close()
            self._ena.close()
            print("[HARDWARE] GPIO liberado.")
        except Exception as e:
            print(f"[HARDWARE] Error liberando GPIO: {e}")


if __name__ == "__main__":
    # Prueba rápida en modo simulado: prepara una Paloma y muestra la secuencia.
    bar = Bartender()
    try:
        bar.preparar("Paloma")
    finally:
        bar.cleanup()
