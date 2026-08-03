import cv2
import mediapipe as mp
import time
import numpy as np
import ssl
import subprocess
import sys
import os
import pyautogui
import webbrowser
import ui_renderer
from ui_renderer import PoseLandmark
from input_simulator import InputSimulator

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

# --- CONFIGURAZIONE SOGLIE E DEBOUNCE ---
# Le coordinate di MediaPipe sono normalizzate tra 0.0 e 1.0 rispetto alla risoluzione del frame.
# L'asse Y cresce verso il basso (0 in alto, 1 in basso).
# L'asse X cresce verso destra (0 a sinistra, 1 a destra).

JUMP_THRESHOLD = 0.07     # Spostamento verso l'alto (diminuzione di Y delle spalle)
CROUCH_THRESHOLD = 0.12   # Spostamento verso il basso (aumento di Y delle spalle, aumentato per evitare falsi positivi pre-salto)
LATERAL_THRESHOLD = 0.10  # Spostamento laterale (X del busto rispetto alla calibrazione)

MIN_STATE_FRAMES = 6      # Numero minimo di frame in cui uno stato deve rimanere attivo (evita sfarfallio)
CALIBRATION_FRAMES = 120  # Numero di frame per calcolare la posizione di riposo (aumentato a 120 / ~4 secondi)

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


