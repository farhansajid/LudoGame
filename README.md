# 🎲 Royal Ludo Championship with Real-Time Audio Calling

A full-featured multiplayer **Ludo Game** with built-in **Real-Time Local Audio Calling**, intelligent AI bots, and high-definition canvas visuals.

---

## ✨ Features

### 🎙️ 1. Real-Time Local Audio Calling System
- **Dual-Engine Voice Pipeline**:
  - **Native WebRTC Mesh**: Direct peer-to-peer audio calling over LAN/loopback with ultra-low latency (<40ms) and crystal-clear Opus sound.
  - **WebSocket Binary PCM Relay**: Automatic fallback audio relay for restricted networks where direct UDP peer-to-peer is blocked.
- **Microphone & Speaker Controls**:
  - Quick **Mute / Unmute** toggle (button or shortcut `M`).
  - **Deafen / Undeafen** toggle (button or shortcut `D`).
  - **Push-to-Talk (PTT)** option: hold `Space` or `T` to talk.
  - **Live Speaking Halo**: Glowing emerald voice pulse rings around the active speaker's avatar on the board and player cards.
  - **Audio Settings Modal**: Test your microphone with local loopback to hear how you sound, plus individual per-player volume sliders.

### 🎮 2. Authentic & Complete Ludo Rules Engine
- **2 to 8 Players**: Supports 2, 3, 4 players (Classic square), 6 players (Hexagon board with 78 tiles), and 8 players (Octagon board with 104 tiles).
- **🎲🎲 2-Dice Mode (Select Die to Step)**:
  - Option to roll 2 dice simultaneously with realistic 3D tumbling physics for both dice.
  - Interactive die selection: player clicks or hits hotkey to choose which rolled die value to use for moving their piece.
  - Smart AI bots evaluate and select the optimal die value based on captures, safety, and goal entries.
  - Double sixes penalty rule: rolling two double-sixes consecutively preserves turn; three consecutive double-sixes forfeits the turn.
- **⚡ Fast Boost Opening (Roll 1 or 6)**:
  - Tokens can open from the Yard on rolling a **1** or a **6** (enabled by default for fast, action-packed matches).
  - Can be toggled to Classic mode (rolling 6 only) in Match Options or in-game Settings.
  - Interactive slash command: `/boost on` or `/boost off`.
  - Rolling 1 opens a pawn to the start square without bonus turn; rolling 6 opens and awards a bonus turn.
- **🤝 2v2 Teamwork Mode [Preview] (`/teamwork-preview`)**:
  - Strategic 2v2 partnership format: **Team Alpha (Red + Yellow)** vs. **Team Bravo (Green + Blue)**.
  - **Teammate Immunity & Safe Sharing**: Friendly pawns cannot capture each other on track squares; they co-exist safely on shared squares.
  - **Finished Player Partner Assistance**: When a player gets all 4 pawns home into the goal, their turns continue to roll and move their teammate's pawns!
  - **Team Victory**: Match ends when all 8 pawns of a team have successfully reached the goal.
  - **In-Game Team HUD**: Real-time team scoreboard banner (`🔴+🟡 Team Alpha: X/8` vs `🟢+🔵 Team Bravo: Y/8`) and team crests on pawns (gold for Alpha, cyan for Bravo).
  - Interactive slash command: `/teamwork-preview on` or `/teamwork-preview off` (or toggle in Match Format / Settings).
- **Extra Turns**:
  - Rolling a 6 grants an extra turn.
  - Capturing an opponent token grants an extra turn.
  - Reaching the home goal grants an extra turn.
  - Three consecutive 6s rule penalty forfeits the 3rd turn.
- **8 Safe Squares**: 4 starting squares + 4 star squares where tokens cannot be captured.
- **Home Column & Exact Roll**: Tokens cannot overshoot the final home goal.
- **Smart AI Bots**: Heuristic AI players that prioritize captures, goal scoring, escaping danger, entering board on 1 or 6, and assisting partners in 2v2 mode.

### 🎨 3. Excellent Graphics, Physics & UX Improvements
- **🎆 Advanced Particle Physics Systems**:
  - **⚔️ Capture Knockout Blast**: Fiery explosion shockwave, 30 bouncing sparks with gravity, and floating `⚔️ KNOCKOUT!` banner upon capturing an opponent piece.
  - **👑 Goal Reached Celebration**: Grand golden shockwave, celebratory rotating confetti, and star fountaining upon scoring into the home goal.
  - **🔥 6 Release Power Surge**: Radial golden energy rays and fire spark aura when launching pawns from the yard on a 6.
  - **🛡️ Danger Evasion Speed Trails**: Cyan and emerald protective shield ripple and wind speed trails when skillfully moving out of an opponent's capture range.
- **Interactive Move Destination Preview**: Hovering over movable tokens previews destination tile with animated dashed curved trajectory, pulsing landing target, safe square shield, capture crosshairs, teamwork safe reticle (`🤝 TEAM SAFE!`), boost release (`⚡ BOOST!`), or goal crown (`👑 GOAL!`).
- **⚡ Boost Opening Burst Particles**: Celebratory "⚡ BOOST!" particle burst and custom procedural chimes when launching pawns on 1.
- **💬 Chat Slash Commands**: Instant in-game chat commands:
  - `/boost [on/off]` — toggles opening pawns on roll of 1.
  - `/teamwork-preview [on/off]` (or `/teamwork`) — toggles 2v2 Teamwork partnership mode.
  - `/help` — displays available chat commands.
