import pytest
import numpy as np
import cv2
import mediapipe as mp
from unittest.mock import MagicMock, patch

import ui_renderer
from input_simulator import InputSimulator

class DummyLandmark:
    def __init__(self, x, y, visibility=1.0):
        self.x = x
        self.y = y
        self.visibility = visibility

def get_mock_landmarks(shoulder_vis=1.0, shoulder_y=0.5, shoulder_left_x=0.4, shoulder_right_x=0.6,
                       hip_vis=1.0, hip_y=0.8, hip_left_x=0.4, hip_right_x=0.6):
    landmarks = {}
    landmarks[ui_renderer.PoseLandmark.LEFT_SHOULDER] = DummyLandmark(shoulder_left_x, shoulder_y, shoulder_vis)
    landmarks[ui_renderer.PoseLandmark.RIGHT_SHOULDER] = DummyLandmark(shoulder_right_x, shoulder_y, shoulder_vis)
    landmarks[ui_renderer.PoseLandmark.LEFT_HIP] = DummyLandmark(hip_left_x, hip_y, hip_vis)
    landmarks[ui_renderer.PoseLandmark.RIGHT_HIP] = DummyLandmark(hip_right_x, hip_y, hip_vis)
    return landmarks

# --- TESTS FOR UI_RENDERER ---

def test_check_framing_valid():
    landmarks = get_mock_landmarks()
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=False)
    assert is_framed is True
    assert msg == "OK"

def test_check_framing_low_shoulder_visibility():
    landmarks = get_mock_landmarks(shoulder_vis=0.4)
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=False)
    assert is_framed is False
    assert "Spalle non visibili" in msg

def test_check_framing_shoulder_clipping():
    landmarks = get_mock_landmarks(shoulder_y=0.02)  # too close to the top edge (margin = 0.05)
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=False)
    assert is_framed is False
    assert "Riposizionati al centro" in msg

def test_check_framing_use_hips_valid():
    landmarks = get_mock_landmarks(hip_vis=0.8, hip_y=0.90)
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=True)
    assert is_framed is True
    assert msg == "OK"

def test_check_framing_use_hips_low_visibility():
    landmarks = get_mock_landmarks(hip_vis=0.3)
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=True)
    assert is_framed is False
    assert "Fianchi non visibili" in msg

def test_check_framing_use_hips_clipping():
    landmarks = get_mock_landmarks(hip_y=0.99)  # too close to bottom (> 0.98)
    is_framed, msg = ui_renderer.check_framing(landmarks, use_hips=True)
    assert is_framed is False
    assert "Fianchi tagliati" in msg

def test_draw_calibration_popup():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ui_renderer.draw_calibration_popup(frame, progress=50)
    assert not np.all(frame == 0)

def test_draw_calibration_popup_warning():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ui_renderer.draw_calibration_popup(frame, progress=20, warning="Stay centered")
    assert not np.all(frame == 0)

def test_draw_countdown_popup():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ui_renderer.draw_countdown_popup(frame, seconds_left=3)
    assert not np.all(frame == 0)

def test_draw_warning_overlay():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    ui_renderer.draw_warning_overlay(frame, message="Warning text")
    assert not np.all(frame == 0)

def test_draw_hud():
    states = ["CORSA / IDLE", "SPOSTAMENTO SINISTRA", "NESSUN UTENTE RILEVATO", "HOVERBOARD", "SALTO"]
    for state in states:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ui_renderer.draw_hud(frame, state)
        assert not np.all(frame == 0)


# --- TESTS FOR INPUT_SIMULATOR ---

@patch('input_simulator.pyautogui.press')
def test_input_simulator_vertical_actions(mock_press):
    sim = InputSimulator()
    
    # SALTO triggers 'up'
    sim.simulate("CORSA / IDLE", "SALTO")
    mock_press.assert_called_with('up')
    mock_press.reset_mock()
    
    # CAPRIOLA triggers 'down'
    sim.simulate("CORSA / IDLE", "CAPRIOLA")
    mock_press.assert_called_with('down')
    mock_press.reset_mock()
    
    # HOVERBOARD triggers 'space'
    sim.simulate("CORSA / IDLE", "HOVERBOARD")
    mock_press.assert_called_with('space')

