import subprocess
import sys
import threading
import time

GAME_TITLE_KEYWORD = "subway surfers"
TRACKER_TITLE_KEYWORD = "motion tracker"   # la finestra dell'anteprima OpenCV non e' il gioco


def get_active_window_title():
    """Titolo della finestra attiva, oppure None se non determinabile su questa piattaforma/ambiente."""
    try:
        if sys.platform == "darwin":
            script = ('tell application "System Events" to get name of front window of '
                      '(first application process whose frontmost is true)')
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1.0)
            return res.stdout.strip() if res.returncode == 0 else None
        if sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value
        if sys.platform.startswith("linux"):
            res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                                 capture_output=True, text=True, timeout=1.0)
            return res.stdout.strip() if res.returncode == 0 else None
    except Exception:
        return None
    return None


def is_game_title(title):
    t = title.lower()
    return GAME_TITLE_KEYWORD in t and TRACKER_TITLE_KEYWORD not in t


class FocusGuard:
    """
    Controlla periodicamente (thread dedicato, senza rallentare il ciclo video) se la finestra
    attiva e' quella del gioco. Se il titolo non e' determinabile (strumento mancante, permessi),
    si comporta in modo permissivo (focused=True) e lo segnala una sola volta.
    """

    def __init__(self, interval=0.4, title_getter=get_active_window_title):
        self._get_title = title_getter
        self._interval = interval
        self._focused = True
        self._unknown = False
        self._stopped = False
        self._warned = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stopped = True

    @property
    def focused(self):
        return self._focused

    @property
    def unknown(self):
        return self._unknown

    def check_now(self):
        title = self._get_title()
        if title is None:
            self._unknown = True
            self._focused = True
            if not self._warned:
                self._warned = True
                print("[FOCUS] Impossibile leggere la finestra attiva: controllo del focus disattivato.")
        else:
            self._unknown = False
            self._focused = is_game_title(title)

    def _run(self):
        while not self._stopped:
            self.check_now()
            time.sleep(self._interval)