- **⏩ Auto-Move Single Choice**: Option to instantly advance when only 1 legal move is available, accelerating match flow.
- **⏱️ Turn Timer Bar**: Smooth animated countdown bar on turn banner keeping games brisk and dynamic.
- **📣 Live Game Event Feed**: Automated combat, partner assist, boost launch, and milestone announcements directly in the chat window.
- **High-DPI Retina Canvas**: Crisp 60fps rendering with smooth piece hopping physics arcs and landing puffs.
- **3 Luxury Board Themes**:
  1. *🪵 Royal Mahogany Wood & Gold*: Polished walnut with brass inlays, engraved star crests, and velvet yards.
  2. *⚡ Cyberpunk Neon*: Dark cyber grid with glowing neon lanes and pulsing nodes.
  3. *💎 Emerald Luxury Marble*: Jade green, ruby red, and diamond marble textures.
- **3D Animated Dice**: Interactive tumbling CSS cube with realistic perspective, physics bounce, and metallic pips.
- **Visual FX**: Knockout shockwaves on captures, sparkling star chimes on safe spots, and victory confetti.
- **Procedural Sound Engine**: Synthesizes all sounds via Web Audio API (dice rattle, hops, captures, token release chimes, victory fanfare) without any missing audio files.
- **Live In-Game Chat & Floating Reaction Emojis** (🎉, 😂, 🔥, 👑, etc.).

---

## 🚀 How to Run

### Option 1: 1-Click Launch (Windows)
Double-click `run_game.bat`. It will automatically check dependencies and launch the game.

### Option 2: Python Command Line
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server (HTTP)
python main.py

# 3. Optional: Run over HTTPS (enables microphone on remote mobile devices)
python main.py --ssl-cert path/to/cert.pem --ssl-key path/to/key.pem
```
Your default browser will automatically open to `http://localhost:8080`.

### 🌐 LAN / Wi-Fi Multiplayer & Audio Calling
To play with family or friends on the same Wi-Fi network:
1. When you run `main.py`, the terminal displays your local LAN IP (e.g. `http://192.168.1.15:8080`).
2. Anyone on your Wi-Fi (phone, tablet, laptop) can open that URL in their browser!
3. Select your match format: **2 Players (Duel)**, **3 Players**, or **4 Players (Classic)**.
4. Host creates a room code (e.g. `LUDO-7421`), and other players enter that code to join with real-time voice chat enabled!
5. On mobile browsers (Chrome/Safari), accessing over HTTPS or setting `chrome://flags/#unsafely-treat-insecure-origin-as-secure` allows full microphone broadcasting; otherwise, mobile joins in listen-only mode.

---

## ⌨️ Keyboard Shortcuts
| Key | Action |
| --- | --- |
| `Space` | Roll Dice (or Push-to-Talk if PTT enabled) |
| `M` | Toggle Microphone Mute |
| `D` | Toggle Deafen |
| `T` | Push-to-Talk (when enabled) |
| `Enter` | Send Chat Message |

---

## 🧪 Testing & Verification
To run the automated test suite (65 comprehensive unit, integration, DOM, 6/8 player, 2-dice, and full match simulation tests):
```bash
python -m unittest discover tests -v
```
All tests verify:
- Board coordinates and perimeter steps (4-player 52 tiles, 6-player 78 tiles, 8-player 104 tiles)
- Yard token release (on 1 and 6) and movement logic
- Danger evasion and particle trigger state flags
- 2-dice rolling, die selection, and AI die evaluation
- Captures on unsafe squares and safe square immunity
- Exact roll goal entries and overshoot prevention
- Consecutive 6s and double-6s penalties
- Winning player turn advancement without extra turn stall
- AI bot move heuristics across Easy, Medium, and Hard difficulty levels
- Real-time audio signaling (WebRTC SDP / ICE), conference routing, and 1-on-1 individual private calls
- Mid-game player quit with automated AI bot handover
- Capture bonus turns awarded in single-die and two-dice modes
- Frontend DOM elements and asset linking integrity
- End-to-end match simulations for 2-player, 4-player, classic, and 2v2 teamwork games to completion without deadlocks

---

## 📖 Deployment & Mobile Publishing Guides
For complete step-by-step production guides:
- 🌐 **[Internet Multiplayer & WebRTC Audio Deployment Guide](file:///i:/Sara%20Games/Ludo%20Game/DEPLOYMENT_GUIDE.md#1-internet-multiplayer-server-deployment)** (Ubuntu VPS, Nginx Reverse Proxy, WebSocket WSS, Let's Encrypt SSL, Coturn STUN/TURN server).
- 📱 **[Android App Packaging & Google Play Store Guide](file:///i:/Sara%20Games/Ludo%20Game/DEPLOYMENT_GUIDE.md#3-android-app-packaging--google-play-store-publishing)** (Capacitor initialization, Android permissions, WebView WebRTC microphone handling, Keystore signing, AAB building, and Google Play Data Safety declaration).

