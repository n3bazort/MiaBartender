# ============================================================
# MIA - Música de espera (reproducción local con mpg123)
# ============================================================
# Reproduce en bucle una pista de espera MIENTRAS se dispensa la bebida
# (Opción A: suena en el hueco silencioso, sin pisar la voz de MIA).
#
# Esto controla el PARLANTE LOCAL de la Raspberry Pi. En el panel web, la
# música se reproduce en el navegador (ver index.html); este módulo se usa
# para el modo por voz local (main.py) en la Pi real.
#
# Es MUY ligero: mpg123 reproduciendo un MP3 consume poco CPU en una Pi 3.
# ============================================================
import glob
import os
import random
import subprocess

from config import MUSIC_DIR, MUSIC_VOLUME, MUSIC_ENABLED, AUDIO_PLAYER_CMD


class MusicPlayer:
    """Reproduce música de espera en bucle con mpg123 (proceso en segundo plano)."""

    def __init__(self):
        self._proc = None
        self.tracks = self._find_tracks()
        if MUSIC_ENABLED and not self.tracks:
            print(f"[MUSICA][AVISO] No se encontraron .mp3 en {MUSIC_DIR}.")

    @staticmethod
    def _find_tracks():
        try:
            return sorted(glob.glob(os.path.join(MUSIC_DIR, "*.mp3")))
        except Exception:
            return []

    def start(self):
        """Arranca la música en bucle (no bloquea). Elige una pista al azar."""
        if not MUSIC_ENABLED or not self.tracks:
            return
        if self._proc and self._proc.poll() is None:
            return  # ya sonando

        track = random.choice(self.tracks)
        # mpg123: --loop -1 = bucle infinito; -f = factor de volumen (0..32768).
        scale = str(int(max(0.0, min(1.0, MUSIC_VOLUME)) * 32768))
        try:
            self._proc = subprocess.Popen(
                [AUDIO_PLAYER_CMD, "-q", "--loop", "-1", "-f", scale, track],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[MUSICA] Sonando: {os.path.basename(track)}")
        except FileNotFoundError:
            print(f"[MUSICA][ERROR] '{AUDIO_PLAYER_CMD}' no está instalado "
                  f"(en la Pi: sudo apt install mpg123).")
            self._proc = None

    def stop(self):
        """Detiene la música si está sonando."""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            print("[MUSICA] Detenida.")
        self._proc = None


if __name__ == "__main__":
    import time
    m = MusicPlayer()
    print("Reproduciendo 5s de música de espera...")
    m.start()
    time.sleep(5)
    m.stop()
