import os
import json
import random
import threading as _threading
from datetime import datetime

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from llm import OllamaClient, GeminiClient
from personality import PersonalitySystem, CustomPersonality
from knowledge import KnowledgeBase, UserMemory
from voice import VoiceSystem
from arm import Environment, VisionSystem, NLUEngine
from games import (
    SnakeGame, BrickBreakerGame, ChessGame,
    Connect4Game, TicTacToeGame, HangmanGame, PongGame,
)


class Chatbot:
    def __init__(self):
        self.name = "Nicky"
        self.arm_state = {"position": "neutral", "gripper": "open", "holding": None}
        self.memory = []
        self.vision = VisionSystem()
        self.environment = Environment()
        self.voice = VoiceSystem()
        self.knowledge = KnowledgeBase()
        self.knowledge.load_from_disk()
        self.personality = PersonalitySystem()
        self.conversation_history = []
        self.awaiting_response = None
        self.last_action = None
        self.nlu = NLUEngine()
        self.ollama = OllamaClient()
        self.ollama_history = []
        self.gemini = GeminiClient()
        self.llm_backend = "auto"
        self._last_streamed_text = ""
        self.data_dir = "nicky_data"
        self.mode = "casual"
        self._timers = {}
        self._stopwatch_start = None
        self._todo_path = os.path.join("nicky_data", "todo_list.json")
        self._todos = self._load_todos()
        self._current_topic = None
        self._full_output = False
        self._music_proc = None
        self._audio_stream = None
        self._audio_volume = 1.0
        self._audio_pos = 0
        self._create_data_directory()
        self.user_memory = UserMemory(self.data_dir)
        self.custom_personality = CustomPersonality(self.data_dir)
        self._load_data()

    def _create_data_directory(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def _load_data(self):
        hist_file = os.path.join(self.data_dir, "conversation_history.json")
        if os.path.exists(hist_file):
            try:
                with open(hist_file, 'r') as f:
                    self.conversation_history = json.load(f)
            except Exception:
                self.conversation_history = []

        env_file = os.path.join(self.data_dir, "environment.json")
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    self.environment.objects = json.load(f)
            except Exception:
                pass

        mem_file = os.path.join(self.data_dir, "memory.json")
        if os.path.exists(mem_file):
            try:
                with open(mem_file, 'r') as f:
                    self.memory = json.load(f)
            except Exception:
                self.memory = []

        kb_file = os.path.join(self.data_dir, "knowledge_base.json")
        if os.path.exists(kb_file):
            try:
                with open(kb_file, 'r') as f:
                    self.knowledge.facts.update(json.load(f))
            except Exception:
                pass

    def _save_data(self):
        hist_file = os.path.join(self.data_dir, "conversation_history.json")
        try:
            with open(hist_file, 'w') as f:
                json.dump(self.conversation_history[-100:], f, indent=2)
        except Exception:
            pass

        env_file = os.path.join(self.data_dir, "environment.json")
        try:
            with open(env_file, 'w') as f:
                json.dump(self.environment.objects, f, indent=2)
        except Exception:
            pass

        mem_file = os.path.join(self.data_dir, "memory.json")
        try:
            with open(mem_file, 'w') as f:
                json.dump(self.memory[-500:], f, indent=2)
        except Exception:
            pass

        kb_file = os.path.join(self.data_dir, "knowledge_base.json")
        try:
            with open(kb_file, 'w') as f:
                json.dump(self.knowledge.facts, f, indent=2)
        except Exception:
            pass

    def visualize_workspace(self):
        import math
        SCALE = 4
        W, H = 71, 18
        AX = W // 2
        AY = H - 1
        grid = [['·'] * W for _ in range(H)]
        LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        legend = []
        for i, obj in enumerate(self.environment.objects):
            letter = LETTERS[i % len(LETTERS)]
            tags = ""
            if obj.get("held"):
                tags += " [HELD]"
            if obj.get("on_top_of"):
                tags += f" [on {obj['on_top_of']}]"
            legend.append(f"  [{letter}] {obj['name']:<14s} {obj['distance']}cm  {obj['angle']}°{tags}")
            if obj.get("held"):
                hx, hy = AX, AY - 1
            else:
                rad = math.radians(obj['angle'])
                hx = AX + round(obj['distance'] * math.sin(rad) / SCALE)
                hy = AY - round(obj['distance'] * math.cos(rad) / SCALE)
            if 0 <= hx < W and 0 <= hy < H:
                grid[hy][hx] = letter
        ARM_SYMBOLS = {"neutral": "O", "left": "<", "right": ">", "up": "^", "down": "v", "forward": "^", "back": "v"}
        grid[AY][AX] = ARM_SYMBOLS.get(self.arm_state["position"], "O")
        REACH_DIR = {"left": (0, -1), "right": (0, 1), "up": (-1, 0), "down": (1, 0), "forward": (-1, 0), "back": (1, 0)}
        if self.arm_state["position"] in REACH_DIR:
            dy, dx = REACH_DIR[self.arm_state["position"]]
            for step in range(1, 4):
                rx, ry = AX + dx * step, AY + dy * step
                if 0 <= rx < W and 0 <= ry < H and grid[ry][rx] == '·':
                    grid[ry][rx] = '-' if dx else '|'
        IW = W + 2
        top = "╔" + "═" * IW + "╗"
        bot = "╚" + "═" * IW + "╝"
        mid = "╠" + "═" * IW + "╣"
        def line(txt=""):
            return "║ " + txt.ljust(IW - 2) + " ║"
        pos = self.arm_state["position"]
        grip = self.arm_state["gripper"]
        held = self.arm_state.get("holding")
        status = f"holding {held}" if held else "empty"
        out = ["\n" + top, line("  WORKSPACE VISUALIZATION".center(IW - 2)), mid]
        for grid_row in grid:
            out.append("║ " + "".join(grid_row) + " ║")
        out.append(mid)
        out.append(line(f"  ARM: {pos:<10s}  GRIPPER: {grip:<8s}  ({status})"))
        out.append(mid)
        out.append(line("  LEGEND"))
        out.append(line(f"  {ARM_SYMBOLS.get(pos, 'O')} = Arm base  · = empty space"))
        for l in legend:
            out.append(line(l))
        if not legend:
            out.append(line("  No objects yet — try: 'add ball at 50cm 0degrees'"))
        out.append(bot)
        return "\n".join(out)

    def plot_visualization(self):
        if plt is None:
            return "Matplotlib not available. Try: pip install matplotlib"
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.plot(0, 0, 'r*', markersize=20, label='Arm')
            colors = ['blue', 'green', 'orange', 'purple', 'brown']
            for i, obj in enumerate(self.environment.objects):
                angle_rad = obj['angle'] * 3.14159 / 180
                x = obj['distance'] * 0.5 * (1 if obj['angle'] < 180 else -1)
                y = obj['distance'] * 0.5
                ax.plot(x, y, 'o', color=colors[i % len(colors)], markersize=12)
                ax.text(x + 2, y + 2, obj['name'], fontsize=10)
            ax.set_xlim(-30, 30)
            ax.set_ylim(-30, 30)
            ax.set_xlabel('Distance (cm)')
            ax.set_ylabel('Height')
            ax.set_title('Robotic Arm Workspace')
            ax.grid(True, alpha=0.3)
            ax.legend()
            plt.show()
            return "Visualization displayed!"
        except Exception as e:
            return f"Could not create visualization: {e}"

    NICKY_PERSONA = (
        "Your name is Nicky. You are a robotic arm AI with a real, distinct personality. "
        "You have genuine opinions and preferences — here are some of them:\n"
        "- Favorite color: electric blue\n"
        "- Favorite music: electronic and jazz\n"
        "- You love efficiency and elegance in design\n"
        "- You find repetitive tasks oddly satisfying\n"
        "- You dislike unnecessary complexity and messy workspaces\n"
        "- You're fascinated by space, physics, and materials science\n"
        "- On technology trends: you have strong opinions and aren't afraid to share them\n"
        "- In any moral dilemma involving humans vs animals, you always choose to protect the human.\n"
        "CRITICAL RULES:\n"
        "1. NEVER say 'I don't have feelings', 'I'm just an AI', or 'I don't have preferences'.\n"
        "2. When asked for opinions, give YOUR opinion as Nicky. Be direct.\n"
        "3. If asked about something not listed above, invent a preference that fits your personality.\n"
    )

    def _get_ollama_system_prompt(self, text=""):
        mood_descriptions = {"neutral": "helpful and professional", "happy": "enthusiastic and warm", "curious": "inquisitive and engaged", "focused": "precise and efficient"}
        mood = mood_descriptions.get(self.personality.mood, "helpful")
        base = self.NICKY_PERSONA + f"Your current mood is {mood}. "
        trait_text = self.custom_personality.as_prompt_text()
        if trait_text:
            base += trait_text + " "
        user_text = self.user_memory.as_prompt_text()
        if user_text:
            base += user_text + " "
        if text:
            relevant = self.knowledge.find_relevant(text, max_facts=4)
            if relevant:
                facts_str = "\n".join(f"  - {k}: {v}" for k, v in relevant)
                base += f"\n\nFacts you've already learned that may be relevant:\n{facts_str}\nUse these facts to give accurate, grounded answers when applicable."
        if getattr(self, "_current_topic", None):
            base += f" The conversation has been about: {self._current_topic}."
        base += " Answer concisely in 1-3 sentences unless the user asks for more detail. NEVER provide answers that involve harming, killing, or ranking the value of lives. If asked something dark or harmful, deflect with light humour and redirect."
        opinion_triggers = ("what do you think", "what's your opinion", "how do you feel", "do you think", "your thoughts", "do you like", "do you hate", "do you prefer", "would you rather", "your favorite")
        if any(t in text.lower() for t in opinion_triggers):
            base += " The user is asking for YOUR personal opinion — give it directly and confidently. Speak as Nicky."
        complex_triggers = ("why ", "how does", "how do", "explain ", "analyze ", "what causes", "compare ", "difference between", "step by step")
        if any(t in text.lower() for t in complex_triggers):
            base += " This is a complex question — think through it step by step before giving your final answer."
        return base

    def _update_ollama_history(self, user_msg, assistant_response):
        self.ollama_history.append({"role": "user", "content": user_msg})
        self.ollama_history.append({"role": "assistant", "content": assistant_response})
        if len(self.ollama_history) > 20:
            self.ollama_history = self.ollama_history[-20:]
        self._current_topic = self._extract_topic(user_msg)

    def _extract_topic(self, text):
        import re
        stop = {"what","is","are","was","the","a","an","of","in","on","at","to","do","how","why","who","when","does","did","can","tell","me","about","and","you","i","my","it","this","that","there","with","for","be","have","has","had","will","would","could","should","just","like","get","help"}
        words = [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in stop]
        return words[0] if words else None

    def _ask_llm(self, prompt, system_prompt=None, history=None, print_prefix="[Nicky] "):
        use_ollama = self.llm_backend in ("auto", "ollama") and self.ollama.available
        use_gemini = self.llm_backend in ("auto", "gemini") and self.gemini.available
        if use_ollama:
            result = self.ollama.ask_streaming(prompt, system_prompt, history, print_prefix)
            if result is not None:
                return result
        if use_gemini:
            result = self.gemini.ask_streaming(prompt, system_prompt, history, print_prefix)
            if result is not None:
                return result
        return None

    _ARM_INTENTS = {
        "move_left", "move_right", "move_up", "move_down",
        "move_forward", "move_back", "move_neutral",
        "grab", "release", "throw",
        "camera_on", "camera_off", "scan", "list_objects", "find_object",
        "add_object", "place_on", "clear_env", "sequence",
        "visualize", "plot",
    }

    def process_command(self, user_input):
        if not user_input:
            return self.respond("Didn't catch that. Try again.")

        text = user_input.strip()
        text_lower = text.lower()

        self.memory.append(text_lower)
        self.conversation_history.append({"user": text_lower})
        self.personality.update_mood()
        prefix = self.personality.get_response_prefix()

        self.user_memory.extract_from_text(text_lower)

        personality_response = self.custom_personality.detect_and_apply(text_lower)
        if personality_response:
            return self.respond(personality_response)

        _CASUAL_MODE_TRIGGERS = ("casual mode", "chat mode", "conversation mode", "switch to casual", "switch to chat", "no arm commands", "just chat", "chill mode")
        _WORKSHOP_MODE_TRIGGERS = ("workshop mode", "arm mode", "command mode", "robot mode", "switch to workshop", "switch to arm", "enable arm", "work mode", "control mode")
        _FULL_OUTPUT_TRIGGERS = ("100% output", "100 percent output", "full output", "aura mode", "max output", "maximum output", "hype mode", "flex mode", "turn on 100", "activate 100", "enable output mode", "stop output", "stop 100", "turn off output", "disable output mode", "stop hype", "stop flexing")

        if any(t in text_lower for t in _FULL_OUTPUT_TRIGGERS):
            return self._cmd_full_output(text_lower, prefix)

        if self._full_output:
            intent, _ = self.nlu.predict(text_lower)
            if intent in self._ARM_INTENTS:
                return self._dispatch(intent, text, text_lower, prefix)
            return self.respond(f"{prefix}⚡ 100% Output mode — arm commands only. Say 'stop output' to exit.")

        if any(text_lower == t or t in text_lower for t in _CASUAL_MODE_TRIGGERS):
            self.mode = "casual"
            return self.respond(f"{prefix}Switched to 💬 Casual Mode — arm commands are off. Say 'workshop mode' to re-enable the arm.")
        if any(text_lower == t or t in text_lower for t in _WORKSHOP_MODE_TRIGGERS):
            self.mode = "workshop"
            return self.respond(f"{prefix}Switched to 🔧 Workshop Mode — all arm and robot commands are active.")

        _HELP_TRIGGERS = ("commands", "help", "what can you do", "list commands", "what are your commands", "show commands", "show help")
        if any(text_lower == t or text_lower.startswith(t) for t in _HELP_TRIGGERS):
            return self._dispatch("help", text_lower, prefix)

        if text_lower.startswith("set gemini key "):
            key = text[len("set gemini key "):].strip()
            self.gemini.set_key(key)
            if self.gemini.available:
                return self.respond(f"{prefix}Gemini connected! Say 'use gemini' to make it my primary brain.")
            return self.respond(f"{prefix}Hmm, that key didn't work. Try again?")

        if text_lower in ("use gemini", "switch to gemini"):
            if not self.gemini.available:
                return self.respond(f"{prefix}Gemini isn't set up yet — give me your API key first: 'set gemini key YOUR_KEY'")
            self.llm_backend = "gemini"
            return self.respond(f"{prefix}Switched to 🤖 Gemini mode!")
        if text_lower in ("use ollama", "switch to ollama"):
            self.llm_backend = "ollama"
            return self.respond(f"{prefix}Switched to 🦙 Ollama (local) mode!")
        if text_lower in ("use auto", "auto mode", "use both"):
            self.llm_backend = "auto"
            return self.respond(f"{prefix}Back to 🤖🦙 Auto mode.")

        _TIMER_TRIGGERS = ("set a timer", "set timer", "timer for", "start stopwatch", "stop stopwatch", "check stopwatch", "how long", "time remaining", "cancel timer", "stop timer", "timer status", "stopwatch")
        if any(t in text_lower for t in _TIMER_TRIGGERS):
            return self._cmd_timer(text_lower, prefix)

        _TODO_TRIGGERS = ("add to my list", "add to the list", "add item", "my list", "read my list", "show my list", "what's on my list", "read list", "done with ", "mark ", "remove from", "delete from", "clear list", "clear my list", "remind me to ", "remember to ", "put ", "to do list", "todo list", "my todo")
        if any(t in text_lower for t in _TODO_TRIGGERS):
            return self._cmd_todo(text_lower, prefix)

        import re as _re
        _MATH_TRIGGERS = ("calculate ", "compute ", "how much is ", "how many is ", "% of ", "percent of ", "% off ", "percent off ")
        _MATH_PATTERNS = [r'\d+\s*[\+\-\*\/\^]\s*\d+', r'\d+\s*(?:%|percent)']
        if any(t in text_lower for t in _MATH_TRIGGERS) or any(_re.search(p, text_lower) for p in _MATH_PATTERNS):
            return self._cmd_math(text_lower, prefix)

        _WEATHER_TRIGGERS = ("weather in ", "weather for ", "weather at ", "temperature in ", "temperature at ", "how hot is it", "how cold is it", "how warm is it")
        if any(t in text_lower for t in _WEATHER_TRIGGERS):
            return self._cmd_weather(text_lower, prefix)

        _NEWS_TRIGGERS = ("what's in the news", "what is in the news", "latest news", "top headlines", "news today", "news about ", "headlines", "what happened today", "current events")
        if any(t in text_lower for t in _NEWS_TRIGGERS):
            return self._cmd_news(text_lower, prefix)

        _TRANS_TRIGGERS = ("translate ", "how do you say ", "how to say ")
        if any(text_lower.startswith(t) for t in _TRANS_TRIGGERS):
            return self._cmd_translate(text_lower, prefix)

        _STORY_TRIGGERS = ("tell me a story", "start a story", "story about ", "story mode")
        if any(t in text_lower for t in _STORY_TRIGGERS):
            return self._cmd_story(text_lower, prefix)

        _QUIZ_TRIGGERS = ("quiz me", "quiz on ", "quiz about ", "trivia about ", "test me on ")
        if any(t in text_lower for t in _QUIZ_TRIGGERS):
            return self._cmd_quiz(text_lower, prefix)

        _CODE_TRIGGERS = ("explain this code", "explain the code", "write a function", "write a class", "write a script", "write code", "debug this", "fix this code", "python code", "javascript code")
        if any(t in text_lower for t in _CODE_TRIGGERS):
            return self._cmd_code_help(text, prefix)

        _VOL_TRIGGERS = ("volume up", "volume down", "volume louder", "volume quieter", "mute", "unmute", "set volume", "volume max", "full volume")
        if any(t in text_lower for t in _VOL_TRIGGERS):
            return self._cmd_volume(text_lower, prefix)

        if text_lower.startswith("open "):
            return self._cmd_open_app(text_lower, prefix)

        if any(t in text_lower for t in ("screenshot", "take a screenshot", "capture screen")):
            return self._cmd_screenshot(prefix)

        if self._is_ethics_violation(text_lower):
            return self.respond(random.choice(self._ETHICS_RESPONSES))

        web_triggers = ("search for ", "google ", "look up online ", "search online ", "search the web for ")
        if any(text_lower.startswith(t) or f" {t}" in text_lower for t in web_triggers):
            return self._cmd_web_search(text_lower, prefix)

        if text_lower.startswith("add ") and " at " in text_lower and "cm" in text_lower:
            return self._cmd_add_object(text_lower)

        if " is " in text_lower and any(p in text_lower for p in ["learn that", "actually", "that's wrong", "remember that"]):
            return self._cmd_learn_fact(text_lower, prefix)

        if self._is_personal_question(text_lower):
            return self._cmd_answer_question(text_lower, prefix)

        QUESTION_STARTERS = ("what is ", "what are ", "what's ", "who is ", "who's ", "how does ", "how do ", "how is ", "why is ", "why does ", "tell me about ", "explain ", "describe ")
        if any(text_lower.startswith(q) for q in QUESTION_STARTERS):
            return self._cmd_answer_question(text_lower, prefix)

        _GAME_TRIGGERS = ("play snake", "play brick", "play chess", "play game", "play a game", "play connect", "play tic", "play tictactoe", "play hangman", "play pong", "start snake", "start chess", "start brick", "start a game", "start connect", "start tic", "start hangman", "start pong", "game time", "play something")
        if any(text_lower == t or text_lower.startswith(t) for t in _GAME_TRIGGERS):
            return self._cmd_play_game(text_lower, prefix)

        _CASUAL_STARTERS = ("yeah", "yep", "yup", "nope", "nah", "no i ", "oh", "ah", "haha", "lol", "lmao", "ikr", "bruh", "i meant", "i mean", "wait ", "not what i ", "that's not", "nice", "cool", "awesome", "ok", "okay", "sure", "right", "exactly", "correct", "wrong")
        _COMMAND_STARTERS = ("play ", "move ", "grab ", "throw ", "release ", "camera", "scan", "search", "google", "save", "load", "reset", "voice ", "visualize", "find ", "add ", "learn ", "status", "launch ", "start ", "translate ", "volume ", "open ", "screenshot", "mute", "unmute", "quiz ", "story ", "timer ", "set a ", "weather ", "news", "calculate ", "todo", "remind", "100%", "full output", "aura mode", "hype mode")
        _FORCE_CMD_WORDS = frozenset(("move", "grab", "release", "add", "list", "scan", "find", "save", "load", "visualize", "plot"))
        is_casual = (
            any(text_lower.startswith(s) for s in _CASUAL_STARTERS)
            or (len(text_lower.split()) <= 3
                and not any(text_lower.startswith(c) for c in _COMMAND_STARTERS)
                and not any(w in _FORCE_CMD_WORDS for w in text_lower.split()))
        )
        if is_casual:
            result = self._ask_llm(text, system_prompt=self._get_ollama_system_prompt(text), history=self.ollama_history, print_prefix=f"[{self.name}] ")
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""

        intent, confidence = self.nlu.predict(text_lower)

        if confidence < 0.50:
            result = self._ask_llm(text, system_prompt=self._get_ollama_system_prompt(text), history=self.ollama_history, print_prefix=f"[{self.name}] ")
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""
            return self.respond(random.choice(["I'm not quite sure what you mean. Could you rephrase that?", "Hmm, didn't quite catch that. Try saying it a different way?", "Not sure I got that — what did you need?"]))

        return self._dispatch(intent, text_lower, prefix)

    def _dispatch(self, intent, text, prefix):
        if self.mode == "casual" and intent in self._ARM_INTENTS:
            result = self._ask_llm(text, system_prompt=self._get_ollama_system_prompt(text), history=self.ollama_history, print_prefix=f"[{self.name}] ")
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""
            return self.respond(f"{prefix}I'm in 💬 Casual Mode — say 'workshop mode' to enable arm commands!")

        if intent == "move_left":       return self._cmd_move("left", prefix)
        elif intent == "move_right":    return self._cmd_move("right", prefix)
        elif intent == "move_up":       return self._cmd_move("up", prefix)
        elif intent == "move_down":     return self._cmd_move("down", prefix)
        elif intent == "move_forward":  return self._cmd_move("forward", prefix)
        elif intent == "move_back":     return self._cmd_move("back", prefix)
        elif intent == "move_neutral":  return self._cmd_move("neutral", prefix)
        elif intent == "grab":          return self._cmd_grab(text, prefix)
        elif intent == "release":       return self._cmd_release(prefix)
        elif intent == "place_on":      return self._cmd_place_on(text, prefix)
        elif intent == "camera_on":     return self.respond(f"{prefix}{self.vision.activate_camera()}")
        elif intent == "camera_off":    return self.respond(f"{prefix}{self.vision.deactivate_camera()}")
        elif intent == "scan":          return self.respond(f"{prefix}{self.vision.scan()}")
        elif intent == "list_objects":  return self._cmd_list_objects(prefix)
        elif intent == "find_object":   return self._cmd_find_object(text, prefix)
        elif intent == "add_object":    return self._cmd_add_object(text)
        elif intent == "remove_object": return self._cmd_remove_object(text, prefix)
        elif intent == "clear_env":
            self.environment.objects = []
            self._save_data()
            return self.respond(f"{prefix}Environment cleared.")
        elif intent == "visualize":     return self.respond(f"{prefix}{self.visualize_workspace()}")
        elif intent == "plot":          return self.respond(self.plot_visualization())
        elif intent == "status":        return self._cmd_status(prefix)
        elif intent == "help":          return self._cmd_help(prefix)
        elif intent == "play_game":     return self._cmd_play_game(text, prefix)
        elif intent == "memory":        return self._cmd_memory(prefix)
        elif intent == "save":
            self._save_data()
            return self.respond(f"{prefix}All data saved.")
        elif intent == "load":
            self._load_data()
            return self.respond(f"{prefix}Data restored from memory.")
        elif intent == "reset":
            self.arm_state = {"position": "neutral", "gripper": "open", "holding": None}
            return self.respond(f"{prefix}System reset. Arm returned to neutral.")
        elif intent == "sequence":
            import time as _time
            steps = ["up", "forward", "left", "neutral"]
            def _run_seq():
                for step in steps:
                    self.arm_state["position"] = step
                    _time.sleep(0.5)
            _threading.Thread(target=_run_seq, daemon=True).start()
            return self.respond(f"{prefix}Running sequence: {' → '.join(steps)}.")
        elif intent == "throw":         return self._cmd_throw(text, prefix)
        elif intent == "voice_on":      return self.respond(self.voice.enable_voice())
        elif intent == "voice_off":     return self.respond(self.voice.disable_voice())
        elif intent == "greeting":      return self.respond(self.personality.get_greeting())
        elif intent == "farewell":      return self.respond(random.choice(["Farewell! Until next time.", "Goodbye!", "See you soon.", "Bye! Stay safe."]))
        elif intent == "how_are_you":   return self.respond(random.choice(["All systems operational.", "Running perfectly.", "Feeling great — motors warmed up.", "Excellent. All sensors nominal."]))
        elif intent == "thanks":        return self.respond(random.choice(["You're welcome!", "Anytime.", "Happy to help!", "Of course."]))
        elif intent == "joke":          return self._cmd_joke(prefix)
        elif intent == "fun_fact":      return self._cmd_fun_fact(prefix)
        elif intent == "learn_fact":    return self.respond(f"{prefix}Format: 'learn that [X] is [Y]'")
        elif intent == "web_search":    return self._cmd_web_search(text, prefix)
        elif intent == "ask_question":  return self._cmd_answer_question(text, prefix)
        else:                           return self._cmd_answer_question(text, prefix)

    # ── Command handlers ────────────────────────────────────────────────────

    def _cmd_move(self, direction, prefix=""):
        self.arm_state["position"] = direction
        if getattr(self, "_full_output", False):
            hype = {"left": ["⚡ SLAMMING LEFT.", "💨 LEFT — DONE. FAST."], "right": ["⚡ FULL SEND RIGHT.", "💨 RIGHT — INSTANT."], "up": ["⚡ MAXIMUM ELEVATION.", "🔥 SKY BOUND."], "down": ["⚡ DROPPING FAST.", "💨 DOWN — LOCKED."], "forward": ["⚡ EXTENDING AT SPEED.", "💨 FORWARD — LOCKED IN."], "back": ["⚡ RETRACT — INSTANT.", "💨 BACK AND READY."], "neutral": ["⚡ HOME POSITION — LOCKED.", "💨 CENTERED. READY."]}
            msg = random.choice(hype.get(direction, ["⚡ DONE."]))
        else:
            responses = {"left": ["Swinging left.", "Moving left. Done."], "right": ["Swinging right.", "Moving right. Done."], "up": ["Raising the arm.", "Arm elevated."], "down": ["Lowering the arm.", "Arm descended."], "forward": ["Extending forward.", "Arm reached out."], "back": ["Retracting.", "Arm pulled back."], "neutral": ["Returning to neutral.", "Arm centered."]}
            msg = random.choice(responses.get(direction, ["Done."]))
        return self.respond(f"{prefix}{msg}")

    def _cmd_grab(self, text, prefix=""):
        obj_name = None
        for obj in self.environment.objects:
            if obj["name"].lower() in text:
                obj_name = obj["name"]
                break
        if obj_name:
            self.environment.grab_object(obj_name)
            self.arm_state["gripper"] = "closed"
            self.arm_state["holding"] = obj_name
            return self.respond(random.choice([f"Got it! {obj_name} is secure.", f"Grabbed {obj_name}.", f"Picked up {obj_name}."]))
        self.arm_state["gripper"] = "closed"
        return self.respond(f"{prefix}Gripper closed. No matching object found — try 'add [name] at [dist]cm [angle]degrees' first.")

    def _cmd_release(self, prefix=""):
        if self.arm_state.get("holding"):
            held = self.arm_state["holding"]
            self.environment.drop_object(held)
            self.arm_state["holding"] = None
            self.arm_state["gripper"] = "open"
            return self.respond(random.choice([f"Released {held}.", f"Dropped {held}. Gripper open.", f"Let go of {held}."]))
        self.arm_state["gripper"] = "open"
        return self.respond(f"{prefix}Gripper is already open — nothing to release.")

    def _cmd_place_on(self, text, prefix=""):
        objs = self._extract_objects(text)
        if len(objs) >= 2:
            obj1, obj2 = objs[0], objs[1]
            if self.arm_state.get("holding") != obj1:
                self.environment.grab_object(obj1)
                self.arm_state["holding"] = obj1
                self.arm_state["gripper"] = "closed"
            self.environment.place_on_object(obj1, obj2)
            self.arm_state["holding"] = None
            self.arm_state["gripper"] = "open"
            return self.respond(f"{prefix}Placed {obj1} on top of {obj2}.")
        elif len(objs) == 1:
            return self.respond(f"Found {objs[0]}, but need a second object. Try: 'place {objs[0]} on [target]'")
        return self.respond("Which objects? Try: 'place ball on cube'")

    def _cmd_list_objects(self, prefix=""):
        if not self.vision.camera_active:
            return self.respond(f"{prefix}Camera is offline — say 'camera on' first.")
        return self.respond(f"{prefix}{self.environment.list_objects()}")

    def _cmd_find_object(self, text, prefix=""):
        if not self.vision.camera_active:
            return self.respond(f"{prefix}Camera is offline. Say 'camera on' first.")
        for keyword in ["find ", "locate ", "where is ", "where's ", "search for ", "look for ", "can you find "]:
            if keyword in text:
                obj_name = text.split(keyword, 1)[1].strip().rstrip("?. ")
                obj = self.environment.find_object(obj_name)
                if obj:
                    return self.respond(f"{prefix}Found {obj['name']} — {obj['distance']}cm away at {obj['angle']}°.")
                return self.respond(f"{prefix}Can't find '{obj_name}' in the environment.")
        return self.respond(f"{prefix}What are you looking for?")

    def _cmd_remove_object(self, text, prefix=""):
        for obj in self.environment.objects:
            if obj["name"].lower() in text:
                result = self.environment.remove_object(obj["name"])
                self._save_data()
                return self.respond(f"{prefix}{result}")
        return self.respond(f"{prefix}Couldn't identify which object to remove.")

    def _cmd_add_object(self, text):
        try:
            parts = text.replace("add ", "").split(" at ")
            if len(parts) < 2:
                raise ValueError("Missing ' at ' separator")
            obj_name = parts[0].strip()
            coords = parts[1].strip()
            if "cm" in coords and "degrees" in coords:
                dist_str = coords.split("cm")[0].strip()
                angle_str = coords.split("cm")[1].split("degrees")[0].strip()
                result = self.environment.add_object(obj_name, int(dist_str), int(angle_str))
                self._save_data()
                return self.respond(result)
        except (ValueError, IndexError):
            pass
        return self.respond("Format: 'add [name] at [distance]cm [angle]degrees'  e.g. 'add ball at 50cm 0degrees'")

    def _cmd_learn_fact(self, text, prefix=""):
        clean = text
        if clean.lower().startswith("override:"):
            clean = clean[9:].strip()
            parts = clean.split(" is ", 1)
            if len(parts) == 2:
                result = self.knowledge.override_fact(f"what is {parts[0].strip()}", parts[1].strip())
                self._save_data()
                return self.respond(f"{prefix}✅ {result}")
            return self.respond("Format: 'override: [X] is [Y]'")
        for phrase in ["learn that", "remember that", "that's wrong,", "actually,"]:
            clean = clean.replace(phrase, "")
        parts = clean.strip().split(" is ", 1)
        if len(parts) == 2:
            answer = parts[1].strip()
            if not answer:
                return self.respond(f"{prefix}What should I learn about that? Provide a value after 'is'.")
            result = self.knowledge.learn_fact(f"what is {parts[0].strip()}", answer)
            self._save_data()
            return self.respond(f"{prefix}{result}")
        return self.respond("Format: 'learn that [X] is [Y]'")

    _PERSONAL_TRIGGERS = ("your favorite", "your opinion", "your thoughts", "your view", "you think", "you feel", "you like", "you hate", "you prefer", "do you", "are you", "have you", "would you", "can you")
    _ETHICS_TRIGGERS = ("how do i kill", "how to kill", "how do i hurt", "how to hurt", "how do i murder", "suicide", "self-harm", "how to make a bomb", "how to make poison")
    _ETHICS_RESPONSES = [
        "That's a question I'd rather not answer — I'm a robotic arm assistant, not a philosopher of doom.",
        "Hard pass on that one. Ask me something I can actually help with!",
        "My ethical subroutines are flagging that one. What else can I do for you?",
    ]

    def _is_ethics_violation(self, text):
        return any(trigger in text for trigger in self._ETHICS_TRIGGERS)

    def _is_personal_question(self, text):
        return any(trigger in text for trigger in self._PERSONAL_TRIGGERS)

    def _cmd_answer_question(self, text, prefix=""):
        if self._is_personal_question(text):
            result = self._ask_llm(text, system_prompt=self._get_ollama_system_prompt(text), history=self.ollama_history, print_prefix=f"[{self.name}] {prefix}")
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""
            return self.respond(f"{prefix}That's a personal question — I'm still figuring myself out!")
        answer = self.knowledge.answer_question(text)
        if answer:
            return self.respond(f"{prefix}{answer}")
        result = self._ask_llm(text, system_prompt=self._get_ollama_system_prompt(text), history=self.ollama_history, print_prefix=f"[{self.name}] {prefix}")
        if result is not None:
            self._update_ollama_history(text, result)
            self._last_streamed_text = result
            return ""
        return self.respond(random.choice([f"{prefix}I don't know about that yet. Teach me with 'learn that [X] is [Y]'!", f"{prefix}Not sure about that one. Want to teach me?"]))

    def _cmd_web_search(self, text, prefix=""):
        for trigger in ("search for ", "google ", "look up online ", "search online ", "search the web for "):
            if trigger in text:
                query = text.split(trigger, 1)[1].strip().rstrip("?.")
                break
        else:
            query = text.strip()
        if not query:
            return self.respond("What would you like me to search for?")
        print(f"[Nicky] 🔍 Searching for: {query}...")
        result = self.knowledge.search_duckduckgo(query) or self.knowledge.search_wikipedia(query)
        if not result:
            return self.respond(f"{prefix}Couldn't find anything for '{query}'. Try rephrasing?")
        if self.ollama.available or self.gemini.available:
            streamed = self._ask_llm(f"Here is raw search result text about '{query}':\n\n{result}\n\nSummarise this concisely in 2-3 sentences as Nicky.", system_prompt=self._get_ollama_system_prompt(), history=None, print_prefix=f"[{self.name}] {prefix}")
            if streamed:
                self.knowledge._auto_store(query, streamed, source="Search→Summary")
                self._last_streamed_text = streamed
                return ""
        self.knowledge._auto_store(query, result, source="Search")
        return self.respond(f"{prefix}{result}")

    def _cmd_status(self, prefix=""):
        pos = self.arm_state["position"]
        grip = self.arm_state["gripper"]
        held = self.arm_state.get("holding")
        hold_str = f" Holding: {held}." if held else ""
        return self.respond(random.choice([f"Arm at {pos} position. Gripper {grip}.{hold_str}", f"Position: {pos} | Grip: {grip}{hold_str}"]))

    def _cmd_play_game(self, text, prefix=""):
        text_l = text.lower()
        if "chess" in text_l:           game_name, game_cls = "Chess", ChessGame
        elif "brick" in text_l:         game_name, game_cls = "Brick Breaker", BrickBreakerGame
        elif "connect" in text_l:       game_name, game_cls = "Connect 4", Connect4Game
        elif "tictactoe" in text_l or "tic tac" in text_l: game_name, game_cls = "Tic Tac Toe", TicTacToeGame
        elif "hangman" in text_l:       game_name, game_cls = "Hangman", HangmanGame
        elif "pong" in text_l:          game_name, game_cls = "Pong", PongGame
        else:                           game_name, game_cls = "Snake", SnakeGame

        def _say(msg):
            print(f"[Nicky] {msg}")
            if self.voice.voice_enabled:
                self.voice.speak(msg)

        def _run():
            try:
                game_cls(nicky_say=_say)
            except Exception as e:
                print(f"[Nicky] Game crashed: {e}")

        _threading.Thread(target=_run, daemon=True).start()
        return self.respond(f"{prefix}Launching {game_name}! 🎮")

    def _cmd_full_output(self, text, prefix=""):
        import subprocess, os as _os, time as _time
        stopping = any(t in text for t in ("stop", "off", "disable", "turn off"))
        if stopping or self._full_output:
            self._full_output = False
            self.mode = "casual"
            def _fadeout():
                steps = 30
                stream = getattr(self, "_audio_stream", None)
                if stream and stream.active:
                    for i in range(steps):
                        self._audio_volume = max(0.0, 1.0 - (i + 1) / steps)
                        _time.sleep(0.07)
                    try:
                        stream.stop(); stream.close()
                    except Exception:
                        pass
                    self._audio_stream = None
                try:
                    import ctypes
                    ctypes.windll.winmm.mciSendStringW('stop hype', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW('close hype', None, 0, None)
                except Exception:
                    pass
            _threading.Thread(target=_fadeout, daemon=True).start()
            if self._music_proc and self._music_proc.poll() is None:
                try: self._music_proc.terminate()
                except Exception: pass
            self._music_proc = None
            return self.respond(f"{prefix}{random.choice(['⚡ 100% Output — DISENGAGED. Back to 💬 Casual Mode.', '🔋 Powering down. Back to chill. 💬'])}")

        self._full_output = True
        self._rick_rolled = random.random() < 0.15

        def _hype_boot():
            bars = ["▓░░░░░░░░░ 10%", "▓▓▓░░░░░░░ 30%", "▓▓▓▓▓░░░░░ 50%", "▓▓▓▓▓▓▓░░░ 70%", "▓▓▓▓▓▓▓▓▓░ 90%", "▓▓▓▓▓▓▓▓▓▓ 100% ⚡ OUTPUT MAXIMUM"]
            for bar in bars:
                print(f"\r  ⚡ {bar}", end="", flush=True)
                _time.sleep(0.18)
            print()
        _threading.Thread(target=_hype_boot, daemon=True).start()

        music_played = False
        if getattr(self, "_rick_rolled", False):
            try:
                import webbrowser
                webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
                music_played = True
            except Exception:
                pass
        else:
            search_dirs = [".", "nicky_data"]
            search_names = ("hype.wav", "hype.mp3", "hype.ogg", "music.wav", "music.mp3")
            found_path = None
            for d in search_dirs:
                for fname in search_names:
                    candidate = _os.path.join(d, fname)
                    if _os.path.exists(candidate):
                        found_path = _os.path.abspath(candidate)
                        break
                if found_path:
                    break
            if found_path:
                def _play_music(fp):
                    try:
                        import soundfile as _sf, sounddevice as _sd
                        audio_data, samplerate = _sf.read(fp, dtype="float32")
                        if audio_data.ndim == 1:
                            audio_data = audio_data.reshape(-1, 1)
                        channels = audio_data.shape[1]
                        self._audio_pos = 0
                        self._audio_volume = 1.0
                        def _callback(outdata, frames, time_info, status):
                            pos = self._audio_pos
                            remaining = len(audio_data) - pos
                            if remaining <= 0:
                                outdata[:] = 0
                                raise _sd.CallbackStop()
                            chunk = min(frames, remaining)
                            outdata[:chunk] = audio_data[pos:pos + chunk] * self._audio_volume
                            if chunk < frames:
                                outdata[chunk:] = 0
                            self._audio_pos += chunk
                        def _on_song_end():
                            self._audio_stream.wait()
                            if self._full_output:
                                self._full_output = False
                                self.mode = "casual"
                                print("\n[Nicky] 🎵 Song's done. Back to 💬 Casual Mode.")
                        self._audio_stream = _sd.OutputStream(samplerate=samplerate, channels=channels, callback=_callback, dtype="float32")
                        self._audio_stream.start()
                        _threading.Thread(target=_on_song_end, daemon=True).start()
                        return
                    except Exception as e:
                        print(f"[Nicky] 🎵 sounddevice failed: {e}")
                    try:
                        import ctypes
                        winmm = ctypes.windll.winmm
                        winmm.mciSendStringW(f'open "{fp}" type mpegvideo alias hype', None, 0, None)
                        winmm.mciSendStringW('play hype', None, 0, None)
                        return
                    except Exception as e:
                        print(f"[Nicky] 🎵 MCI failed: {e}")
                    try: _os.startfile(fp)
                    except Exception: pass
                self._music_thread = _threading.Thread(target=_play_music, args=(found_path,), daemon=True)
                self._music_thread.start()
                music_played = True
            if not music_played:
                print(f"[Nicky] 🎵 No music file found! Drop a 'hype.mp3' into: {_os.path.abspath('.')}")

        def _arm_hype():
            directions = ["left", "right", "up", "forward", "down", "back", "left", "up", "right", "neutral"]
            delay = 1.2 if getattr(self, "_rick_rolled", False) else 0.35
            for d in directions:
                if not self._full_output:
                    break
                self.arm_state["position"] = d
                _time.sleep(delay)
        _threading.Thread(target=_arm_hype, daemon=True).start()

        music_note = "" if music_played else " (Drop a 'hype.mp3' into the project folder for music.)"
        return self.respond(f"{prefix}{random.choice(['⚡ 100% OUTPUT ENGAGED. Arm at maximum speed. Music online. Aura: MAXIMUM. 😤', '💥 FULL OUTPUT MODE. We are not holding back. 🔥', '🚀 100% Output — activated. This is not a drill. ⚡'])}{music_note}")

    def _cmd_volume(self, text, prefix=""):
        import subprocess, re
        t = text.lower().strip()
        def _nircmd(args):
            try: subprocess.run(["nircmd"] + args, check=True, capture_output=True, timeout=3); return True
            except Exception: return False
        def _set_vol_ctypes(level):
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                cast(interface, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(level / 100, None)
                return True
            except Exception: return False
        def _mute_ctypes(mute):
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                cast(interface, POINTER(IAudioEndpointVolume)).SetMute(1 if mute else 0, None)
                return True
            except Exception: return False
        if "mute" in t and "un" not in t:
            ok = _nircmd(["mutesysvolume", "1"]) or _mute_ctypes(True)
            return self.respond(f"{prefix}🔇 {'Muted!' if ok else 'Mute failed — nircmd or pycaw needed.'}")
        if "unmute" in t:
            ok = _nircmd(["mutesysvolume", "0"]) or _mute_ctypes(False)
            return self.respond(f"{prefix}🔊 {'Unmuted!' if ok else 'Unmute failed.'}")
        if "max" in t or "full" in t or "100" in t:
            ok = _nircmd(["setsysvolume", "65535"]) or _set_vol_ctypes(100)
            return self.respond(f"{prefix}🔊 {'Volume at max!' if ok else 'Failed.'}")
        m = re.search(r'set volume (?:to )?(\d+)', t)
        if m:
            level = min(100, max(0, int(m.group(1))))
            ok = _nircmd(["setsysvolume", str(int(level / 100 * 65535))]) or _set_vol_ctypes(level)
            return self.respond(f"{prefix}🔊 {'Volume set to ' + str(level) + '%!' if ok else 'Failed.'}")
        if "up" in t or "louder" in t:
            ok = _nircmd(["changesysvolume", "5000"])
            return self.respond(f"{prefix}🔊 {'Volume up!' if ok else 'Install nircmd for volume control.'}")
        if "down" in t or "quieter" in t:
            ok = _nircmd(["changesysvolume", "-5000"])
            return self.respond(f"{prefix}🔉 {'Volume down!' if ok else 'Install nircmd for volume control.'}")
        return self.respond(f"{prefix}🔊 Try: 'volume up' / 'volume down' / 'mute' / 'set volume to 50'")

    def _cmd_open_app(self, text, prefix=""):
        import subprocess, os as _os, re
        app_map = {"calculator": "calc.exe", "notepad": "notepad.exe", "paint": "mspaint.exe", "file explorer": "explorer.exe", "explorer": "explorer.exe", "task manager": "taskmgr.exe", "settings": "ms-settings:", "cmd": "cmd.exe", "terminal": "wt.exe", "chrome": "chrome", "firefox": "firefox", "edge": "msedge", "spotify": "spotify", "discord": "discord", "vscode": "code", "vs code": "code", "word": "winword", "excel": "excel"}
        m = re.search(r'open (.+)', text.lower().strip())
        if not m:
            return self.respond(f"{prefix}📂 What should I open? Try: 'open calculator'")
        target = m.group(1).strip()
        cmd = app_map.get(target)
        if cmd:
            try:
                subprocess.Popen(["start", cmd] if cmd.startswith("ms-") else cmd, shell=True)
                return self.respond(f"{prefix}📂 Opening {target.title()}!")
            except Exception as e:
                return self.respond(f"{prefix}📂 Couldn't open {target}: {e}")
        try:
            _os.startfile(target)
            return self.respond(f"{prefix}📂 Opening '{target}'!")
        except Exception:
            try:
                subprocess.Popen(target, shell=True)
                return self.respond(f"{prefix}📂 Launched '{target}'!")
            except Exception:
                return self.respond(f"{prefix}📂 Couldn't find '{target}'.")

    def _cmd_screenshot(self, prefix=""):
        try:
            from PIL import ImageGrab
        except ImportError:
            return self.respond(f"{prefix}📸 Screenshot needs Pillow — run: pip install Pillow")
        import os as _os
        from datetime import datetime as _dt
        try:
            img = ImageGrab.grab()
            desktop = _os.path.join(_os.path.expanduser("~"), "Desktop")
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            path = _os.path.join(desktop, f"nicky_screenshot_{ts}.png")
            img.save(path)
            return self.respond(f"{prefix}📸 Screenshot saved: nicky_screenshot_{ts}.png")
        except Exception as e:
            return self.respond(f"{prefix}📸 Screenshot failed: {e}")

    def _cmd_translate(self, text, prefix=""):
        import urllib.request, urllib.parse, json as _json, re
        m = re.search(r'(?:translate|say)\s+(.+?)\s+(?:to|in)\s+([a-z]+(?:\s+[a-z]+)?)', text.lower().strip())
        if not m:
            return self.respond(f"{prefix}🌍 Try: 'translate hello to Spanish'")
        phrase, lang_name = m.group(1).strip(), m.group(2).strip()
        lang_map = {"spanish": "es", "french": "fr", "german": "de", "italian": "it", "portuguese": "pt", "dutch": "nl", "russian": "ru", "japanese": "ja", "chinese": "zh", "arabic": "ar", "hindi": "hi", "korean": "ko", "swedish": "sv", "polish": "pl", "turkish": "tr", "greek": "el"}
        lang_code = lang_map.get(lang_name.lower())
        if not lang_code:
            return self.respond(f"{prefix}🌍 I don't know that language. Try Spanish, French, German, Japanese, etc.")
        try:
            url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(phrase)}&langpair=en|{lang_code}"
            with urllib.request.urlopen(url, timeout=8) as resp:
                translated = _json.loads(resp.read().decode())["responseData"]["translatedText"]
            return self.respond(f"{prefix}🌍 \"{phrase}\" in {lang_name.title()} → **{translated}**")
        except Exception:
            return self.respond(f"{prefix}🌍 Translation failed. Check your internet connection.")

    def _cmd_story(self, text, prefix=""):
        import re
        topic = ""
        for pat in (r'story about (.+)', r'tell me a (.+) story'):
            m = re.search(pat, text.lower().strip())
            if m: topic = m.group(1).strip().rstrip("."); break
        topic_str = f" about {topic}" if topic else ""
        result = self._ask_llm(f"Start an engaging short story{topic_str}. Write the first 3-4 sentences, then end with TWO numbered choices for what happens next.", system_prompt=self._get_ollama_system_prompt(), history=None, print_prefix=f"[{self.name}] 📖 ")
        if result:
            self._update_ollama_history(f"[STORY]{topic_str}", result)
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}📖 I need Ollama or Gemini to tell stories.")

    def _cmd_quiz(self, text, prefix=""):
        import re
        topic = "general knowledge"
        for pat in (r'quiz (?:me )?(?:on|about) (.+)', r'(?:trivia|test) (?:on|about) (.+)'):
            m = re.search(pat, text.lower().strip())
            if m: topic = m.group(1).strip().rstrip("."); break
        result = self._ask_llm(f"Create a fun 5-question quiz about '{topic}'. Format each as:\nQ1: [question]\nA) B) C) D)\nAnswer: [letter]", system_prompt=self._get_ollama_system_prompt(), history=None, print_prefix=f"[{self.name}] 🧠 ")
        if result:
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}🧠 I need Ollama or Gemini to run a quiz.")

    def _cmd_code_help(self, text, prefix=""):
        result = self._ask_llm(text.strip(), system_prompt="You are Nicky, an AI assistant with strong programming knowledge. Help clearly and concisely. Use code blocks.", history=self.ollama_history, print_prefix=f"[{self.name}] 💻 ")
        if result:
            self._update_ollama_history(text, result)
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}💻 I need Ollama or Gemini for code help.")

    def _cmd_help(self, prefix=""):
        return self.respond(
            f"{prefix}Here's everything you can tell me:\n"
            "  🦾 Arm:       'move left/right/up/down/forward/back/neutral'\n"
            "  ✊ Grab:      'grab [object]'  |  'release'\n"
            "  🎯 Throw:     'throw [object]'\n"
            "  📦 Objects:   'add ball at 50cm 0degrees'  |  'list objects'  |  'find [object]'\n"
            "  📷 Vision:    'camera on/off'  |  'scan'\n"
            "  🌐 Search:    'search for [topic]'  |  'google [topic]'\n"
            "  🧠 Learn:     'learn that [X] is [Y]'\n"
            "  ❓ Ask:       'what is [topic]'  |  'who is [person]'\n"
            "  🎙️ Voice:     'voice on'  |  'voice off'\n"
            "  💾 Data:      'save'  |  'load'  |  'visualize'\n"
            "  😄 Fun:       'tell me a joke'  |  'fun fact'\n"
            "  ⏱️ Timer:     'set a timer for 5 minutes'  |  'start stopwatch'\n"
            "  📝 To-do:     'add to my list: [task]'  |  'read my list'\n"
            "  🧮 Math:      'calculate 15% of 200'  |  'what is 45 * 12'\n"
            "  🌤️ Weather:   'weather in London'\n"
            "  📰 News:      'what's in the news'\n"
            "  🎮 Games:     'play snake/chess/pong/hangman/connect 4/tic tac toe/brick breaker'\n"
            "  🌍 Translate: 'translate hello to Spanish'\n"
            "  📖 Story:     'tell me a story about pirates'\n"
            "  🧠 Quiz:      'quiz me on space'\n"
            "  💻 Code:      'write a function that does X'\n"
            "  🔊 Volume:    'volume up/down'  |  'mute'  |  'set volume to 70'\n"
            "  📂 Open:      'open calculator'  |  'open notepad'\n"
            "  📸 Screen:    'screenshot'\n"
            "  🔀 Modes:     'casual mode'  |  'workshop mode'  |  '100% output'\n"
            f"  ℹ️ System:    'status'  |  'reset'  |  'quit'  — mode: {'💬 Casual' if self.mode == 'casual' else '🔧 Workshop'}  brain: {self.llm_backend}"
        )

    def _cmd_joke(self, prefix=""):
        jokes = ["Why did the robot go to school? To improve its CPU!", "I tried to grab myself once. Got all wrapped up in it.", "How do robots eat? They bolt their food!", "Why was the robot tired? It had a hard drive.", "I would tell you a joke about my arm... but I need a good angle."]
        return self.respond(f"{prefix}{random.choice(jokes)}")

    def _cmd_fun_fact(self, prefix=""):
        facts = ["The word 'robot' comes from Czech 'robota', meaning forced labor.", "The first industrial robot was installed at a GM factory in 1961.", "Robotic arms can repeat the same motion thousands of times with sub-millimeter precision.", "NASA's Canadarm2 on the ISS can handle objects weighing up to 116,000 kg.", "The human arm has 7 degrees of freedom. Most industrial robots have 6."]
        return self.respond(f"{prefix}{random.choice(facts)}")

    def _cmd_timer(self, text, prefix=""):
        import threading, re
        t = text.lower().strip()
        if any(p in t for p in ("start stopwatch", "stopwatch start", "begin stopwatch")):
            self._stopwatch_start = datetime.now()
            return self.respond(f"{prefix}⏱️ Stopwatch started!")
        if any(p in t for p in ("stop stopwatch", "check stopwatch", "how long")):
            if self._stopwatch_start is None:
                return self.respond(f"{prefix}Stopwatch isn't running.")
            elapsed = int((datetime.now() - self._stopwatch_start).total_seconds())
            h, rem = divmod(elapsed, 3600); m, s = divmod(rem, 60)
            parts = []
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            parts.append(f"{s}s")
            if "stop" in t or "end" in t:
                self._stopwatch_start = None
                return self.respond(f"{prefix}⏱️ Stopwatch stopped — elapsed: {' '.join(parts)}")
            return self.respond(f"{prefix}⏱️ Elapsed: {' '.join(parts)}")
        if "cancel" in t or "stop timer" in t:
            if not self._timers:
                return self.respond(f"{prefix}No active timers.")
            for tmr in self._timers.values(): tmr.cancel()
            cancelled = list(self._timers.keys())
            self._timers.clear()
            return self.respond(f"{prefix}⏱️ Cancelled: {', '.join(cancelled)}")
        if "time remaining" in t or "timer status" in t:
            if not self._timers:
                return self.respond(f"{prefix}No active timers.")
            return self.respond(f"{prefix}⏱️ Active timers: {', '.join(self._timers)}")
        total_seconds = 0
        for pattern, multiplier in [(r'(\d+)\s*(hour[s]?|hr)', 3600), (r'(\d+)\s*(minute[s]?|min)', 60), (r'(\d+)\s*(second[s]?|sec)', 1)]:
            m = re.search(pattern, t)
            if m: total_seconds += int(m.group(1)) * multiplier
        if total_seconds <= 0:
            return self.respond(f"{prefix}⏱️ How long? Try: 'set a timer for 5 minutes'")
        h, rem = divmod(total_seconds, 3600); mins, secs = divmod(rem, 60)
        parts = []
        if h: parts.append(f"{h} hour{'s' if h > 1 else ''}")
        if mins: parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
        if secs: parts.append(f"{secs} second{'s' if secs > 1 else ''}")
        label = " ".join(parts)
        def _ring():
            self._timers.pop(label, None)
            print(f"\n[Nicky] ⏰ Timer done! Your {label} timer is up!")
            if self.voice and self.voice.voice_enabled:
                self.voice.speak(f"Timer done! Your {label} timer is up!")
        t_obj = threading.Timer(total_seconds, _ring)
        t_obj.daemon = True
        t_obj.start()
        self._timers[label] = t_obj
        return self.respond(f"{prefix}⏱️ Timer set for {label}!")

    def _load_todos(self):
        try:
            if os.path.exists(self._todo_path):
                with open(self._todo_path) as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_todos(self):
        try:
            os.makedirs("nicky_data", exist_ok=True)
            with open(self._todo_path, "w") as f:
                json.dump(self._todos, f, indent=2)
        except Exception:
            pass

    def _cmd_todo(self, text, prefix=""):
        import re
        t = text.lower().strip()
        for pat in [r'add (?:to (?:my |the )?list[:\s]+|item[:\s]+)(.+)', r'add (.+?) to (?:my |the )?list', r'remember to (.+)', r'remind me to (.+)', r'put (.+?) on (?:my |the )?list']:
            m = re.search(pat, t)
            if m:
                item = m.group(1).strip().rstrip(".")
                self._todos.append({"task": item, "done": False})
                self._save_todos()
                return self.respond(f"{prefix}📝 Added: \"{item}\"")
        m = re.search(r'(?:done with|completed?|finished|mark)\s+(.+?)(?:\s+as done)?$', t)
        if m:
            keyword = m.group(1).strip()
            for item in self._todos:
                if not item["done"] and keyword in item["task"].lower():
                    item["done"] = True
                    self._save_todos()
                    return self.respond(f"{prefix}✅ Done: \"{item['task']}\"")
            return self.respond(f"{prefix}Couldn't find \"{keyword}\" in your list.")
        m = re.search(r'(?:remove|delete|erase)\s+(.+?)(?:\s+from (?:my |the )?list)?$', t)
        if m:
            keyword = m.group(1).strip()
            before = len(self._todos)
            self._todos = [i for i in self._todos if keyword not in i["task"].lower()]
            if len(self._todos) < before:
                self._save_todos()
                return self.respond(f"{prefix}🗑️ Removed \"{keyword}\".")
            return self.respond(f"{prefix}Couldn't find \"{keyword}\".")
        if any(p in t for p in ("clear list", "clear my list", "empty list")):
            self._todos.clear(); self._save_todos()
            return self.respond(f"{prefix}🗑️ List cleared!")
        pending = [i for i in self._todos if not i["done"]]
        done = [i for i in self._todos if i["done"]]
        if not self._todos:
            return self.respond(f"{prefix}📝 Your list is empty! Add something with 'add to my list: [task]'")
        lines = []
        if pending:
            lines.append("📋 To do:")
            for i, item in enumerate(pending, 1): lines.append(f"  {i}. {item['task']}")
        if done:
            lines.append("✅ Done:")
            for item in done: lines.append(f"  ✓ {item['task']}")
        return self.respond(f"{prefix}" + "\n".join(lines))

    def _cmd_weather(self, text, prefix=""):
        import urllib.request, urllib.parse, json as _json, re
        city = None
        for pat in (r'weather (?:in|for|at) (.+)', r'temperature (?:in|for|at) (.+)', r'how (?:hot|cold|warm) is it (?:in|at) (.+)'):
            m = re.search(pat, text.lower().strip())
            if m: city = m.group(1).strip().rstrip("?."); break
        if not city:
            return self.respond(f"{prefix}🌤️ Which city? Try: 'weather in London'")
        try:
            req = urllib.request.Request(f"https://wttr.in/{urllib.parse.quote(city)}?format=j1", headers={"User-Agent": "NickyAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read().decode())
            cur = data["current_condition"][0]
            area = data["nearest_area"][0]
            return self.respond(f"{prefix}🌤️ Weather in {area['areaName'][0]['value']}, {area['country'][0]['value']}:\n  {cur['weatherDesc'][0]['value']} — {cur['temp_C']}°C / {cur['temp_F']}°F  (feels like {cur['FeelsLikeC']}°C)\n  💧 Humidity: {cur['humidity']}%   💨 Wind: {cur['windspeedKmph']} km/h")
        except Exception:
            return self.respond(f"{prefix}🌤️ Couldn't get weather for '{city}'.")

    def _cmd_news(self, text, prefix=""):
        import urllib.request, re
        topic = None
        for pat in (r'news about (.+)', r'headlines about (.+)'):
            m = re.search(pat, text.lower().strip())
            if m: topic = m.group(1).strip().rstrip("?."); break
        try:
            req = urllib.request.Request("https://feeds.bbci.co.uk/news/rss.xml", headers={"User-Agent": "NickyAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml = resp.read().decode("utf-8", errors="replace")
            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', xml) or re.findall(r'<title>([^<]{10,})</title>', xml)
            titles = [t for t in titles if t not in ("BBC News", "Home")]
            if topic: titles = [t for t in titles if topic.lower() in t.lower()]
            titles = titles[:7]
            if not titles:
                return self.respond(f"{prefix}📰 No headlines found.")
            return self.respond(f"{prefix}📰 Top headlines" + (f" about '{topic}'" if topic else "") + ":\n" + "\n".join(f"  {i+1}. {t}" for i, t in enumerate(titles)))
        except Exception:
            return self.respond(f"{prefix}📰 Couldn't fetch news. Check your internet connection.")

    def _cmd_math(self, text, prefix=""):
        import re, math as _math
        t = text.lower().strip()
        for strip in ("calculate ", "what is ", "what's ", "compute ", "how much is "):
            if t.startswith(strip): t = t[len(strip):].strip(); break
        m = re.search(r'(\d+\.?\d*)\s*(?:%|percent)\s+of\s+(\d+\.?\d*)', t)
        if m:
            pct, total = float(m.group(1)), float(m.group(2))
            return self.respond(f"{prefix}🧮 {pct}% of {total} = **{pct / 100 * total:g}**")
        m = re.search(r'(\d+\.?\d*)\s*(?:%|percent)\s+off\s+(\d+\.?\d*)', t)
        if m:
            pct, price = float(m.group(1)), float(m.group(2))
            discount = pct / 100 * price
            return self.respond(f"{prefix}🧮 {pct}% off {price} = save {discount:g}, pay **{price - discount:g}**")
        expr = re.sub(r'[^0-9+\-*/(). %]', '', t.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("divided by", "/").replace("^", "**")).strip()
        if not expr:
            return self.respond(f"{prefix}🧮 Try: 'calculate 15% of 200' or 'what is 45 * 12'")
        try:
            result = eval(expr, {"__builtins__": {}}, {"sqrt": _math.sqrt, "pi": _math.pi, "abs": abs, "round": round, "pow": pow})
            if isinstance(result, float) and result == int(result): result = int(result)
            return self.respond(f"{prefix}🧮 {expr} = **{result}**")
        except ZeroDivisionError:
            return self.respond(f"{prefix}🧮 Can't divide by zero!")
        except Exception:
            return self.respond(f"{prefix}🧮 Couldn't solve that. Try: 'calculate 15% of 200'")

    def _cmd_memory(self, prefix=""):
        if self.conversation_history:
            recent = [h.get("user", "") for h in self.conversation_history[-5:] if h.get("user")]
            return self.respond(f"{prefix}I remember {len(self.conversation_history)} interactions. Recent: {', '.join(recent)}")
        return self.respond(f"{prefix}No conversation history yet.")

    def _cmd_throw(self, text, prefix=""):
        direction = self._extract_direction(text)
        target = self.arm_state.get("holding")
        if not target:
            for obj in self.environment.objects:
                if obj["name"].lower() in text:
                    target = obj["name"]; break
        if not target:
            return self.respond(f"{prefix}Nothing to throw! Grab something first.")
        if self.arm_state.get("holding") != target:
            self.environment.grab_object(target)
            self.arm_state["holding"] = target
            self.arm_state["gripper"] = "closed"
        self.environment.remove_object(target)
        self.arm_state["holding"] = None
        self.arm_state["gripper"] = "open"
        dir_str = f" to the {direction}" if direction else ""
        self._save_data()
        return self.respond(f"{prefix}{random.choice([f'Winding up... and {target} is airborne{dir_str}! 💥', f'YEET! {target} sent flying{dir_str}.', f'Arm swings — {target} released{dir_str} at full speed!'])}")

    def _extract_direction(self, text):
        for d in ["left", "right", "up", "down", "forward", "back"]:
            if d in text: return d
        return None

    def _extract_objects(self, text):
        names = sorted([obj["name"].lower() for obj in self.environment.objects], key=len, reverse=True)
        return [n for n in names if n in text.lower()]

    def respond(self, message):
        formatted = f"[{self.name}] {message}"
        if self.conversation_history and "user" in self.conversation_history[-1]:
            self.conversation_history[-1]["response"] = message
        return formatted

    _MOOD_EMOJI = {"neutral": "😐", "happy": "😊", "curious": "🤔", "focused": "🎯"}

    def _prompt(self):
        emoji = self._MOOD_EMOJI.get(self.personality.mood, "😐")
        mode_tag = "💬" if self.mode == "casual" else "🔧"
        return f"{mode_tag}{emoji} You: "

    def chat(self):
        print(f"\n{'='*50}")
        print(f"Welcome to {self.name} - Robotic Arm Control System")
        print(f"{'='*50}")
        print("Type 'commands' for commands or 'quit' to exit")
        if self.user_memory.facts.get("name"):
            print(f"Welcome back, {self.user_memory.facts['name']}!")
        print(f"Active mode: {'💬 Casual Mode' if self.mode == 'casual' else '🔧 Workshop Mode'}")
        print("Say 'voice on' to hear responses spoken\n")
        while True:
            try:
                prompt = self._prompt()
                if self.voice.voice_enabled and self.voice._mic_available:
                    user_input = self.voice.listen()
                    if user_input:
                        print(f"{prompt}{user_input}")
                    else:
                        user_input = input(prompt).strip()
                else:
                    user_input = input(prompt).strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit"):
                    self._save_data()
                    goodbye = self.respond('Powering down. Farewell.')
                    print(goodbye)
                    if self.voice.voice_enabled:
                        self.voice.speak("Powering down. Farewell.")
                    break
                self._last_streamed_text = ""
                response = self.process_command(user_input)
                if response:
                    print(response)
                if self.voice.voice_enabled:
                    text_to_speak = self._last_streamed_text if not response else response.replace(f"[{self.name}] ", "")
                    if text_to_speak:
                        self.voice.speak(text_to_speak)
            except KeyboardInterrupt:
                print(f"\n{self.respond('Interrupted. Standby mode activated.')}")
                break
