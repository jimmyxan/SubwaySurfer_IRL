import cv2
import numpy as np

try:
    import mediapipe.python.solutions.pose as mp_pose
    PoseLandmark = mp_pose.PoseLandmark
except Exception:
    try:
        from mediapipe.solutions import pose as mp_pose
        PoseLandmark = mp_pose.PoseLandmark
    except Exception:
        class PoseLandmark:
            LEFT_SHOULDER = 11
            RIGHT_SHOULDER = 12
            LEFT_HIP = 23
            RIGHT_HIP = 24
            LEFT_WRIST = 15
            RIGHT_WRIST = 16
            LEFT_INDEX = 19
            RIGHT_INDEX = 20
            LEFT_PINKY = 17
            RIGHT_PINKY = 18
            LEFT_THUMB = 21
            RIGHT_THUMB = 22

def check_framing(landmarks, use_hips=False):
    """
    Verifica se l'inquadratura dell'utente e' corretta.
    Ritorna (is_framed, warning_message)
    """
    # 1. Recupero i punti chiave delle spalle
    left_shoulder = landmarks[PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks[PoseLandmark.RIGHT_SHOULDER]
    
    # Verifica visibilita' delle spalle
    if left_shoulder.visibility < 0.5 or right_shoulder.visibility < 0.5:
        return False, "Spalle non visibili o parziali"
        
    # Verifica che le spalle non stiano uscendo dai bordi dell'inquadratura (clipping)
    margin = 0.05
    if (left_shoulder.y < margin or left_shoulder.y > 1.0 - margin or
        right_shoulder.y < margin or right_shoulder.y > 1.0 - margin or
        left_shoulder.x < margin or left_shoulder.x > 1.0 - margin or
        right_shoulder.x < margin or right_shoulder.x > 1.0 - margin):
        return False, "Riposizionati al centro dell'inquadratura"
        
    # 2. Se e' richiesto il controllo dei fianchi (modalita' a corpo intero)
    if use_hips:
        left_hip = landmarks[PoseLandmark.LEFT_HIP]
        right_hip = landmarks[PoseLandmark.RIGHT_HIP]
        
        # Verifica visibilita' dei fianchi
        if left_hip.visibility < 0.5 or right_hip.visibility < 0.5:
            return False, "Fianchi non visibili. Allontanati"
            
        # Verifica che i fianchi non stiano uscendo dal bordo inferiore
        if left_hip.y > 0.98 or right_hip.y > 0.98:
            return False, "Fianchi tagliati. Allontanati dalla fotocamera"
            
    return True, "OK"

def draw_calibration_popup(frame, progress, warning=None):
    """
    Disegna un pop-up di calibrazione moderno, centrato e semitrasparente.
    """
    height, width, _ = frame.shape
    
    # Dimensioni del pop-up
    popup_w = 520
    popup_h = 220
    x1 = (width - popup_w) // 2
    y1 = (height - popup_h) // 2
    x2 = x1 + popup_w
    y2 = y1 + popup_h

    # Colori (BGR)
    dark_gray = (15, 15, 15)
    neon_yellow = (0, 242, 254)  # Colore per calibrazione
    neon_cyan = (255, 255, 0)
    neon_red = (0, 0, 255)
    white = (255, 255, 255)
    
    # Sfondo sfocato/semitrasparente
    roi = frame[y1:y2, x1:x2]
    overlay = np.full(roi.shape, dark_gray, dtype=np.uint8)
    blended = cv2.addWeighted(overlay, 0.85, roi, 0.15, 0)
    frame[y1:y2, x1:x2] = blended
    
    # Bordo del pop-up
    border_color = neon_red if warning else neon_yellow
    cv2.rectangle(frame, (x1, y1), (x2, y2), border_color, 3)
    
    # Titolo
    title = "CALIBRAZIONE IN CORSO"
    title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_DUPLEX, 0.8, 2)[0]
    cv2.putText(frame, title, (width // 2 - title_size[0] // 2, y1 + 40),
                cv2.FONT_HERSHEY_DUPLEX, 0.8, neon_yellow, 2, cv2.LINE_AA)
    
    # Messaggio di avviso o istruzioni standard
    if warning:
        msg1 = "REGOLA L'INQUADRATURA:"
        msg2 = warning
        color1 = neon_red
        color2 = white
    else:
        msg1 = "Rimani dritto e FERMO al centro"
        msg2 = "fino al completamento della calibrazione."
        color1 = white
        color2 = white
        
    size1 = cv2.getTextSize(msg1, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
    size2 = cv2.getTextSize(msg2, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
    cv2.putText(frame, msg1, (width // 2 - size1[0] // 2, y1 + 80),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, color1, 1, cv2.LINE_AA)
    cv2.putText(frame, msg2, (width // 2 - size2[0] // 2, y1 + 105),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, color2, 1, cv2.LINE_AA)
    
    # Barra di avanzamento
    bar_w = 400
    bar_h = 16
    bx1 = (width - bar_w) // 2
    by1 = y1 + 140
    bx2 = bx1 + bar_w
    by2 = by1 + bar_h
    
    # Sfondo barra
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (40, 40, 40), -1)
    # Riempimento barra
    fill_w = int(bar_w * (progress / 100))
    if fill_w > 0:
        cv2.rectangle(frame, (bx1, by1), (bx1 + fill_w, by2), neon_cyan, -1)
    
    # Percentuale o messaggio di stato
    status_text = f"Progresso: {progress}%" if not warning else "Calibrazione Sospesa"
    status_color = neon_cyan if not warning else neon_red
    status_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
    cv2.putText(frame, status_text, (width // 2 - status_size[0] // 2, by2 + 25),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, status_color, 1, cv2.LINE_AA)

def draw_countdown_popup(frame, seconds_left):
    """
    Disegna un pop-up di conto alla rovescia moderno ed elegante prima della calibrazione.
    """
    height, width, _ = frame.shape
    
    # Dimensioni del pop-up
    popup_w = 480
    popup_h = 170
    x1 = (width - popup_w) // 2
    y1 = (height - popup_h) // 2
    x2 = x1 + popup_w
    y2 = y1 + popup_h

    # Colori (BGR)
    dark_gray = (15, 15, 15)
    neon_cyan = (255, 255, 0)
    white = (255, 255, 255)
    
    # Sfondo semitrasparente
    roi = frame[y1:y2, x1:x2]
    overlay = np.full(roi.shape, dark_gray, dtype=np.uint8)
    blended = cv2.addWeighted(overlay, 0.85, roi, 0.15, 0)
    frame[y1:y2, x1:x2] = blended
    
    # Bordo
    cv2.rectangle(frame, (x1, y1), (x2, y2), neon_cyan, 3)
    
    # Testo
    title = "PREPARATI AL CENTRO"
    msg = "La calibrazione iniziera' tra:"
    
    title_size = cv2.getTextSize(title, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
    msg_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
    
    cv2.putText(frame, title, (width // 2 - title_size[0] // 2, y1 + 35),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, neon_cyan, 2, cv2.LINE_AA)
    cv2.putText(frame, msg, (width // 2 - msg_size[0] // 2, y1 + 65),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, white, 1, cv2.LINE_AA)
    
    # Contatore gigante
    count_text = str(seconds_left)
    count_size = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_DUPLEX, 1.8, 4)[0]
    cv2.putText(frame, count_text, (width // 2 - count_size[0] // 2, y1 + 140),
                cv2.FONT_HERSHEY_DUPLEX, 1.8, neon_cyan, 4, cv2.LINE_AA)

def draw_warning_overlay(frame, message):
    """
    Disegna un avviso visivo semitrasparente sullo schermo quando l'inquadratura non e' corretta.
    """
    height, width, _ = frame.shape
    
    # Disegna una fascia rossa semitrasparente in basso
    overlay_h = 50
    x1, y1 = 0, height - overlay_h
    x2, y2 = width, height
    
    roi = frame[y1:y2, x1:x2]
    overlay = np.zeros(roi.shape, dtype=np.uint8)
    overlay[:, :] = (0, 0, 180) # Rosso scuro
    
    blended = cv2.addWeighted(overlay, 0.6, roi, 0.4, 0)
    frame[y1:y2, x1:x2] = blended
    
    # Bordo superiore della fascia
    cv2.line(frame, (x1, y1), (x2, y1), (0, 0, 255), 2)
    
    # Scrittura del messaggio
    size = cv2.getTextSize(message, cv2.FONT_HERSHEY_DUPLEX, 0.5, 1)[0]
    cv2.putText(frame, message, (width // 2 - size[0] // 2, y1 + 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

def draw_hud(frame, state):
    """
    Disegna un HUD (Heads-Up Display) moderno e semitrasparente nella parte superiore centrale.
    """
    height, width, _ = frame.shape
    
    # Dimensioni dell'HUD
    hud_width = 500
    hud_height = 70
    x1 = (width - hud_width) // 2
    y1 = 15
    x2 = x1 + hud_width
    y2 = y1 + hud_height

    # Colori (BGR)
    dark_gray = (20, 20, 20)
    neon_green = (57, 255, 20)
    neon_yellow = (0, 242, 254)
    neon_cyan = (255, 255, 0)
    
    # 1. Disegna sfondo semitrasparente
    roi = frame[y1:y2, x1:x2]
    overlay = np.full(roi.shape, dark_gray, dtype=np.uint8)
    blended = cv2.addWeighted(overlay, 0.7, roi, 0.3, 0)
    frame[y1:y2, x1:x2] = blended
    
    # Bordo dell'HUD
    cv2.rectangle(frame, (x1, y1), (x2, y2), neon_cyan, 2)

    # Mostra lo stato corrente o avvisi
    text = f"STATO: {state}"
    
    # Scegli il colore in base allo stato
    if state == "CORSA / IDLE":
        color = neon_green
    elif state in ["SPOSTAMENTO SINISTRA", "SPOSTAMENTO DESTRA", "SPOSTAMENTO CENTRO"]:
        color = neon_cyan
    elif state == "NESSUN UTENTE RILEVATO":
        color = (0, 0, 255) # Rosso
    elif state == "HOVERBOARD":
        color = (255, 0, 255) # Rosa/Magenta neon
    else: # SALTO o CAPRIOLA
        color = neon_yellow

    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
    cv2.putText(frame, text, (width // 2 - text_size[0] // 2, y1 + 45),
                cv2.FONT_HERSHEY_DUPLEX, 0.9, color, 2, cv2.LINE_AA)