@patch('input_simulator.pyautogui.press')
def test_input_simulator_lane_changes(mock_press):
    sim = InputSimulator()
    assert sim.corsia_attuale == "CENTRO"
    
    # SPOSTAMENTO SINISTRA from CENTRO -> press 'left' once
    sim.simulate("CORSA / IDLE", "SPOSTAMENTO SINISTRA")
    mock_press.assert_called_once_with('left')
    assert sim.corsia_attuale == "SINISTRA"
    mock_press.reset_mock()
    
    # SPOSTAMENTO DESTRA from SINISTRA -> press 'right' twice
    sim.simulate("SPOSTAMENTO SINISTRA", "SPOSTAMENTO DESTRA")
    assert mock_press.call_count == 2
    mock_press.assert_any_call('right')
    assert sim.corsia_attuale == "DESTRA"
    mock_press.reset_mock()
    
    # SPOSTAMENTO CENTRO from DESTRA -> press 'left' once
    sim.simulate("SPOSTAMENTO DESTRA", "SPOSTAMENTO CENTRO")
    mock_press.assert_called_once_with('left')
    assert sim.corsia_attuale == "CENTRO"
    mock_press.reset_mock()
    
    # Move to SINISTRA
    sim.simulate("SPOSTAMENTO CENTRO", "SPOSTAMENTO SINISTRA")
    mock_press.reset_mock()
    
    # SPOSTAMENTO CENTRO from SINISTRA -> press 'right' once
    sim.simulate("SPOSTAMENTO SINISTRA", "SPOSTAMENTO CENTRO")
    mock_press.assert_called_once_with('right')
    assert sim.corsia_attuale == "CENTRO"

@patch('input_simulator.pyautogui.press')
@patch('time.time')
def test_input_simulator_cooldowns(mock_time, mock_press):
    sim = InputSimulator()
    
    # Time t = 100.0 (jump works)
    mock_time.return_value = 100.0
    sim.simulate("CORSA / IDLE", "SALTO")
    mock_press.assert_called_once_with('up')
    mock_press.reset_mock()
    
    # Time t = 100.2 (cooldown of 0.5 active -> should not press)
    mock_time.return_value = 100.2
    sim.simulate("CORSA / IDLE", "SALTO")
    mock_press.assert_not_called()
    
    # Time t = 100.6 (cooldown passed -> should press)
    mock_time.return_value = 100.6
    sim.simulate("CORSA / IDLE", "SALTO")
    mock_press.assert_called_once_with('up')


# --- TESTS FOR BROWSER & WINDOW SETUP ---

import motion_tracker

@patch('motion_tracker.pyautogui.size', return_value=(1920, 1080))
@patch('motion_tracker.pyautogui.moveTo')
@patch('motion_tracker.open_private_browser', return_value="Google Chrome (Incognito)")
@patch('motion_tracker.subprocess.run')
@patch('motion_tracker.time.sleep')
def test_setup_browser_and_windows_darwin(mock_sleep, mock_subproc, mock_open_priv, mock_moveto, mock_size):
    with patch('motion_tracker.sys.platform', 'darwin'), patch('motion_tracker.AUTO_LAUNCH_GAME', True):
        screen_w, screen_h, browser_w, opencv_w, target_x, target_y = motion_tracker.setup_browser_and_windows()
        assert screen_w == 1920
        assert screen_h == 1080
        assert browser_w == 1440
        assert opencv_w == 480
        assert target_x == 720
        assert target_y == 669
        mock_open_priv.assert_called_once_with(motion_tracker.HTML_FILE_PATH)
        mock_moveto.assert_called_once_with(720, 669)


@patch('motion_tracker.subprocess.run')
def test_open_private_browser_safari(mock_subproc):
    mock_subproc.return_value.returncode = 0
    res = motion_tracker.open_private_browser("test.html")
    assert res == "Safari (Finestra Privata)"
    assert "tell application \"Safari\"" in mock_subproc.call_args[0][0][2]


@pytest.mark.parametrize("screen_res", [
    (1920, 1080),
    (2560, 1440),
    (1440, 900),
    (1366, 768),
    (1280, 800),
    (3840, 2160),
])
def test_dynamic_window_sizing_visibility(screen_res):
    """
    Verifica che il ridimensionamento dinamico garantisca la completa visibilita'
    di entrambe le finestre senza sovrapposizioni ne' tagli dello schermo,
    dando priorita' al browser (75%) e adattando l'anteprima video (restante 25%).
    """
    sw, sh = screen_res
    with patch('motion_tracker.pyautogui.size', return_value=(sw, sh)), \
         patch('motion_tracker.AUTO_LAUNCH_GAME', False):
        screen_w, screen_h, browser_w, opencv_w, target_x, target_y = motion_tracker.setup_browser_and_windows()
        
        # 1. Dimensioni totali rispettano esattamente la larghezza dello schermo
        assert browser_w + opencv_w == screen_w
        # 2. Browser ha la priorita' (75% della larghezza)
        assert browser_w == int(screen_w * 0.75)
        # 3. Anteprima video occupa il rimanente spazio (completamente visibile a destra)
        assert opencv_w == screen_w - browser_w
        # 4. Target X e' centrato orizzontalmente sul browser
        assert target_x == browser_w // 2
        # 5. Target Y e' posizionato al 62% dell'altezza (12% sotto il centro)
        assert target_y == int(screen_h * 0.62)


