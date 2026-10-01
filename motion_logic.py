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

# Un gesto e' valido solo dopo un periodo di riposo (segnale nella zona neutra)
REST_SECONDS_VERTICAL = 0.15
REST_SECONDS_LATERAL = 0.10
ARM_GRACE_SECONDS = 0.35    # Dopo il riposo, il gesto deve iniziare entro questo tempo dall'uscita dalla zona neutra

# Zona morta dopo un gesto (rimbalzo di atterraggio, oscillazione di ritorno)
DEAD_ZONE_VERTICAL = 0.30
DEAD_ZONE_LATERAL = 0.12

# Robustezza del segnale
MIN_VISIBILITY = 0.6        # Sotto questa visibilita' i landmark non vengono usati
MAX_JUMP_PER_FRAME = 0.15   # Salto di un landmark in un frame: considerato errore del modello
MAX_CONSECUTIVE_OUTLIERS = 3

# Salto "vero": anche i fianchi devono salire e il busto non deve inclinarsi (accorciarsi/allungarsi)
JUMP_HIP_FOLLOW = 0.4       # Frazione della soglia di salto che i fianchi devono raggiungere
JUMP_MAX_TORSO_CHANGE = 0.2

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

    def calibrate(self, y, x, shoulder_dist, hip_y=None):
        """y = Y delle spalle; hip_y (opzionale) = Y dei fianchi, abilita i controlli anti-falso-positivo."""
        self.sho0 = y
        self.hip0 = hip_y
        self.y0 = y if hip_y is None else (y + hip_y) / 2   # riferimento verticale
        self.x0 = x
        self.d0 = shoulder_dist
        self.reset_state()

    def reset_state(self):
        """Riporta lo stato a riposo/centro senza toccare la calibrazione."""
        self.vertical = None   # None | "SALTO" | "CAPRIOLA"
        self.lane = "CENTRO"   # "SINISTRA" | "CENTRO" | "DESTRA"
        self._sy = None
        self._sh = None
        self._sx = None
        self._last_raw = None
        self._outliers = 0
        self._history = deque()
        self._vcand = None
        self._vcount = 0
        self._lcand = None
        self._lcount = 0
        self._v_rest_since = None
        self._l_rest_since = None
        self._v_armed_until = float("inf")   # inizialmente armato
        self._l_armed_until = float("inf")
        self._v_lock_until = 0.0
        self._l_lock_until = 0.0

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

    def update(self, y, x, shoulder_dist, now, hip_y=None):
        """
        Aggiorna con le misure correnti (y/hip_y = Y di spalle/fianchi, x = X del busto).
        Ritorna la lista degli eventi scattati in questo frame: "SALTO", "CAPRIOLA",
        "SPOSTAMENTO SINISTRA/DESTRA/CENTRO".
        """
        if self.hip0 is not None and hip_y is None:
            return []  # calibrato con i fianchi ma ora non disponibili: segnale non confrontabile
        use_hips = hip_y is not None and self.hip0 is not None

        # Scarta i salti improvvisi di landmark (errori del modello); dopo qualche frame
        # consecutivo li accetta, perche' allora l'utente si e' davvero spostato.
        raw = (y, x, hip_y if use_hips else 0.0)
        if self._last_raw is not None and self._outliers < MAX_CONSECUTIVE_OUTLIERS and (
                abs(raw[0] - self._last_raw[0]) > MAX_JUMP_PER_FRAME
                or abs(raw[1] - self._last_raw[1]) > MAX_JUMP_PER_FRAME
                or abs(raw[2] - self._last_raw[2]) > MAX_JUMP_PER_FRAME):
            self._outliers += 1
            return []
        self._outliers = 0
        self._last_raw = raw

        a = SMOOTHING_ALPHA
        self._sy = y if self._sy is None else a * y + (1 - a) * self._sy
        self._sx = x if self._sx is None else a * x + (1 - a) * self._sx
        if use_hips:
            self._sh = hip_y if self._sh is None else a * hip_y + (1 - a) * self._sh
        sho, sx = self._sy, self._sx
        # Riferimento verticale: media spalle+fianchi (un'inclinazione in avanti pesa la meta')
        sy = (sho + self._sh) / 2 if use_hips else sho

        scale = min(max(shoulder_dist / self.d0, 0.5), 2.0)
        jump_t = JUMP_THRESHOLD * scale
        crouch_t = CROUCH_THRESHOLD * scale
        lateral_t = LATERAL_THRESHOLD * scale

        # Storico recente per la velocita' verticale
        self._history.append((now, sy))
        while self._history and now - self._history[0][0] > JUMP_VELOCITY_WINDOW:
            self._history.popleft()
        lowest = max(v for _, v in self._history)
        # Il salto rapido parte dalla zona neutra: risalire da una posizione bassa (es. rialzarsi) non e' un salto
        fast_jump = (lowest - sy) > JUMP_VELOCITY_DELTA * scale and lowest < self.y0 + jump_t * EXIT_HYSTERESIS

        events = []

        # --- Asse verticale ---
        up = self.y0 - sy
        down = sy - self.y0

        # Zona neutra: dopo REST_SECONDS di riposo il gesto e' "armato" per ARM_GRACE_SECONDS
        neutral_v = up < jump_t * EXIT_HYSTERESIS and down < crouch_t * EXIT_HYSTERESIS
        if neutral_v:
            if self._v_rest_since is None:
                self._v_rest_since = now
            if now - self._v_rest_since >= REST_SECONDS_VERTICAL:
                self._v_armed_until = now + ARM_GRACE_SECONDS
        else:
            self._v_rest_since = None
            if self._v_armed_until == float("inf"):   # primo movimento dopo l'avvio
                self._v_armed_until = now + ARM_GRACE_SECONDS
        entries_open = now <= self._v_armed_until and now >= self._v_lock_until

        # Il salto vero solleva anche i fianchi e non inclina il busto
        jump_ok = True
        if use_hips:
            hip_up = self.hip0 - self._sh
            torso_ratio = (self._sh - sho) / max(self.hip0 - self.sho0, 1e-6)
            jump_ok = (hip_up >= JUMP_HIP_FOLLOW * jump_t
                       and abs(torso_ratio - 1.0) <= JUMP_MAX_TORSO_CHANGE)

        if self.vertical == "SALTO":
            raw_v = "SALTO" if up > jump_t * EXIT_HYSTERESIS else None
        elif self.vertical == "CAPRIOLA":
            raw_v = "CAPRIOLA" if down > crouch_t * EXIT_HYSTERESIS else None
        elif not entries_open:
            raw_v = None
        elif (up > jump_t or fast_jump) and jump_ok:
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
                if raw_v is None:
                    # Fine del gesto: zona morta (rimbalzo) e nuovo periodo di riposo richiesto
                    self._v_lock_until = now + DEAD_ZONE_VERTICAL
                    self._v_rest_since = None
                    self._v_armed_until = 0.0
                self.vertical = raw_v
                self._vcand, self._vcount = None, 0
                if raw_v:
                    events.append(raw_v)

        # --- Asse laterale (corsia derivata dalla posizione, con isteresi) ---
        dx = sx - self.x0
        exit_t = lateral_t * EXIT_HYSTERESIS
        if self.lane == "CENTRO":
            if abs(dx) < exit_t:
                if self._l_rest_since is None:
                    self._l_rest_since = now
                if now - self._l_rest_since >= REST_SECONDS_LATERAL:
                    self._l_armed_until = now + ARM_GRACE_SECONDS
            else:
                self._l_rest_since = None
                if self._l_armed_until == float("inf"):
                    self._l_armed_until = now + ARM_GRACE_SECONDS
            armed_l = now <= self._l_armed_until
            raw_l = "SINISTRA" if dx < -lateral_t else "DESTRA" if dx > lateral_t else "CENTRO"
            if raw_l != "CENTRO" and not (armed_l and now >= self._l_lock_until):
                raw_l = "CENTRO"
        elif self.lane == "SINISTRA":
            raw_l = "DESTRA" if dx > lateral_t else "CENTRO" if dx > -exit_t else "SINISTRA"
        else:
            raw_l = "SINISTRA" if dx < -lateral_t else "CENTRO" if dx < exit_t else "DESTRA"
        if raw_l != self.lane and raw_l != "CENTRO" and now < self._l_lock_until:
            raw_l = self.lane  # cambio diretto sinistra<->destra bloccato dalla zona morta

        if raw_l == self.lane:
            self._lcand, self._lcount = None, 0
        else:
            self._lcount = self._lcount + 1 if raw_l == self._lcand else 1
            self._lcand = raw_l
            if self._lcount >= LATERAL_CONFIRM_FRAMES:
                self.lane = raw_l
                self._lcand, self._lcount = None, 0
                self._l_lock_until = now + DEAD_ZONE_LATERAL
                if raw_l == "CENTRO":
                    self._l_rest_since = None
                    self._l_armed_until = 0.0
                events.append(LANE_STATES[raw_l])

        # --- Deriva lenta della calibrazione, solo a riposo ---
        if self.is_idle:
            b = BASELINE_ALPHA
            self.y0 = b * sy + (1 - b) * self.y0
            self.x0 = b * sx + (1 - b) * self.x0
            self.d0 = b * shoulder_dist + (1 - b) * self.d0
            if use_hips:
                self.sho0 = b * sho + (1 - b) * self.sho0
                self.hip0 = b * self._sh + (1 - b) * self.hip0

        return events


def landmarks_reliable(visibilities):
    """True se tutti i landmark necessari hanno visibilita' sufficiente."""
    return all(v >= MIN_VISIBILITY for v in visibilities)


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
