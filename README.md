# 🤖 Nicky AI

> A personal AI assistant built in Python — originally designed to control a robotic arm, now a full-featured AI companion with games, tools, voice, and personality.

---

## ✨ Features

### 🧠 AI Core
- Powered by **Ollama** (local LLM — llama3 or any model) + optional **Google Gemini**
- Persistent **long-term memory** — remembers your name, age, location, hobbies, projects
- **Custom personality** — adjusts tone through conversation (sarcastic, funny, serious, etc.)
- **Mood system** — Nicky's mood shifts based on conversation (shown as emoji in prompt)
- **Knowledge base** — auto-saves every DDG/Wikipedia search result for future recall
- **Chain-of-thought reasoning** — breaks down complex questions step by step
- **Topic tracking** — maintains context across follow-up questions

### 🛠️ Tools
| Command | What it does |
|---|---|
| `weather in Tokyo` | Live weather via wttr.in |
| `news` / `tech news` | BBC RSS headlines |
| `set a 10 minute timer` | Background timer with voice alert |
| `add buy milk` | Persistent to-do list |
| `what is 15% of 200` | Math solver with percentage support |
| `translate hello to Spanish` | Free translation (MyMemory API) |
| `volume up` / `mute` | Windows volume control |
| `open calculator` | Open any app by name |
| `screenshot` | Saves screenshot to Desktop |

### 🎮 Games
| Game | Mode |
|---|---|
| Snake | Nicky plays solo |
| Brick Breaker | Nicky plays solo |
| Chess | You vs Nicky |
| Connect 4 | You vs Nicky (minimax AI) |
| Tic Tac Toe | You vs Nicky (unbeatable) |
| Hangman | You play, Nicky hosts |
| Pong | You (W/S keys) vs Nicky |

### 🤝 Conversation Modes
- **Casual Mode** — pure chat, no arm commands
- **Workshop Mode** — full robotic arm control + chat
- **100% Output Mode** — hype music + fast arm movements (15% chance of Rick Roll 💀)

### 📖 Creative AI
- `tell me a story about X` — collaborative storytelling
- `quiz me on space` — dynamic quiz on any topic
- `explain this code: [code]` — code helper and explainer

### 🦾 Robotic Arm (Workshop Mode)
- Move commands: `move left/right/up/down/forward/back`
- `grab`, `release`, `throw`
- Camera scan, object detection, sequences

---

## 🚀 Installation & Setup (Step by Step)

### Step 1 — Install Python 3.10+
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the latest **Python 3.10+** installer for Windows
3. Run the installer — **check "Add Python to PATH"** before clicking Install
4. Verify it worked by opening a terminal and running:
   ```bash
   python --version
   ```
   You should see something like `Python 3.11.x`

---

### Step 2 — Install Git
1. Go to [git-scm.com/downloads](https://git-scm.com/downloads)
2. Download and run the Windows installer (leave all defaults as-is)
3. Verify:
   ```bash
   git --version
   ```

---

### Step 3 — Clone the Repo
Open a terminal (Command Prompt or PowerShell) and run:
```bash
git clone https://github.com/BurntMoofun/nicky-ai.git
cd nicky-ai
```

---

### Step 4 — Install Python Dependencies
Inside the `nicky-ai` folder, run:
```bash
pip install -r requirements.txt
```
This installs all of the following automatically:

| Package | What it's for |
|---|---|
| `pyttsx3` | Text-to-speech (Nicky's voice) |
| `SpeechRecognition` | Microphone/voice input |
| `sounddevice` + `soundfile` | Audio playback |
| `edge-tts` | Higher quality TTS voice option |
| `wikipedia` | Wikipedia lookups |
| `matplotlib` | Workspace visualization / graphs |
| `sentence-transformers` | Smarter understanding of your questions |
| `torch` | Required by sentence-transformers (PyTorch) |
| `numpy` | Math/array support |
| `ddgs` | DuckDuckGo web search |

> ⚠️ **Note on `torch`:** PyTorch is a large download (~200–500MB). This is normal — just let it run.

---

### Step 5 — Install Ollama (the AI brain)
> Without this, Nicky still runs but gives basic pre-written responses instead of real AI answers.

1. Go to [ollama.com](https://ollama.com) and click **Download for Windows**
2. Run the installer
3. Once installed, open a terminal and run:
   ```bash
   ollama pull llama3.2
   ```
   > ⚠️ This downloads the AI model — about **2GB**. Wait for it to finish.
4. Ollama runs automatically in the background after install. To verify:
   ```bash
   ollama list
   ```
   You should see `llama3.2` in the list.

---

### Step 6 — Run Nicky
```bash
python main.py
```

That's it! Nicky will start up and you can begin chatting.

---

### ❓ Troubleshooting

**`pip` not recognized** → Make sure you checked "Add Python to PATH" during install. Re-install Python if needed.

**`torch` install fails** → Try: `pip install torch --index-url https://download.pytorch.org/whl/cpu`

**Ollama not responding** → Make sure Ollama is running. Open the Start menu and launch **Ollama**, or run `ollama serve` in a terminal.

**No voice output** → `pyttsx3` requires Windows. Make sure your speakers aren't muted and you're on Windows.

**Microphone not working** → Voice input is optional. Just type your messages instead.

---

## 🎵 100% Output Mode (Optional)
Drop a music file named `hype.mp3` into the project folder, then say:
```
100% output
```
Nicky will play your music and move the arm at maximum speed.
*(There is a small chance she Rick Rolls you instead. This is intentional.)*

---

## 💬 Example Commands
```
You: what is the speed of light
You: tell me a story about a robot
You: quiz me on history
You: play chess
You: set a 5 minute timer
You: translate good morning to Japanese
You: 100% output
You: workshop mode
You: move left
```

---

## ⚙️ Optional: Google Gemini
Get an API key from [Google AI Studio](https://aistudio.google.com) and run:
```
set gemini key YOUR_KEY_HERE
use gemini
```

---

## 📋 Requirements
- Python 3.10+
- [Ollama](https://ollama.com) running locally
- Windows (for voice, volume control, screenshot features)
- Microphone (optional, for voice input)

---

## 🗂️ Project Structure
```
nicky-ai/
├── main.py          # Everything — all features in one file
├── requirements.txt
├── QUICK_START.txt
└── nicky_data/      # Auto-created — stores memory, knowledge, todos
```

---

## 🎬 Demo
*[none]*

---

## 📝 License
MIT — do whatever you want with it.

---

*Built by a teenager with a robotic arm and too much free time. 🤖*
