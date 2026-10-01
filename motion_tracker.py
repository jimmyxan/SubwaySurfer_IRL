import cv2
import mediapipe as mp
import time
import numpy as np
import threading
import subprocess
import sys
import os
import pyautogui
import webbrowser
import ui_renderer
from ui_renderer import PoseLandmark
from input_simulator import InputSimulator
from motion_logic import (MotionDetector, ClapDetector, JUMP_THRESHOLD, CROUCH_THRESHOLD,
                          LATERAL_THRESHOLD)

try:
    import mediapipe.python.solutions.pose as mp_pose
    import mediapipe.python.solutions.drawing_utils as mp_drawing
except Exception:
    try:
        from mediapipe.solutions import pose as mp_pose
        from mediapipe.solutions import drawing_utils as mp_drawing
    except Exception:
        try:
            mp_pose = mp.solutions.pose
            mp_drawing = mp.solutions.drawing_utils
        except Exception:
            mp_pose = None
            mp_drawing = None

# --- CONFIGURAZIONE ---
# Le soglie di movimento (salto, capriola, laterale, isteresi, conferma) sono in motion_logic.py.

CALIBRATION_FRAMES = 45   # Frame per calcolare la posizione di riposo (~1.5 s a 30 fps)
COUNTDOWN_SECONDS = 2.0   # Conto alla rovescia prima della calibrazione

MODEL_COMPLEXITY = 0      # 0 = piu' veloce, 1 = piu' preciso (provalo se gli FPS reggono)
SMOOTH_LANDMARKS = False  # Lo smoothing interno di MediaPipe aggiunge latenza; il filtro e' in MotionDetector

CLAP_DISTANCE_RATIO = 0.45          # Mani "vicine" se piu' vicine di questa frazione della distanza spalle
HOVERBOARD_DISPLAY_SECONDS = 0.8    # Durata del feedback HOVERBOARD (non blocca i movimenti)
FRAMING_TOLERANCE_FRAMES = 5        # Frame consecutivi di inquadratura errata tollerati prima di azzerare lo stato

# Indice della fotocamera da utilizzare.
# Su macOS, se hai un iPhone vicino, Continuity Camera potrebbe impostare l'iPhone come indice 0.
# Impostando CAMERA_INDEX = None, il programma tenterà prima l'indice 1 (webcam integrata) e farà il fallback su 0.
CAMERA_INDEX = None

# --- CONFIGURAZIONE AUTOMAZIONE E GESTIONE FINESTRE ---
# Impostare su False per disattivare l'apertura automatica del browser
AUTO_LAUNCH_GAME = True
HTML_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "index.html"))