@patch('motion_tracker.mp_pose', None)
def test_main_handles_none_pose(capsys):
    """
    Verifica che main() gestisca correttamente l'assenza di MediaPipe Pose,
    stampando un messaggio di errore chiaro ed uscendo senza sollevare eccezioni.
    """
    motion_tracker.main()
    captured = capsys.readouterr()
    assert "[ERRORE CRITICO]" in captured.out
    assert "MediaPipe Pose" in captured.out


@patch('motion_tracker.pyautogui.size', return_value=(1920, 1080))
@patch('motion_tracker.pyautogui.moveTo')
@patch('motion_tracker.open_private_browser', return_value="Google Chrome (Incognito)")
@patch('motion_tracker.time.sleep')
def test_setup_browser_and_windows_win32(mock_sleep, mock_open_priv, mock_moveto, mock_size):
    with patch('motion_tracker.sys.platform', 'win32'), patch('motion_tracker.AUTO_LAUNCH_GAME', True):
        screen_w, screen_h, browser_w, opencv_w, target_x, target_y = motion_tracker.setup_browser_and_windows()
        assert screen_w == 1920
        assert screen_h == 1080
        assert browser_w == 1440
        assert opencv_w == 480
        mock_open_priv.assert_called_once_with(motion_tracker.HTML_FILE_PATH)
        mock_moveto.assert_called_once_with(720, 669)


@patch('motion_tracker.pyautogui.size', return_value=(1920, 1080))
@patch('motion_tracker.pyautogui.moveTo')
@patch('motion_tracker.open_private_browser', return_value="Google Chrome (Incognito)")
@patch('motion_tracker.subprocess.run')
@patch('motion_tracker.time.sleep')
def test_setup_browser_and_windows_linux(mock_sleep, mock_subproc, mock_open_priv, mock_moveto, mock_size):
    mock_subproc.return_value.returncode = 0
    with patch('motion_tracker.sys.platform', 'linux'), patch('motion_tracker.AUTO_LAUNCH_GAME', True):
        screen_w, screen_h, browser_w, opencv_w, target_x, target_y = motion_tracker.setup_browser_and_windows()
        assert screen_w == 1920
        assert screen_h == 1080
        assert browser_w == 1440
        assert opencv_w == 480
        mock_open_priv.assert_called_once_with(motion_tracker.HTML_FILE_PATH)
        mock_moveto.assert_called_once_with(720, 669)
        mock_subproc.assert_called_with(["wmctrl", "-r", ":ACTIVE:", "-e", "0,0,0,1440,1080"], capture_output=True)


@patch('motion_tracker.subprocess.run')
def test_open_private_browser_win32_chrome(mock_subproc):
    mock_subproc.return_value.returncode = 0
    with patch('motion_tracker.sys.platform', 'win32'):
        res = motion_tracker.open_private_browser("index.html")
        assert res == "Google Chrome (Incognito)"
        mock_subproc.assert_called_once_with(["cmd", "/c", "start", "", "chrome", "--incognito", "file://index.html"], capture_output=True)


@patch('motion_tracker.subprocess.run')
def test_open_private_browser_win32_edge(mock_subproc):
    # First call (chrome) fails, second call (msedge) succeeds
    mock_res_fail = MagicMock(returncode=1)
    mock_res_success = MagicMock(returncode=0)
    mock_subproc.side_effect = [mock_res_fail, mock_res_success]
    with patch('motion_tracker.sys.platform', 'win32'):
        res = motion_tracker.open_private_browser("index.html")
        assert res == "Microsoft Edge (InPrivate)"
        assert mock_subproc.call_count == 2


@patch('motion_tracker.subprocess.run')
def test_open_private_browser_linux_chrome(mock_subproc):
    mock_subproc.return_value.returncode = 0
    with patch('motion_tracker.sys.platform', 'linux'):
        res = motion_tracker.open_private_browser("index.html")
        assert res == "Google Chrome (Incognito)"
        mock_subproc.assert_called_once_with(["google-chrome", "--incognito", "file://index.html"], capture_output=True)


@patch('motion_tracker.webbrowser.open')
@patch('motion_tracker.subprocess.run')
def test_open_private_browser_linux_fallback(mock_subproc, mock_webbrowser):
    mock_subproc.return_value.returncode = 1
    with patch('motion_tracker.sys.platform', 'linux'):
        res = motion_tracker.open_private_browser("index.html")
        assert res == "Browser Predefinito"
        mock_webbrowser.assert_called_once_with("file://index.html")








