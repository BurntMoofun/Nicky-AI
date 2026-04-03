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

## 🚀 Quick Start

### 1. Install Ollama
Download from [ollama.com](https://ollama.com) and pull a model:
```bash
ollama pull llama3
```

### 2. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/nicky-ai.git
cd nicky-ai
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Nicky
```bash
python main.py
```

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
*[Add your demo video link here after recording]*

---

## 📝 License
MIT — do whatever you want with it.

---

*Built by a teenager with a robotic arm and too much free time. 🤖*