def open_private_browser(url):
    """
    Tenta di aprire l'URL in una finestra di navigazione privata / incognito.
    Supporta macOS (sys.platform == 'darwin'), Windows (sys.platform == 'win32')
    e Linux (sys.platform.startswith('linux')).
    Priorita' macOS: Safari -> Google Chrome -> Brave -> Firefox -> Browser Predefinito.
    Priorita' Windows: Google Chrome -> Microsoft Edge -> Firefox -> Brave -> Browser Predefinito.
    Priorita' Linux: Google Chrome -> Chromium -> Firefox -> Brave -> Microsoft Edge -> Browser Predefinito.
    Al primo browser aperto con successo si ferma immediatamente.
    """
    file_url = f"file://{url}" if not url.startswith("file://") and not url.startswith("http") else url

    if sys.platform == "darwin":
        # 1. Priorita' 1: Safari (Finestra Privata via AppleScript)
        applescript_safari = f'''
        tell application "Safari"
            activate
            tell application "System Events"
                keystroke "n" using {{command down, shift down}}
            end tell
            delay 0.5
            set URL of current tab of front window to "{file_url}"
        end tell
        '''
        try:
            res = subprocess.run(["osascript", "-e", applescript_safari], capture_output=True)
            if res.returncode == 0:
                return "Safari (Finestra Privata)"
        except Exception:
            pass

        # 2. Priorita' 2: Google Chrome Incognito
        try:
            res = subprocess.run(["open", "-a", "Google Chrome", "-n", "--args", "--incognito", file_url], capture_output=True)
            if res.returncode == 0:
                return "Google Chrome (Incognito)"
        except Exception:
            pass

        # 3. Priorita' 3: Brave Incognito
        try:
            res = subprocess.run(["open", "-a", "Brave Browser", "-n", "--args", "--incognito", file_url], capture_output=True)
            if res.returncode == 0:
                return "Brave Browser (Incognito)"
        except Exception:
            pass

        # 4. Priorita' 4: Firefox Private Window
        try:
            res = subprocess.run(["open", "-a", "Firefox", "-n", "--args", "--private-window", file_url], capture_output=True)
            if res.returncode == 0:
                return "Firefox (Private)"
        except Exception:
            pass

        # 5. Fallback finale su browser predefinito
        subprocess.run(["open", file_url])
        return "Browser Predefinito"

    elif sys.platform == "win32":
        win_browsers = [
            (["cmd", "/c", "start", "", "chrome", "--incognito", file_url], "Google Chrome (Incognito)"),
            (["cmd", "/c", "start", "", "msedge", "--inprivate", file_url], "Microsoft Edge (InPrivate)"),
            (["cmd", "/c", "start", "", "firefox", "-private-window", file_url], "Firefox (Private)"),
            (["cmd", "/c", "start", "", "brave", "--incognito", file_url], "Brave Browser (Incognito)"),
        ]
        for cmd_args, label in win_browsers:
            try:
                res = subprocess.run(cmd_args, capture_output=True)
                if res.returncode == 0:
                    return label
            except Exception:
                pass

        try:
            if hasattr(os, "startfile"):
                os.startfile(file_url)
            else:
                subprocess.run(["cmd", "/c", "start", "", file_url])
        except Exception:
            webbrowser.open(file_url)
        return "Browser Predefinito"

    elif sys.platform.startswith("linux"):
        linux_browsers = [
            (["google-chrome", "--incognito", file_url], "Google Chrome (Incognito)"),
            (["chromium-browser", "--incognito", file_url], "Chromium (Incognito)"),
            (["chromium", "--incognito", file_url], "Chromium (Incognito)"),
            (["firefox", "--private-window", file_url], "Firefox (Private)"),
            (["brave-browser", "--incognito", file_url], "Brave Browser (Incognito)"),
            (["microsoft-edge", "--inprivate", file_url], "Microsoft Edge (InPrivate)"),
        ]
        for cmd_args, label in linux_browsers:
            try:
                res = subprocess.run(cmd_args, capture_output=True)
                if res.returncode == 0:
                    return label
            except Exception:
                pass

        try:
            res = subprocess.run(["xdg-open", file_url], capture_output=True)
            if res.returncode == 0:
                return "Browser Predefinito"
        except Exception:
            pass

        webbrowser.open(file_url)
        return "Browser Predefinito"

    else:
        webbrowser.open(file_url)
        return "Browser Predefinito"