def main():
    # Inizializzazione MediaPipe Pose
    pose = None
    if mp_pose is not None:
        try:
            pose = mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                smooth_landmarks=True,
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

    # Inizializzazione Input Simulator per la tastiera
    simulator = InputSimulator()

    # Inizializzazione Webcam con fallback automatico
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

    if not cap.isOpened():
        print("Errore: Impossibile accedere a nessuna webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 60)

    # Variabili per la calibrazione
    calibrated = False
    calibration_y_shoulders = []
    calibration_x_torso = []
    calibration_shoulder_dist = []
    calibration_hips_visibility = []
    
    y_calibrated = 0.5
    x_calibrated = 0.5
    shoulder_dist_calibrated = 0.15
    use_hips_detection = False
    countdown_start_time = None

    # Gestione dello stato e debounce
    current_state = "CORSA / IDLE"
    state_frame_count = 0

    # Rilevamento applauso (Hoverboard)
    hands_were_joined = False
    hoverboard_frames_left = 0

    # Setup risoluzione e layout dinamico dello schermo (Browser 3/4 + OpenCV 1/4)
    screen_w, screen_h, browser_w, opencv_w, target_x, target_y = setup_browser_and_windows()

    print("Subway Surfers Motion Tracker avviato. Premi 'ESC' nella finestra video per uscire.")

    # Configura la finestra dell'anteprima OpenCV nell'ultimo quarto a destra (X = 75% larghezza schermo)
    cv2.namedWindow("Subway Surfers Motion Tracker", cv2.WINDOW_NORMAL)
    cv2.moveWindow("Subway Surfers Motion Tracker", browser_w, 0)
    cv2.resizeWindow("Subway Surfers Motion Tracker", opencv_w, screen_h)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Errore: Impossibile leggere il frame dalla webcam.")
            break

        # 1. Specchia orizzontalmente l'immagine per un controllo intuitivo
        frame = cv2.flip(frame, 1)
        height, width, _ = frame.shape

        # Converti il frame in RGB per MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)

        raw_state = "CORSA / IDLE"

        if results.pose_landmarks:
            # Estrazione dei landmarks
            landmarks = results.pose_landmarks.landmark
            
            # Punti di interesse: spalla sinistra (11) e spalla destra (12)
            left_shoulder = landmarks[PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[PoseLandmark.RIGHT_SHOULDER]
            left_hip = landmarks[PoseLandmark.LEFT_HIP]
            right_hip = landmarks[PoseLandmark.RIGHT_HIP]

            # Calcolo dei valori correnti
            # Coordinata Y media delle spalle
            y_shoulders = (left_shoulder.y + right_shoulder.y) / 2
            # Coordinata X media del busto (midpoint delle spalle)
            x_torso = (left_shoulder.x + right_shoulder.x) / 2
            # Distanza attuale tra le spalle (usata per calcolare lo scaling)
            shoulder_dist = np.linalg.norm(np.array([left_shoulder.x - right_shoulder.x, left_shoulder.y - right_shoulder.y]))

            # Coordinate pixel per il disegno
            ls_px = (int(left_shoulder.x * width), int(left_shoulder.y * height))
            rs_px = (int(right_shoulder.x * width), int(right_shoulder.y * height))
            torso_px = (int(x_torso * width), int(y_shoulders * height))

            # Disegna lo scheletro standard di MediaPipe
            if mp_drawing is not None and mp_pose is not None:
                mp_drawing.draw_landmarks(
                    frame, 
                    results.pose_landmarks, 
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2)
                )

            # Evidenzia i punti chiave con cerchi personalizzati
            cv2.circle(frame, ls_px, 8, (0, 255, 255), -1)   # Spalla sinistra (Giallo)
            cv2.circle(frame, rs_px, 8, (0, 255, 255), -1)   # Spalla destra (Giallo)
            cv2.circle(frame, torso_px, 10, (0, 0, 255), -1) # Centro Busto (Rosso)

            # --- LOGICA DI CALIBRAZIONE ---
            if not calibrated:
                # Verifica inquadratura base (spalle e clipping) prima di procedere con la calibrazione
                is_framed_calib, warning_calib = ui_renderer.check_framing(landmarks, use_hips=False)
                
                if is_framed_calib:
                    if countdown_start_time is None:
                        countdown_start_time = time.time()
                        
                    elapsed_countdown = time.time() - countdown_start_time
                    
                    if elapsed_countdown < 3.0:
                        # Fase di conto alla rovescia
                        seconds_left = int(3.0 - elapsed_countdown) + 1
                        ui_renderer.draw_countdown_popup(frame, seconds_left)
                    else:
                        # Calibrazione vera e propria
                        calibration_y_shoulders.append(y_shoulders)
                        calibration_x_torso.append(x_torso)
                        calibration_shoulder_dist.append(shoulder_dist)
                        calibration_hips_visibility.append((left_hip.visibility + right_hip.visibility) / 2)
                        
                        progress = int((len(calibration_y_shoulders) / CALIBRATION_FRAMES) * 100)
                        ui_renderer.draw_calibration_popup(frame, progress)
                        
                        if len(calibration_y_shoulders) >= CALIBRATION_FRAMES:
                            y_calibrated = np.mean(calibration_y_shoulders)
                            x_calibrated = np.mean(calibration_x_torso)
                            shoulder_dist_calibrated = np.mean(calibration_shoulder_dist)
                            
                            # Decide se richiedere i fianchi nel gameplay
                            mean_hips_vis = np.mean(calibration_hips_visibility)
                            use_hips_detection = mean_hips_vis > 0.5
                            
                            calibrated = True
                            print(f"Calibrazione completata!")
                            print(f" - Y spalle base: {y_calibrated:.3f}")
                            print(f" - X busto base: {x_calibrated:.3f}")
                            print(f" - Distanza spalle base: {shoulder_dist_calibrated:.3f}")
                            print(f" - Controllo fianchi attivo: {use_hips_detection} (Visibilita' media: {mean_hips_vis:.2f})")
                            
                            # Esegui il click di avvio al centro del browser SOLO dopo il completamento della calibrazione
                            if AUTO_LAUNCH_GAME:
                                print("[TRACKER] Calibrazione ultimata! Invio click di avvio sul tasto START...")
                                pyautogui.click(target_x, target_y)
                                pyautogui.click(target_x, target_y)
                                time.sleep(1.5)
                                pyautogui.click(target_x, target_y)


                else:
                    # Se l'inquadratura non e' idonea, sospendi la calibrazione, resetta il timer e mostra l'errore
                    countdown_start_time = None
                    progress = int((len(calibration_y_shoulders) / CALIBRATION_FRAMES) * 100)
                    ui_renderer.draw_calibration_popup(frame, progress, warning=warning_calib)
            
            # --- LOGICA DI RILEVAMENTO DEI MOVIMENTI ---
            else:
                # Controlla l'inquadratura corrente
                is_framed, warning_msg = ui_renderer.check_framing(landmarks, use_hips=use_hips_detection)
                
                if not is_framed:
                    # Forza lo stato IDLE e mostra l'avviso
                    raw_state = "CORSA / IDLE"
                    current_state = "CORSA / IDLE"
                    state_frame_count = 0
                    ui_renderer.draw_hud(frame, current_state)
                    ui_renderer.draw_warning_overlay(frame, f"INQUADRATURA COMPROMESSA: {warning_msg}")
                else:
                    # Rilevamento Gesto Applauso (HOVERBOARD) - multi-keypoint per massima precisione e sensibilita'
                    left_wrist = landmarks[PoseLandmark.LEFT_WRIST]
                    right_wrist = landmarks[PoseLandmark.RIGHT_WRIST]
                    left_index = landmarks[PoseLandmark.LEFT_INDEX]
                    right_index = landmarks[PoseLandmark.RIGHT_INDEX]
                    left_pinky = landmarks[PoseLandmark.LEFT_PINKY]
                    right_pinky = landmarks[PoseLandmark.RIGHT_PINKY]
                    left_thumb = landmarks[PoseLandmark.LEFT_THUMB]
                    right_thumb = landmarks[PoseLandmark.RIGHT_THUMB]
                    
                    # Definiamo coppie di punti corrispondenti delle mani
                    hand_pairs = [
                        (left_wrist, right_wrist),
                        (left_index, right_index),
                        (left_pinky, right_pinky),
                        (left_thumb, right_thumb)
                    ]
                    
                    distances = []
                    valid_pairs = []
                    
                    for l_pt, r_pt in hand_pairs:
                        if l_pt.visibility > 0.5 and r_pt.visibility > 0.5:
                            dist = np.linalg.norm(np.array([l_pt.x - r_pt.x, l_pt.y - r_pt.y]))
                            distances.append(dist)
                            valid_pairs.append((l_pt, r_pt))
                    
                    if distances:
                        # Troviamo la distanza minima tra tutti i keypoint delle mani per maggiore sensibilita'
                        min_dist = min(distances)
                        min_idx = np.argmin(distances)
                        closest_l, closest_r = valid_pairs[min_idx]
                        
                        # Soglia per mani vicine aumentata a 0.45 * distanza spalle per facilitare il rilevamento senza falsi positivi
                        max_hand_dist = 0.45 * shoulder_dist_calibrated
                        hands_joined = min_dist < max_hand_dist
                        
                        # Visualizzazione dei punti di tracciamento
                        cv2.circle(frame, (int(left_wrist.x * width), int(left_wrist.y * height)), 6, (255, 0, 255), -1)
                        cv2.circle(frame, (int(right_wrist.x * width), int(right_wrist.y * height)), 6, (255, 0, 255), -1)
                        
                        if hands_joined:
                            # Centroide delle due mani nel punto piu' vicino
                            x_hands = (closest_l.x + closest_r.x) / 2
                            y_hands = (closest_l.y + closest_r.y) / 2
                            cv2.circle(frame, (int(x_hands * width), int(y_hands * height)), 18, (255, 0, 255), 2)
                    else:
                        hands_joined = False
 
                    # Rilevamento trigger sul fronte di salita (edge trigger)
                    if hands_joined and not hands_were_joined:
                        hoverboard_frames_left = 24  # Circa 0.8 secondi di durata
                        print("[TRACKER] GESTO RILEVATO: Applauso! Attivazione HOVERBOARD")
                        simulator.simulate(current_state, "HOVERBOARD")
                        
                    hands_were_joined = hands_joined
 
                    # Gestione dello stato prioritario HOVERBOARD o dei movimenti standard
                    if hoverboard_frames_left > 0:
                        hoverboard_frames_left -= 1
                        current_state = "HOVERBOARD"
                        state_frame_count = 0
                        ui_renderer.draw_hud(frame, current_state)
                    else:
                        # Calcolo dei limiti di tolleranza scalati dinamicamente rispetto alla distanza spalle
                        scale = shoulder_dist / shoulder_dist_calibrated
                        dynamic_jump_threshold = JUMP_THRESHOLD * scale
                        dynamic_crouch_threshold = CROUCH_THRESHOLD * scale
                        dynamic_lateral_threshold = LATERAL_THRESHOLD * scale
 
                        # Disegna linee guida di riferimento (HUD hi-tech a schermo)
                        y_base_px = int(y_calibrated * height)
                        x_left_px = int((x_calibrated - dynamic_lateral_threshold) * width)
                        x_right_px = int((x_calibrated + dynamic_lateral_threshold) * width)
 
                        # Linea orizzontale altezza spalle (Calibrata)
                        cv2.line(frame, (0, y_base_px), (width, y_base_px), (0, 255, 255), 1)
                        
                        # Linee di salto/capriola per feedback visivo
                        y_jump_px = int((y_calibrated - dynamic_jump_threshold) * height)
                        y_crouch_px = int((y_calibrated + dynamic_crouch_threshold) * height)
                        cv2.line(frame, (0, y_jump_px), (width, y_jump_px), (57, 255, 20), 1, cv2.LINE_4)
                        cv2.line(frame, (0, y_crouch_px), (width, y_crouch_px), (0, 242, 254), 1, cv2.LINE_4)
 
                        # Linee verticali per i limiti laterali
                        cv2.line(frame, (x_left_px, 0), (x_left_px, height), (255, 255, 0), 1)
                        cv2.line(frame, (x_right_px, 0), (x_right_px, height), (255, 255, 0), 1)
 
                        # Controllo Altezza (Salto / Capriola) rispetto alla calibrazione
                        if y_shoulders < y_calibrated - dynamic_jump_threshold:
                            raw_state = "SALTO"
                        elif y_shoulders > y_calibrated + dynamic_crouch_threshold:
                            raw_state = "CAPRIOLA"
                        
                        # Controllo Laterale (Sinistra / Destra)
                        else:
                            if x_torso < x_calibrated - dynamic_lateral_threshold:
                                raw_state = "SPOSTAMENTO SINISTRA"
                            elif x_torso > x_calibrated + dynamic_lateral_threshold:
                                raw_state = "SPOSTAMENTO DESTRA"
                            else:
                                # Se l'utente era a sinistra o a destra, il ritorno al centro viene
                                # identificato come uno stato di transizione "SPOSTAMENTO CENTRO"
                                if current_state in ["SPOSTAMENTO SINISTRA", "SPOSTAMENTO DESTRA"]:
                                    raw_state = "SPOSTAMENTO CENTRO"
                                else:
                                    raw_state = "CORSA / IDLE"
 
                        # Se veniamo dallo stato HOVERBOARD, ripristiniamo immediatamente lo stato reale senza attendere il debounce
                        if current_state == "HOVERBOARD":
                            print(f"[TRACKER] Cambio Stato: HOVERBOARD -> {raw_state}")
                            simulator.simulate(current_state, raw_state)
                            current_state = raw_state
                            state_frame_count = 0
                        else:
                            # Debounce normale
                            if raw_state != current_state:
                                if state_frame_count >= MIN_STATE_FRAMES:
                                    print(f"[TRACKER] Cambio Stato: {current_state} -> {raw_state}")
                                    simulator.simulate(current_state, raw_state)
                                    current_state = raw_state
                                    state_frame_count = 0
                                else:
                                    state_frame_count += 1
                            else:
                                state_frame_count += 1
 
                        # Aggiornamento dinamico (EMA) dei parametri di calibrazione (attivo solo in CORSA / IDLE stabile)
                        if current_state == "CORSA / IDLE":
                            alpha = 0.005
                            y_calibrated = alpha * y_shoulders + (1.0 - alpha) * y_calibrated
                            x_calibrated = alpha * x_torso + (1.0 - alpha) * x_calibrated
                            shoulder_dist_calibrated = alpha * shoulder_dist + (1.0 - alpha) * shoulder_dist_calibrated
 
                        # Disegna l'HUD con lo stato corrente calibrato
                        ui_renderer.draw_hud(frame, current_state)
        else:
            # Se la posa non e' rilevata
            if not calibrated:
                countdown_start_time = None
                ui_renderer.draw_calibration_popup(frame, 0, warning="Nessun utente rilevato. Posizionati davanti alla fotocamera")
            else:
                # Ripristina lo stato IDLE in assenza di rilevamento
                current_state = "CORSA / IDLE"
                state_frame_count = 0
                ui_renderer.draw_hud(frame, "NESSUN UTENTE RILEVATO")
 
        # Mostra il frame
        cv2.imshow("Subway Surfers Motion Tracker", frame)
 
        # Chiusura con tasto ESC (ASCII 27)
        key = cv2.waitKey(1) & 0xFF
        if key == 27:
            break
 
    # Rilascio risorse
    cap.release()
    cv2.destroyAllWindows()
    pose.close()
    print("Programma terminato pulitamente.")
 
if __name__ == "__main__":
    main()
