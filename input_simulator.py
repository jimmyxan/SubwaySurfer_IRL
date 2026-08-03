import time
import pyautogui

class InputSimulator:
    """
    Simulator for keyboard inputs in Subway Surfers using PyAutoGUI.
    Encapsulates player lane state and action cooldowns.
    """
    # Cooldown constants in seconds
    COOLDOWN_JUMP = 0.5
    COOLDOWN_CROUCH = 0.5
    COOLDOWN_HOVERBOARD = 3.0

    def __init__(self, failsafe=True, pause=0):
        pyautogui.FAILSAFE = failsafe
        pyautogui.PAUSE = pause
        
        self.corsia_attuale = "CENTRO"  # "SINISTRA", "CENTRO", "DESTRA"
        self.last_jump_time = 0.0
        self.last_crouch_time = 0.0
        self.last_hoverboard_time = 0.0

    def simulate(self, prev_state, next_state):
        """
        Sends simulated keyboard presses based on state transitions,
        taking cooldowns and current lane into account.
        """
        now = time.time()

        # 1. Vertical movements and special actions
        if next_state == "SALTO":
            if now - self.last_jump_time > self.COOLDOWN_JUMP:
                pyautogui.press('up')
                self.last_jump_time = now
                print("[KEYBOARD] Premuto UP (Salto)")
        elif next_state == "CAPRIOLA":
            if now - self.last_crouch_time > self.COOLDOWN_CROUCH:
                pyautogui.press('down')
                self.last_crouch_time = now
                print("[KEYBOARD] Premuto DOWN (Capriola)")
        elif next_state == "HOVERBOARD":
            if now - self.last_hoverboard_time > self.COOLDOWN_HOVERBOARD:
                pyautogui.press('space')
                self.last_hoverboard_time = now
                print("[KEYBOARD] Premuto SPACE (Hoverboard)")

        # 2. Lane changes detection (lateral)
        elif next_state == "SPOSTAMENTO SINISTRA":
            if self.corsia_attuale == "CENTRO":
                pyautogui.press('left')
                self.corsia_attuale = "SINISTRA"
                print("[KEYBOARD] Premuto LEFT (Centro -> Sinistra)")
            elif self.corsia_attuale == "DESTRA":
                pyautogui.press('left')
                pyautogui.press('left')
                self.corsia_attuale = "SINISTRA"
                print("[KEYBOARD] Premuto LEFT x2 (Destra -> Sinistra)")
        elif next_state == "SPOSTAMENTO DESTRA":
            if self.corsia_attuale == "CENTRO":
                pyautogui.press('right')
                self.corsia_attuale = "DESTRA"
                print("[KEYBOARD] Premuto RIGHT (Centro -> Destra)")
            elif self.corsia_attuale == "SINISTRA":
                pyautogui.press('right')
                pyautogui.press('right')
                self.corsia_attuale = "DESTRA"
                print("[KEYBOARD] Premuto RIGHT x2 (Sinistra -> Destra)")
        elif next_state == "SPOSTAMENTO CENTRO":
            if self.corsia_attuale == "DESTRA":
                pyautogui.press('left')
                self.corsia_attuale = "CENTRO"
                print("[KEYBOARD] Premuto LEFT (Destra -> Centro)")
            elif self.corsia_attuale == "SINISTRA":
                pyautogui.press('right')
                self.corsia_attuale = "CENTRO"
                print("[KEYBOARD] Premuto RIGHT (Sinistra -> Centro)")