def setup_browser_and_windows():
    """
    Ricava dinamicamente la risoluzione dello schermo e, se AUTO_LAUNCH_GAME e' True,
    apre il file HTML locale con il gioco Subway Surfers in una finestra di navigazione PRIVATA/INCOGNITO,
    lo posiziona nei primi 3/4 dello schermo e posiziona il cursore al 62% Y (12% piu' in basso del centro).
    Supporta macOS (darwin), Windows (win32) e Linux (linux).
    """
    screen_w, screen_h = pyautogui.size()
    browser_w = int(screen_w * 0.75)
    opencv_w = screen_w - browser_w  # Rimanente 25% esatto della larghezza schermo

    # Coordinate del tasto START (centro orizzontale browser, 12% sotto il centro verticale dello schermo)
    target_x = browser_w // 2
    target_y = int(screen_h * 0.62)

    if AUTO_LAUNCH_GAME:
        print(f"[SETUP] Avvio del browser in modalita' PRIVATA/INCOGNITO con file locale: {HTML_FILE_PATH}...")
        # a) Apri il file HTML locale nel browser in modalita' privata
        browser_used = open_private_browser(HTML_FILE_PATH)
        print(f"[SETUP] Avviato con successo in: {browser_used}")
        
        # b) Attendi 2 secondi per il caricamento della finestra
        time.sleep(2)
        
        # c) Ridimensiona e riposiziona la finestra del browser nei primi 3/4 dello schermo (X: 0 -> 75%)
        if sys.platform == "darwin":
            applescript = f'''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set frontAppName to name of frontApp
                tell process frontAppName
                    if exists window 1 then
                        set position of window 1 to {{0, 0}}
                        set size of window 1 to {{{browser_w}, {screen_h}}}
                    end if
                end tell
            end tell
            '''
            try:
                subprocess.run(["osascript", "-e", applescript], check=True)
            except Exception as e:
                print(f"[SETUP] Avviso AppleScript durante il ridimensionamento finestra: {e}")
        elif sys.platform == "win32":
            resized = False
            try:
                import pygetwindow as gw
                win = gw.getActiveWindow()
                if win:
                    win.moveTo(0, 0)
                    win.resizeTo(browser_w, screen_h)
                    resized = True
            except Exception:
                pass

            if not resized:
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if hwnd:
                        ctypes.windll.user32.MoveWindow(hwnd, 0, 0, browser_w, screen_h, True)
                except Exception as e:
                    print(f"[SETUP] Avviso Windows API / pygetwindow durante il ridimensionamento finestra: {e}")
        elif sys.platform.startswith("linux"):
            try:
                res = subprocess.run(["wmctrl", "-r", ":ACTIVE:", "-e", f"0,0,0,{browser_w},{screen_h}"], capture_output=True)
                if res.returncode != 0:
                    subprocess.run(["xdotool", "getactivewindow", "windowmove", "0", "0", "windowsize", f"{browser_w}", f"{screen_h}"], capture_output=True)
            except Exception as e:
                print(f"[SETUP] Avviso Linux window manager (wmctrl/xdotool) durante il ridimensionamento finestra: {e}")

        # d) Posiziona il cursore sul tasto START (senza fare click fino al termine della calibrazione)
        pyautogui.moveTo(target_x, target_y)
        time.sleep(0.5)

    return screen_w, screen_h, browser_w, opencv_w, target_x, target_y


