# ============================================================
# MIA - Música de espera y preparación (reproducción local con mpg123)
# ============================================================
# Reproduce música de espera mientras MIA está en reposo (idle),
# música especial cuando prepara un cóctel (prep), y reduce el volumen
# un 30% cuando detecta que el usuario le está hablando.
# ============================================================
import glob
import os
import random
import subprocess
import threading

from config import MUSIC_DIR, MUSIC_VOLUME, MUSIC_ENABLED, AUDIO_PLAYER_CMD, AUDIO_OUTPUT_DEVICE


class MusicPlayer:
    """Controla la música de fondo (espera / preparación / atenuación por voz)."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self.current_mode = None  # "idle", "prep", None
        self.is_ducked = False
        self.current_track = None
        self.idle_tracks, self.prep_tracks = self._find_tracks()

        if MUSIC_ENABLED and not (self.idle_tracks or self.prep_tracks):
            print(f"[MUSICA][AVISO] No se encontraron .mp3 en {MUSIC_DIR}.")

    @staticmethod
    def _find_tracks():
        try:
            all_tracks = sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")))
        except Exception:
            all_tracks = []

        idle = []
        prep = []
        for t in all_tracks:
            fname = os.path.basename(t).lower()
            if any(k in fname for k in ("prep", "coctel", "cocktail")):
                prep.append(t)
            elif any(k in fname for k in ("espera", "idle", "hold")):
                idle.append(t)
            else:
                idle.append(t)

        if not idle and all_tracks:
            idle = all_tracks
        if not prep and all_tracks:
            prep = [t for t in all_tracks if t not in idle] or all_tracks

        return idle, prep

    def play_idle(self):
        self.play(mode="idle")

    def play_prep(self):
        self.play(mode="prep")

    def set_ducked(self, ducked: bool):
        """Aplica o remueve la atenuación del 30% si le están hablando."""
        with self._lock:
            if self.is_ducked == ducked:
                return
            self.is_ducked = ducked
            if self._proc and self._proc.poll() is None and self.current_mode:
                self._start_proc(self.current_mode, force=True)

    def play(self, mode="idle", force=False):
        """Arranca la música en el modo indicado ('idle' o 'prep')."""
        if not MUSIC_ENABLED:
            return
        with self._lock:
            if self._proc and self._proc.poll() is None and self.current_mode == mode and not force:
                return  # ya sonando este modo

            tracks = self.prep_tracks if mode == "prep" else self.idle_tracks
            if not tracks:
                return

            self._stop_proc()
            self.current_mode = mode
            self.current_track = random.choice(tracks)
            self._start_proc(mode)

    def start(self, mode="idle"):
        """Método compatible hacia atrás."""
        self.play(mode=mode)

    def _start_proc(self, mode, force=False):
        tracks = self.prep_tracks if mode == "prep" else self.idle_tracks
        if not tracks:
            return

        if force and self.current_track in tracks:
            track = self.current_track
        else:
            track = random.choice(tracks)
            self.current_track = track

        # Si le están hablando (is_ducked), bajamos 30% (factor 0.70)
        vol_factor = 0.70 if self.is_ducked else 1.0
        effective_vol = max(0.0, min(1.0, MUSIC_VOLUME * vol_factor))
        scale = str(int(effective_vol * 32768))

        cmd = [AUDIO_PLAYER_CMD, "-q", "--loop", "-1", "-f", scale]
        if AUDIO_OUTPUT_DEVICE:
            cmd.extend(["-a", AUDIO_OUTPUT_DEVICE])
        cmd.append(track)

        try:
            if self._proc and self._proc.poll() is None:
                self._stop_proc()

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            duck_str = " (-30% por voz)" if self.is_ducked else ""
            print(f"[MUSICA] Modo '{mode}'{duck_str} - Sonando: {os.path.basename(track)}")
        except FileNotFoundError:
            print(f"[MUSICA][ERROR] '{AUDIO_PLAYER_CMD}' no está instalado.")
            self._proc = None

    def _stop_proc(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    def stop(self):
        """Detiene la música si está sonando."""
        with self._lock:
            self._stop_proc()
            self.current_mode = None
            print("[MUSICA] Detenida.")


if __name__ == "__main__":
    import time
    m = MusicPlayer()
    print("Probando música de espera (5s)...")
    m.play_idle()
    time.sleep(3)
    print("Atenuando por voz (3s)...")
    m.set_ducked(True)
    time.sleep(3)
    print("Probando música de preparación de cóctel (5s)...")
    m.set_ducked(False)
    m.play_prep()
    time.sleep(5)
    m.stop()
