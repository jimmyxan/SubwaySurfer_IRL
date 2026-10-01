from collections import deque

# --- SOGLIE (coordinate normalizzate MediaPipe: Y cresce verso il basso, X verso destra) ---
JUMP_THRESHOLD = 0.05       # Spostamento verso l'alto delle spalle rispetto alla calibrazione
CROUCH_THRESHOLD = 0.10     # Spostamento verso il basso delle spalle
LATERAL_THRESHOLD = 0.07    # Spostamento laterale del busto

# Rilevamento rapido del salto: sollevamento delle spalle in una breve finestra temporale
JUMP_VELOCITY_DELTA = 0.035
JUMP_VELOCITY_WINDOW = 0.15  # secondi

# Isteresi: per uscire da uno stato basta rientrare sotto questa frazione della soglia di ingresso
EXIT_HYSTERESIS = 0.5

# Frame consecutivi richiesti per confermare un cambio (1 = reazione immediata)
JUMP_CONFIRM_FRAMES = 1
CROUCH_CONFIRM_FRAMES = 2
LATERAL_CONFIRM_FRAMES = 2

SMOOTHING_ALPHA = 0.7       # Filtro EMA leggero sui segnali (1.0 = nessun filtro)
BASELINE_ALPHA = 0.005      # Deriva lenta della calibrazione, solo a riposo

LANE_STATES = {
    "SINISTRA": "SPOSTAMENTO SINISTRA",
    "CENTRO": "SPOSTAMENTO CENTRO",
    "DESTRA": "SPOSTAMENTO DESTRA",
}


class MotionDetector:
    """
    Classifica il movimento su due assi indipendenti (verticale e laterale),
    con isteresi e conferma minima, cosi' salto/capriola e cambio corsia non si
    sopprimono a vicenda. Non dipende da OpenCV/MediaPipe: riceve solo numeri.
    """

    def __init__(self):
        self.calibrate(0.5, 0.5, 0.15)

    def calibrate(self, y, x, shoulder_dist):
        self.y0 = y
        self.x0 = x
        self.d0 = shoulder_dist
        self.vertical = None   # None | "SALTO" | "CAPRIOLA"
        self.lane = "CENTRO"   # "SINISTRA" | "CENTRO" | "DESTRA"
        self._sy = None
        self._sx = None
        self._history = deque()
        self._vcand = None
        self._vcount = 0
        self._lcand = None
        self._lcount = 0

    def release_vertical(self):
        """Azzera lo stato verticale (es. utente perso di vista)."""
        self.vertical = None
        self._vcand = None
        self._vcount = 0

    @property
    def display_state(self):
        if self.vertical:
            return self.vertical
        if self.lane != "CENTRO":
            return LANE_STATES[self.lane]
        return "CORSA / IDLE"

    @property
    def is_idle(self):
        return self.vertical is None and self.lane == "CENTRO"

    def update(self, y, x, shoulder_dist, now):
        """
        Aggiorna con le misure correnti. Ritorna la lista degli eventi scattati
        in questo frame: "SALTO", "CAPRIOLA", "SPOSTAMENTO SINISTRA/DESTRA/CENTRO".
        """
        a = SMOOTHING_ALPHA
        self._sy = y if self._sy is None else a * y + (1 - a) * self._sy
        self._sx = x if self._sx is None else a * x + (1 - a) * self._sx
        sy, sx = self._sy, self._sx

        scale = min(max(shoulder_dist / self.d0, 0.5), 2.0)
        jump_t = JUMP_THRESHOLD * scale
        crouch_t = CROUCH_THRESHOLD * scale
        lateral_t = LATERAL_THRESHOLD * scale

        # Storico recente per la velocita' verticale
        self._history.append((now, sy))
        while self._history and now - self._history[0][0] > JUMP_VELOCITY_WINDOW:
            self._history.popleft()
        rise = max(v for _, v in self._history) - sy
        fast_jump = rise > JUMP_VELOCITY_DELTA * scale

        events = []

        # --- Asse verticale ---
        up = self.y0 - sy
        down = sy - self.y0
        if self.vertical == "SALTO":
            raw_v = "SALTO" if up > jump_t * EXIT_HYSTERESIS else None
        elif self.vertical == "CAPRIOLA":
            raw_v = "CAPRIOLA" if down > crouch_t * EXIT_HYSTERESIS else None
        elif up > jump_t or fast_jump:
            raw_v = "SALTO"
        elif down > crouch_t:
            raw_v = "CAPRIOLA"
        else:
            raw_v = None

        if raw_v == self.vertical:
            self._vcand, self._vcount = None, 0
        else:
            self._vcount = self._vcount + 1 if raw_v == self._vcand else 1
            self._vcand = raw_v
            needed = {"SALTO": JUMP_CONFIRM_FRAMES, "CAPRIOLA": CROUCH_CONFIRM_FRAMES}.get(raw_v, 1)
            if self._vcount >= needed:
                self.vertical = raw_v
                self._vcand, self._vcount = None, 0
                if raw_v:
                    events.append(raw_v)

        # --- Asse laterale (corsia derivata dalla posizione, con isteresi) ---
        dx = sx - self.x0
        exit_t = lateral_t * EXIT_HYSTERESIS
        if self.lane == "CENTRO":
            raw_l = "SINISTRA" if dx < -lateral_t else "DESTRA" if dx > lateral_t else "CENTRO"
        elif self.lane == "SINISTRA":
            raw_l = "DESTRA" if dx > lateral_t else "CENTRO" if dx > -exit_t else "SINISTRA"
        else:
            raw_l = "SINISTRA" if dx < -lateral_t else "CENTRO" if dx < exit_t else "DESTRA"

        if raw_l == self.lane:
            self._lcand, self._lcount = None, 0
        else:
            self._lcount = self._lcount + 1 if raw_l == self._lcand else 1
            self._lcand = raw_l
            if self._lcount >= LATERAL_CONFIRM_FRAMES:
                self.lane = raw_l
                self._lcand, self._lcount = None, 0
                events.append(LANE_STATES[raw_l])

        # --- Deriva lenta della calibrazione, solo a riposo ---
        if self.is_idle:
            b = BASELINE_ALPHA
            self.y0 = b * sy + (1 - b) * self.y0
            self.x0 = b * sx + (1 - b) * self.x0
            self.d0 = b * shoulder_dist + (1 - b) * self.d0

        return events


class ClapDetector:
    """Applauso (hoverboard): almeno 2 coppie di punti delle mani vicine per N frame, a fronte di salita."""

    CONFIRM_FRAMES = 2
    MIN_CLOSE_PAIRS = 2

    def __init__(self):
        self._count = 0
        self._active = False

    def update(self, close_pairs, valid_pairs):
        needed = min(self.MIN_CLOSE_PAIRS, valid_pairs)
        joined = valid_pairs > 0 and close_pairs >= needed
        if not joined:
            self._count = 0
            self._active = False
            return False
        self._count += 1
        if self._count >= self.CONFIRM_FRAMES and not self._active:
            self._active = True
            return True
        return False