class LatestFrameReader:
    """Legge la webcam in un thread dedicato e conserva solo l'ultimo frame (niente buffer di frame vecchi)."""

    def __init__(self, cap):
        self.cap = cap
        self._lock = threading.Lock()
        self._frame = None
        self._seq = 0
        self._ok = True
        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stopped:
            ret, frame = self.cap.read()
            with self._lock:
                if not ret:
                    self._ok = False
                    return
                self._frame = frame
                self._seq += 1

    def read(self, last_seq, timeout=1.0):
        """Attende un frame piu' recente di last_seq. Ritorna (ok, frame, seq)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._ok:
                    return False, None, last_seq
                if self._frame is not None and self._seq != last_seq:
                    return True, self._frame, self._seq
            time.sleep(0.001)
        return False, None, last_seq

    def stop(self):
        self._stopped = True
        self._thread.join(timeout=1.0)


def open_camera():
    if CAMERA_INDEX is not None:
        print(f"Tentativo di connessione alla fotocamera con indice fisso: {CAMERA_INDEX}...")
        cap = cv2.VideoCapture(CAMERA_INDEX)
    else:
        print("Rilevamento automatico della webcam... Tentativo con indice 1 (webcam integrata Mac)...")
        cap = cv2.VideoCapture(1)
        if not cap.isOpened():
            print("Indice 1 non disponibile. Fallback su indice 0...")
            cap.release()
            cap = cv2.VideoCapture(0)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 60)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def draw_guides(frame, detector, width, height, scale=1.0):
    y_base = int(detector.y0 * height)
    cv2.line(frame, (0, y_base), (width, y_base), (0, 255, 255), 1)
    cv2.line(frame, (0, int((detector.y0 - JUMP_THRESHOLD * scale) * height)),
             (width, int((detector.y0 - JUMP_THRESHOLD * scale) * height)), (57, 255, 20), 1, cv2.LINE_4)
    cv2.line(frame, (0, int((detector.y0 + CROUCH_THRESHOLD * scale) * height)),
             (width, int((detector.y0 + CROUCH_THRESHOLD * scale) * height)), (0, 242, 254), 1, cv2.LINE_4)
    for sign in (-1, 1):
        px = int((detector.x0 + sign * LATERAL_THRESHOLD * scale) * width)
        cv2.line(frame, (px, 0), (px, height), (255, 255, 0), 1)


def main():
    # Inizializzazione MediaPipe Pose
    pose = None
    if mp_pose is not None:
        try:
            pose = mp_pose.Pose(
                static_image_mode=False,
                model_complexity=MODEL_COMPLEXITY,
                smooth_landmarks=SMOOTH_LANDMARKS,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except Exception as e:
            print(f"[ERRORE] Impossibile creare l'istanza MediaPipe Pose: {e}")
            pose = None

    if pose is None:
        print("\n[ERRORE CRITICO] Impossibile inizializzare MediaPipe Pose!")
        print(f"Interprete Python in uso: {sys.executable} (Python {sys.version.split()[0]})")
        mp_ver = getattr(mp, '__version__', 'non disponibile')
        print(f"Versione MediaPipe: {mp_ver}")
        print("\nCausa probabile:")
        if sys.version_info >= (3, 13):
            print("- Stai usando Python 3.13+. MediaPipe Solutions (Pose) e' supportato solo su Python <= 3.12.")
        else:
            print("- MediaPipe Pose Solutions non e' presente o e' incompatibile in questo ambiente.")
        print("\nSOLUZIONE:")
        print("1. Se sei in un terminale con Conda attivo, disattivalo prima:")
        print("   conda deactivate")
        print("2. Esegui direttamente con l'ambiente virtuale del progetto:")
        print("   ./.venv/bin/python3 motion_tracker.py")
        print("3. Oppure attiva l'ambiente virtuale dedicato:")
        print("   source .venv/bin/activate")
        print("   python3 motion_tracker.py\n")
        return

    simulator = InputSimulator()
    detector = MotionDetector()
    clap = ClapDetector()

    cap = open_camera()
    if not cap.isOpened():
        print("Errore: Impossibile accedere a nessuna webcam.")
        return
    reader = LatestFrameReader(cap)

    # Stato di calibrazione
    calibrated = False
    calib_y, calib_x, calib_d, calib_hips = [], [], [], []
    use_hips_detection = False
    countdown_start_time = None
    game_started = False
    bad_framing_frames = 0

    hoverboard_until = 0.0

    screen_w, screen_h, browser_w, opencv_w, target_x, target_y = setup_browser_and_windows()

    print("Subway Surfers Motion Tracker avviato. 'ESC' per uscire, 'R' per ricalibrare.")

    cv2.namedWindow("Subway Surfers Motion Tracker", cv2.WINDOW_NORMAL)
    cv2.moveWindow("Subway Surfers Motion Tracker", browser_w, 0)
    cv2.resizeWindow("Subway Surfers Motion Tracker", opencv_w, screen_h)

    seq = -1
    fps = 0.0
    infer_ms = 0.0
    last_loop = time.monotonic()

    while True:
        ok, frame, seq = reader.read(seq)
        if not ok:
            print("Errore: Impossibile leggere il frame dalla webcam.")
            break

        now = time.monotonic()
        dt = now - last_loop
        last_loop = now
        if dt > 0:
            fps = 0.9 * fps + 0.1 * (1.0 / dt) if fps else 1.0 / dt

        frame = cv2.flip(frame, 1)
        height, width, _ = frame.shape

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        t0 = time.monotonic()
        results = pose.process(rgb_frame)
        infer_ms = 0.9 * infer_ms + 0.1 * (time.monotonic() - t0) * 1000.0

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            left_shoulder = landmarks[PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[PoseLandmark.RIGHT_SHOULDER]
            left_hip = landmarks[PoseLandmark.LEFT_HIP]
            right_hip = landmarks[PoseLandmark.RIGHT_HIP]

            y_shoulders = (left_shoulder.y + right_shoulder.y) / 2
            x_torso = (left_shoulder.x + right_shoulder.x) / 2
            shoulder_dist = float(np.linalg.norm([left_shoulder.x - right_shoulder.x,
                                                  left_shoulder.y - right_shoulder.y]))

            ls_px = (int(left_shoulder.x * width), int(left_shoulder.y * height))
            rs_px = (int(right_shoulder.x * width), int(right_shoulder.y * height))
            torso_px = (int(x_torso * width), int(y_shoulders * height))

            if mp_drawing is not None and mp_pose is not None:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
                )
            cv2.circle(frame, ls_px, 8, (0, 255, 255), -1)
            cv2.circle(frame, rs_px, 8, (0, 255, 255), -1)
            cv2.circle(frame, torso_px, 10, (0, 0, 255), -1)

            # --- CALIBRAZIONE ---
            if not calibrated:
                is_framed_calib, warning_calib = ui_renderer.check_framing(landmarks, use_hips=False)

                if is_framed_calib:
                    if countdown_start_time is None:
                        countdown_start_time = now
                    elapsed_countdown = now - countdown_start_time

                    if elapsed_countdown < COUNTDOWN_SECONDS:
                        ui_renderer.draw_countdown_popup(frame, int(COUNTDOWN_SECONDS - elapsed_countdown) + 1)
                    else:
                        calib_y.append(y_shoulders)
                        calib_x.append(x_torso)
                        calib_d.append(shoulder_dist)
                        calib_hips.append((left_hip.visibility + right_hip.visibility) / 2)

                        progress = int((len(calib_y) / CALIBRATION_FRAMES) * 100)
                        ui_renderer.draw_calibration_popup(frame, progress)

                        if len(calib_y) >= CALIBRATION_FRAMES:
                            # Mediana: robusta ai frame rumorosi
                            detector.calibrate(float(np.median(calib_y)), float(np.median(calib_x)),
                                               float(np.median(calib_d)))
                            simulator.corsia_attuale = "CENTRO"
                            use_hips_detection = float(np.mean(calib_hips)) > 0.5
                            calibrated = True
                            bad_framing_frames = 0
                            print("Calibrazione completata!")
                            print(f" - Y spalle base: {detector.y0:.3f}")
                            print(f" - X busto base: {detector.x0:.3f}")
                            print(f" - Distanza spalle base: {detector.d0:.3f}")
                            print(f" - Controllo fianchi attivo: {use_hips_detection}")

                            if AUTO_LAUNCH_GAME and not game_started:
                                game_started = True
                                print("[TRACKER] Calibrazione ultimata! Invio click di avvio sul tasto START...")
                                pyautogui.click(target_x, target_y)
                                pyautogui.click(target_x, target_y)
                                time.sleep(1.5)
                                pyautogui.click(target_x, target_y)
                else:
                    countdown_start_time = None
                    progress = int((len(calib_y) / CALIBRATION_FRAMES) * 100)
                    ui_renderer.draw_calibration_popup(frame, progress, warning=warning_calib)

            # --- RILEVAMENTO MOVIMENTI ---
            else:
                is_framed, warning_msg = ui_renderer.check_framing(landmarks, use_hips=use_hips_detection)

                if not is_framed:
                    # Tolleranza: un frame sporadico fuori inquadratura (es. durante un salto) non resetta nulla
                    bad_framing_frames += 1
                    if bad_framing_frames > FRAMING_TOLERANCE_FRAMES:
                        detector.release_vertical()
                    ui_renderer.draw_hud(frame, detector.display_state)
                    ui_renderer.draw_warning_overlay(frame, f"INQUADRATURA COMPROMESSA: {warning_msg}")
                else:
                    bad_framing_frames = 0

                    # Applauso -> HOVERBOARD (non blocca gli altri movimenti)
                    hand_pairs = [
                        (PoseLandmark.LEFT_WRIST, PoseLandmark.RIGHT_WRIST),
                        (PoseLandmark.LEFT_INDEX, PoseLandmark.RIGHT_INDEX),
                        (PoseLandmark.LEFT_PINKY, PoseLandmark.RIGHT_PINKY),
                        (PoseLandmark.LEFT_THUMB, PoseLandmark.RIGHT_THUMB),
                    ]
                    max_hand_dist = CLAP_DISTANCE_RATIO * detector.d0
                    valid = 0
                    close = 0
                    for l_idx, r_idx in hand_pairs:
                        l_pt, r_pt = landmarks[l_idx], landmarks[r_idx]
                        if l_pt.visibility > 0.5 and r_pt.visibility > 0.5:
                            valid += 1
                            if np.hypot(l_pt.x - r_pt.x, l_pt.y - r_pt.y) < max_hand_dist:
                                close += 1
                    for idx in (PoseLandmark.LEFT_WRIST, PoseLandmark.RIGHT_WRIST):
                        pt = landmarks[idx]
                        cv2.circle(frame, (int(pt.x * width), int(pt.y * height)), 6, (255, 0, 255), -1)

                    if clap.update(close, valid):
                        hoverboard_until = now + HOVERBOARD_DISPLAY_SECONDS
                        print("[TRACKER] GESTO RILEVATO: Applauso! Attivazione HOVERBOARD")
                        simulator.simulate(detector.display_state, "HOVERBOARD")

                    prev_lane = detector.lane
                    events = detector.update(y_shoulders, x_torso, shoulder_dist, now)
                    for event in events:
                        print(f"[TRACKER] Evento: {event}")
                        simulator.simulate(prev_lane, event)

                    draw_guides(frame, detector, width, height,
                                min(max(shoulder_dist / detector.d0, 0.5), 2.0))

                    if now < hoverboard_until and detector.is_idle:
                        ui_renderer.draw_hud(frame, "HOVERBOARD")
                    else:
                        ui_renderer.draw_hud(frame, detector.display_state)
        else:
            if not calibrated:
                countdown_start_time = None
                ui_renderer.draw_calibration_popup(frame, 0, warning="Nessun utente rilevato. Posizionati davanti alla fotocamera")
            else:
                detector.release_vertical()
                ui_renderer.draw_hud(frame, "NESSUN UTENTE RILEVATO")

        cv2.putText(frame, f"{fps:.0f} FPS | inferenza {infer_ms:.0f} ms", (10, height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imshow("Subway Surfers Motion Tracker", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
        if key in (ord('r'), ord('R')):
            print("[TRACKER] Ricalibrazione richiesta.")
            calibrated = False
            calib_y, calib_x, calib_d, calib_hips = [], [], [], []
            countdown_start_time = None

    reader.stop()
    cap.release()
    cv2.destroyAllWindows()
    pose.close()
    print("Programma terminato pulitamente.")


if __name__ == "__main__":
    main()
