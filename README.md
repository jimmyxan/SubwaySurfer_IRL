# SubwaySurfer_IRL
# 🏃‍♂️ Subway Surfers Motion Tracker

[🇬🇧 English](#-english) | [🇮🇹 Italiano](#-italiano)

---

## 🇬🇧 English

An advanced **Computer Vision & AI** application in Python that allows you to play **Subway Surfers** by controlling your character directly with real-time body movements and hand gestures captured via your webcam.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/OpenCV-4.x-green?style=for-the-badge&logo=opencv" alt="OpenCV">
  <img src="https://img.shields.io/badge/MediaPipe-Pose-orange?style=for-the-badge" alt="MediaPipe">
  <br>
  <img src="https://img.shields.io/badge/macOS-Supported-brightgreen?style=for-the-badge&logo=apple" alt="macOS">
  <img src="https://img.shields.io/badge/Windows-Supported-blue?style=for-the-badge&logo=windows" alt="Windows">
  <img src="https://img.shields.io/badge/Linux-Supported-yellow?style=for-the-badge&logo=linux" alt="Linux">
</p>

---

### ✨ Key Features

- 🏃 **Real-Time Body Motion Tracking**:
  - **Jump ($\uparrow$)**: Raising upper body/shoulders.
  - **Roll / Crouch ($\downarrow$)**: Lowering upper body.
  - **Move Left ($\leftarrow$) / Right ($\rightarrow$)**: Lateral torso tilt or step.
  - 🛹 **Clap / Hand Join Gesture for Hoverboard ($\text{Space}$)**: Multi-keypoint detection (wrists, index fingers, pinkies, thumbs) of joined hands / clapping to trigger the Hoverboard instantly.
  
- 🎯 **Automatic Calibration with HUD**:
  - 3-second countdown pop-up window to prepare yourself in the frame center.
  - Dynamic base calibration of shoulder and torso resting positions (120 frames).
  - Adaptive hip visibility detection and framing checks.
    
- 🌐 **Automated Cross-Platform Private Browser Launcher**:
  - Automatic launch of a private/incognito window with native OS priorities:
    - **macOS**: Safari $\rightarrow$ Google Chrome $\rightarrow$ Brave Browser $\rightarrow$ Firefox.
    - **Windows**: Google Chrome $\rightarrow$ Microsoft Edge $\rightarrow$ Firefox $\rightarrow$ Brave Browser.
    - **Linux**: Google Chrome $\rightarrow$ Chromium $\rightarrow$ Firefox $\rightarrow$ Brave $\rightarrow$ Microsoft Edge.
  - Loads local `index.html` with an embedded, responsive `Subway Surfers` game iframe.
  - Robust fallback structure to default system browser if primary browsers are not found.
    
- 📐 **Dynamic Cross-Platform Window Layout (100% Visibility)**:
  - The browser window occupies the first **3/4 of the screen (75%)** on the left (via AppleScript on macOS, `pygetwindow`/Win32 API on Windows, `wmctrl`/`xdotool` on Linux).
  - The OpenCV Motion Tracker preview window dynamically resizes and docks into the **remaining 1/4 (25%)** on the right.
  - Both windows automatically adapt to any screen resolution (Full HD, 2K, 4K, Retina displays) with zero overlap or clipping.
    
- 🖱️ **Smart START Button Auto-Click**:
  - Cursor automatically positions over the game's "START" button ($X = 50\%$ of browser, $Y = 62\%$ of screen height, 12% below center).
  - The start click is triggered **only after keypoint calibration is fully completed**.

---

### 📁 Project Structure

```text
SubwaySurferProject/
├── motion_tracker.py        # Main script: video capture, MediaPipe Pose & cross-platform window management
├── ui_renderer.py           # Graphical Renderer: HUD, calibration pop-ups, warning overlays
├── input_simulator.py       # Keyboard Input Simulator (PyAutoGUI) with lane management & debounce
├── index.html               # Responsive local HTML file embedding the Subway Surfers game
├── test_motion_tracker.py   # Cross-platform unit & integration test suite with Pytest
└── requirements.txt         # List of Python dependencies
```

### 🏗 Project Architecture
    
      ┌──────────────────────┐
      │    Webcam Capture    │
      └──────────┬───────────┘
                 │ Frame RGB
                 ▼
      ┌──────────────────────┐
      │ MediaPipe Pose Engine│
      └──────────┬───────────┘
                 │ Keypoints (x, y, z)
                 ▼
      ┌──────────────────────┐
      │  motion_tracker.py   │ ◄── ui_renderer.py (HUD & Overlay)
      └──────────┬───────────┘
                 │ Eventi / Stati
                 ▼
      ┌──────────────────────┐
      │  input_simulator.py  │ ──► Tasti Tastiera (UP, DOWN, LEFT, RIGHT, SPACE)
      └──────────────────────┘

---

### 🛠️ System Requirements

- **Operating System**: Fully cross-platform supported on **macOS**, **Windows** (10/11), and **Linux**.
  - *Optional window positioning tools*: `pygetwindow` on Windows; `wmctrl` or `xdotool` on Linux.
- **Python**: 3.10 or higher (Python 3.10 – 3.12 recommended for MediaPipe Pose compatibility).
- **Webcam**: Built-in webcam (e.g. FaceTime HD) or external USB/Continuity Camera.

---

### 🚀 Installation & Setup Guide

#### 1. Clone the Repository
```bash
git clone https://github.com/jimmyxan/SubwaySurfer_IRL.git

cd SubwaySurfer_IRL
```

#### 2. Create & Activate a Virtual Environment (Recommended)
```bash
# Create virtual environment
python3 -m venv .venv

# Activate on macOS / Linux
source .venv/bin/activate

# Activate on Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Activate on Windows (CMD)
# .venv\Scripts\activate.bat
```

#### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> [!IMPORTANT]
> Make sure u are positioned inside the Virtual Environment when you install the dependencies!

---

### 🎮 How to Play

Launch the main script from your terminal:

```bash
python motion_tracker.py
```
If you get an error related to the virtual environment not being active, run directly:

- **macOS / Linux**:
  ```bash
  ./.venv/bin/python3 motion_tracker.py
  ```
- **Windows**:
  ```powershell
  .\.venv\Scripts\python.exe motion_tracker.py
  ```

#### Execution Workflow:
1. **Browser Launch**: A private window of your browser automatically opens on the left (75% screen width) loading `index.html`.
2. **Video Window Positioning**: The OpenCV Motion Tracker window docks to the right (25% screen width).
3. **Countdown & Calibration**:
   - Stand centered in front of your webcam.
   - A pop-up on screen displays a 3-second countdown (3.. 2.. 1..).
   - Hold still and upright for automatic pose calibration (~4 seconds).
4. **Automatic Game Start**: Once calibration completes, the script clicks the **START** button to launch the game.
   
5. **Motion Controls**:
   - **Jump**: Jump or lift your shoulders above the green threshold line.
   - **Crouch**: Bend down below the cyan threshold line.
   - **Lateral Move**: Step or tilt left/right across the yellow vertical lines.
   - **Hoverboard**: Join hands or clap to activate the skateboard.
6. **Exit**: Press `ESC` on the video preview window to close cleanly.

---

### 🧪 Running Tests

The project includes unit and integration tests verifying framing, input simulations, HUD rendering, cross-platform private browser launching, and dynamic window layout adaptation across multiple display resolutions and OS platforms.

Run the test suite with `pytest`:

```bash
pytest -v
```

---

### 📜 License

This project is licensed under the MIT License - see the `LICENSE` file for details.

---
---

## 🇮🇹 Italiano

Un'applicazione avanzata di **Computer Vision & AI** in Python che consente di giocare a **Subway Surfers** controllando il personaggio direttamente con i movimenti del proprio corpo e gesti delle mani in tempo reale tramite la webcam.


<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/OpenCV-4.x-green?style=for-the-badge&logo=opencv" alt="OpenCV">
  <img src="https://img.shields.io/badge/MediaPipe-Pose-orange?style=for-the-badge" alt="MediaPipe">
  <br>
  <img src="https://img.shields.io/badge/macOS-Supported-brightgreen?style=for-the-badge&logo=apple" alt="macOS">
  <img src="https://img.shields.io/badge/Windows-Supported-blue?style=for-the-badge&logo=windows" alt="Windows">
  <img src="https://img.shields.io/badge/Linux-Supported-yellow?style=for-the-badge&logo=linux" alt="Linux">
</p>

---

### ✨ Caratteristiche Principali

- 🏃 **Tracciamento dei Movimenti Corporei in Tempo Reale**:
  - **Salto ($\uparrow$)**: Sollevamento del busto/spalle.
  - **Capriola / Scivolata ($\downarrow$)**: Abbassamento del busto.
  - **Spostamento Sinistra ($\leftarrow$) / Destra ($\rightarrow$)**: Inclinazione o traslazione laterale del busto.
  - 🛹 **Gesto Applauso per Hoverboard ($\text{Spazio}$)**: Rilevamento multi-keypoint (polsi, dita, pollici) del gesto delle mani unite / applauso per attivare istantaneamente l'Hoverboard.
  
- 🎯 **Calibrazione Automatica con HUD**:
  - Pop-up con conto alla rovescia di 3 secondi per prepararsi al centro dell'inquadratura.
  - Calibrazione dinamica delle posizioni base di spalle e busto (120 frame).
  - Rilevamento adattivo della presenza dei fianchi e controllo inquadratura.
    
- 🌐 **Automazione Browser Cross-Platform in Navigazione Privata**:
  - Avvio automatico di una finestra privata/incognito con priorità native in base al sistema operativo:
    - **macOS**: Safari $\rightarrow$ Google Chrome $\rightarrow$ Brave Browser $\rightarrow$ Firefox.
    - **Windows**: Google Chrome $\rightarrow$ Microsoft Edge $\rightarrow$ Firefox $\rightarrow$ Brave Browser.
    - **Linux**: Google Chrome $\rightarrow$ Chromium $\rightarrow$ Firefox $\rightarrow$ Brave $\rightarrow$ Microsoft Edge.
  - Carica il file locale `index.html` con il gioco `Subway Surfers` incorporato.
  - Struttura di fallback automatica sul browser di sistema predefinito in caso di assenza dei browser primari.
    
- 📐 **Layout Dinamico delle Finestre Cross-Platform (100% Visibilità)**:
  - La finestra del browser occupa esattamente i primi **3/4 dello schermo (75%)** a sinistra (tramite AppleScript su macOS, `pygetwindow`/Win32 API su Windows, `wmctrl`/`xdotool` su Linux).
  - La finestra OpenCV del Motion Tracker viene ridimensionata ed affiancata nel **restante 1/4 dello schermo (25%)** a destra.
  - Entrambe le finestre si adattano automaticamente a qualsiasi risoluzione dello schermo (Full HD, 2K, 4K, display Retina).
    
- 🖱️ **Autoclick Smart sul Tasto START**:
  - Il cursore viene posizionato automaticamente sul tasto "START" del gioco ($X = 50\%$ del browser, $Y = 62\%$ dello schermo, 12% sotto il centro).
  - Il click di avvio viene inviato **solamente dopo che la calibrazione dei keypoint è stata ultimata**.

---

### 📁 Struttura del Progetto

```text
SubwaySurferProject/
├── motion_tracker.py        # Script principale: acquisizione video, posa MediaPipe e gestione finestre cross-platform
├── ui_renderer.py           # Rendering Grafico: HUD, pop-up di calibrazione, avvisi ed overlay
├── input_simulator.py       # Simulatore di input da tastiera (PyAutoGUI) con gestione corsie e debounce
├── index.html               # File HTML locale responsive con embed del gioco Subway Surfers
├── test_motion_tracker.py   # Suite di test unitari cross-platform con Pytest
└── requirements.txt         # Elenco delle dipendenze Python
```

### 🏗 Architettura del Progetto
    
      ┌──────────────────────┐
      │    Webcam Capture    │
      └──────────┬───────────┘
                 │ Frame RGB
                 ▼
      ┌──────────────────────┐
      │ MediaPipe Pose Engine│
      └──────────┬───────────┘
                 │ Keypoints (x, y, z)
                 ▼
      ┌──────────────────────┐
      │  motion_tracker.py   │ ◄── ui_renderer.py (HUD & Overlay)
      └──────────┬───────────┘
                 │ Eventi / Stati
                 ▼
      ┌──────────────────────┐
      │  input_simulator.py  │ ──► Tasti Tastiera (UP, DOWN, LEFT, RIGHT, SPACE)
      └──────────┬───────────┘
      
---

### 🛠️ Requisiti di Sistema

- **Sistema Operativo**: Supporto nativo cross-platform per **macOS**, **Windows** (10/11) e **Linux**.
  - *Strumenti opzionali per il posizionamento finestra*: `pygetwindow` su Windows; `wmctrl` o `xdotool` su Linux.
- **Python**: 3.10 o superiore (consigliato Python 3.10 – 3.12 per la compatibilità con MediaPipe Pose).
- **Webcam**: Webcam integrata (es. FaceTime HD) o fotocamera USB/Continuity Camera.

---

### 🚀 Guida all'Installazione e Avvio

#### 1. Clonare la Repository
```bash
git clone https://github.com/jimmyxan/SubwaySurfer_IRL.git

cd SubwaySurfer_IRL
```

#### 2. Creare ed Attivare un Ambiente Virtuale (Consigliato)
```bash
# Creazione dell'ambiente virtuale
python3 -m venv .venv

# Attivazione su macOS / Linux
source .venv/bin/activate

# Attivazione su Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Attivazione su Windows (CMD)
# .venv\Scripts\activate.bat
```

#### 3. Installare le Dipendenze
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> [!IMPORTANT]
> Assicurati di essere posizionato all'interno dell'Ambiente Virtuale (Venv) quando installi le dipendenze!

---

### 🎮 Come Giocare

Avvia lo script principale dal terminale:

```bash
python motion_tracker.py
```
Se ricevi un errore riguardo la mancata attivazione dell'Ambiente Virtuale, esegui direttamente:

- **macOS / Linux**:
  ```bash
  ./.venv/bin/python3 motion_tracker.py
  ```
- **Windows**:
  ```powershell
  .\.venv\Scripts\python.exe motion_tracker.py
  ```

#### Flusso di Esecuzione:
1. **Avvio del Browser**: Si aprirà automaticamente una finestra privata del browser a sinistra (75% dello schermo) caricando `index.html`.
2. **Posizionamento Finestra Video**: L'anteprima video del Motion Tracker si posizionerà sulla destra (25% dello schermo).
3. **Conto alla Rovescia & Calibrazione**:
   - Posizionati al centro dell'inquadratura della webcam.
   - Sullo schermo comparirà un pop-up con un conto alla rovescia (3.. 2.. 1..).
   - Rimani fermo e dritto per la calibrazione automatica (~4 secondi).
     
4. **Avvio Automatico del Gioco**: Al termine della calibrazione, lo script invierà il click sul pulsante **START** per iniziare la partita.

5. **Controllo dei Movimenti**:
   - **Salto**: Salta o alza le spalle sopra la linea verde.
   - **Capriola**: Piegati verso il basso sotto la linea azzurra.
   - **Spostamento Laterale**: Fai un passo o inclinati a sinistra/destra oltre le linee verticali gialle.
   - **Hoverboard**: Unisci le mani / fai un gesto di applauso per attivare lo skateboard.

6. **Uscita**: Premi il tasto `ESC` sulla finestra dell'anteprima video per chiudere l'applicazione in modo pulito.

---

### 🧪 Esecuzione dei Test

Il progetto include test unitari ed integrati per verificare l'inquadratura, le simulazioni di input, il rendering dell'HUD, l'apertura privata del browser ed il ridimensionamento dinamico del layout delle finestre cross-platform.

Per eseguire l'intera suite di test con `pytest`:

```bash
pytest -v
```

---

### 📜 Licenza

Questo progetto è distribuito sotto Licenza MIT. Consulta il file `LICENSE` per ulteriori dettagli.