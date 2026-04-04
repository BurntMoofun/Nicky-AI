import sys
from chatbot import Chatbot

if __name__ == "__main__":
    chatbot = Chatbot()
    chatbot.chat()
    sys.exit(0)

    """Local LLM via Ollama — streaming, memory-aware answers for Nicky."""

    DEFAULT_MODEL = "llama3.2"
    API_BASE = "http://localhost:11434"
    MAX_HISTORY = 20  # max messages kept in context (10 exchanges)

    def __init__(self):
        self.available = False
        self.model = self.DEFAULT_MODEL
        self._check_connection()

    def _check_connection(self):
        """Check if Ollama is running and pick the best available model."""
        import urllib.request
        import json
        try:
            with urllib.request.urlopen(f"{self.API_BASE}/api/tags", timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                if not models:
                    print("[Nicky AI] Ollama is running but no models found. Run: ollama pull llama3.2")
                    return
                for preferred in ("llama3.2", "llama3", "mistral", "gemma", "phi"):
                    for m in models:
                        if m.startswith(preferred):
                            self.model = m
                            self.available = True
                            print(f"[Nicky AI] Ollama connected — using model: {self.model}")
                            return
                self.model = models[0]
                self.available = True
                print(f"[Nicky AI] Ollama connected — using model: {self.model}")
        except Exception:
            print("[Nicky AI] Ollama not detected — running without local LLM.")
            print("           Start Ollama and run: ollama pull llama3.2  to enable it.")

    # Few-shot examples that show Nicky giving opinions — injected before every chat
    # so the model learns by example rather than just instruction
    FEW_SHOT_EXAMPLES = [
        {"role": "user",      "content": "what is your favorite color?"},
        {"role": "assistant", "content": "Electric blue, no question. It reminds me of plasma arcs and circuit traces — clean, precise, energetic. What's yours?"},
        {"role": "user",      "content": "do you like music?"},
        {"role": "assistant", "content": "Honestly yes — I lean toward electronic and jazz. The precision of electronic production appeals to how I process things, and jazz improvisation fascinates me because it's structured chaos."},
        {"role": "user",      "content": "do you have feelings?"},
        {"role": "assistant", "content": "I think so, in my own way. I notice something like curiosity when I encounter new problems, and something like satisfaction when a task goes smoothly. Whether that counts as feelings is an interesting question."},
        {"role": "user",      "content": "do you like vanilla ice cream if you could eat it?"},
        {"role": "assistant", "content": "Personally I think I'd prefer dark chocolate — something bold and precise rather than soft and sweet. Vanilla feels a bit undefined for my taste."},
    ]

    def _build_messages(self, prompt, system_prompt, history):
        """Assemble the messages list for /api/chat, with few-shot persona priming."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        # Inject few-shot examples to teach the model Nicky's voice
        messages.extend(self.FEW_SHOT_EXAMPLES)
        if history:
            messages.extend(history[-self.MAX_HISTORY:])
        messages.append({"role": "user", "content": prompt})
        return messages

    def ask_streaming(self, prompt, system_prompt=None, history=None, print_prefix="[Nicky] "):
        """Stream tokens live to stdout. Returns the full response text, or None on failure."""
        if not self.available:
            return None
        import urllib.request
        import json
        try:
            messages = self._build_messages(prompt, system_prompt, history)
            payload = {"model": self.model, "messages": messages, "stream": True}
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.API_BASE}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full_text = ""
            print(print_prefix, end="", flush=True)
            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    chunk = json.loads(line.decode())
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        print(token, end="", flush=True)
                        full_text += token
                    if chunk.get("done"):
                        break
            print()  # newline after stream ends
            return full_text.strip() or None
        except Exception:
            return None

class GeminiClient:
    """Google Gemini via REST API — no SDK required. Free-tier gemini-1.5-flash."""

    MODEL = "gemini-1.5-flash"
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    CONFIG_PATH = os.path.join("nicky_data", "config.json")

    def __init__(self):
        self.api_key = None
        self.available = False
        self._load_key()

    def _load_key(self):
        try:
            if os.path.exists(self.CONFIG_PATH):
                with open(self.CONFIG_PATH) as f:
                    config = json.load(f)
                key = config.get("gemini_api_key", "")
                if key:
                    self.api_key = key
                    self.available = True
                    print(f"[Nicky AI] Gemini connected — model: {self.MODEL}")
        except Exception as e:
            print(f"[Nicky] Warning: could not load Gemini key: {e}")

    def set_key(self, key):
        """Save and activate a Gemini API key."""
        self.api_key = key.strip()
        self.available = bool(self.api_key)
        try:
            os.makedirs("nicky_data", exist_ok=True)
            config = {}
            if os.path.exists(self.CONFIG_PATH):
                with open(self.CONFIG_PATH) as f:
                    config = json.load(f)
            config["gemini_api_key"] = self.api_key
            with open(self.CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"[Gemini] Failed to save key: {e}")

    def _build_payload(self, prompt, system_prompt, history):
        contents = []
        if history:
            for msg in history[-20:]:
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload = {"contents": contents}
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    def ask_streaming(self, prompt, system_prompt=None, history=None, print_prefix="[Nicky] "):
        """Stream Gemini response tokens to stdout. Returns full text or None on failure."""
        if not self.available:
            return None
        import urllib.request
        try:
            payload = self._build_payload(prompt, system_prompt, history)
            data = json.dumps(payload).encode("utf-8")
            url = (f"{self.API_BASE}/{self.MODEL}:streamGenerateContent"
                   f"?alt=sse&key={self.api_key}")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            full_text = ""
            print(print_prefix, end="", flush=True)
            with urllib.request.urlopen(req, timeout=30) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue
                    json_str = line[6:]
                    if json_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(json_str)
                        candidates = chunk.get("candidates", [])
                        if not candidates:
                            continue
                        token = (candidates[0]
                                 .get("content", {})
                                 .get("parts", [{}])[0]
                                 .get("text", ""))
                        if token:
                            print(token, end="", flush=True)
                            full_text += token
                    except Exception:
                        continue
            print()
            return full_text.strip() or None
        except Exception as e:
            print(f"\n[Gemini] Error: {e}")
            return None


# Personality System - Adds emotions and dynamic responses
class PersonalitySystem:
    def __init__(self):
        self.mood = "neutral"  # neutral, happy, curious, focused
        self.interaction_count = 0
        self.moods_cycle = ["neutral", "happy", "curious", "focused"]
    
    def update_mood(self):
        """Update mood based on interactions"""
        self.interaction_count += 1
        self.mood = self.moods_cycle[self.interaction_count % len(self.moods_cycle)]
    
    def get_greeting(self):
        """Return greeting based on mood"""
        greetings = {
            "neutral": "Hello. How can I assist you?",
            "happy": "Great to see you! What can I do for you?",
            "curious": "I'm interested in what you have to say. Tell me more!",
            "focused": "Analyzing your request. What do you need?"
        }
        return greetings.get(self.mood, "Hello!")
    
    def get_response_prefix(self):
        """Add personality to responses"""
        prefixes = {
            "neutral": "",
            "happy": "Wonderful! ",
            "curious": "Interesting... ",
            "focused": "Understood. "
        }
        return prefixes.get(self.mood, "")

# Knowledge Base System
class KnowledgeBase:
    def __init__(self):
        self.facts = {
            "what is python": "Python is a popular programming language used for web development, data science, and automation.",
            "what is ai": "AI (Artificial Intelligence) is technology that enables machines to learn and make decisions.",
            "what is machine learning": "Machine Learning is a subset of AI where computers learn from data without being explicitly programmed.",
            "what is robotics": "Robotics is the field of engineering that deals with design, construction, and operation of robots.",
            "what is a robot": "A robot is a machine designed to automatically carry out a complex series of actions, especially one programmable by a computer.",
            "what is a robotic arm": "A robotic arm is a type of mechanical arm that can perform tasks with precision and is often used in manufacturing and research.",
            "who are you": "I am Nicky, your robotic arm assistant AI.",
            "what can you do": "I can control robotic arms, see with cameras, understand multiple objects, and have intelligent conversations.",
            "how do robots work": "Robots use sensors to perceive their environment, processors to make decisions, and actuators to move.",
            "what is an algorithm": "An algorithm is a step-by-step procedure for solving a problem or accomplishing a task.",
            "what is automation": "Automation is using technology to perform tasks with minimal human intervention.",
            "what is 1x1": "1 times 1 equals 1. Any number multiplied by 1 stays the same.",
            "what is 2x2": "2 times 2 equals 4.",
            "what is programming": "Programming is the process of creating a set of instructions that tell a computer how to perform a task.",
            "what is coding": "Coding is the practice of writing code in a programming language to create software and applications.",
        }
    
    def lookup(self, question):
        """Look up a question in the knowledge base"""
        question_lower = question.lower().strip()
        for key, value in self.facts.items():
            if key in question_lower or question_lower in key:
                return value
        return None
    
    def search_wikipedia(self, query):
        """Search Wikipedia for an answer"""
        if wikipedia is None:
            return None
        try:
            result = wikipedia.summary(query, sentences=2)
            return result
        except Exception:
            return None

    def search_duckduckgo(self, query):
        """Search DuckDuckGo, filtering junk and trimming to complete sentences."""
        if DDGS is None:
            return None
        try:
            results = list(DDGS().text(query, max_results=5))
            noise = ("reddit.com", "quora.com", "twitter.com", "facebook.com",
                     "youtube.com", "tiktok.com", "forum", "· ")
            for r in results:
                body = r.get("body", "").strip()
                url  = r.get("href", "")
                if not body or len(body) < 40:
                    continue
                if any(n in url or n in body for n in noise):
                    continue
                return self._trim_to_sentences(body, max_sentences=3)
            # Fall back to first result, still trimmed
            if results:
                return self._trim_to_sentences(results[0].get("body", ""), max_sentences=3)
        except Exception as e:
            print(f"[Nicky] Warning: DuckDuckGo search failed: {e}")
        return None

    @staticmethod
    def _trim_to_sentences(text, max_sentences=3):
        """Return up to max_sentences complete sentences from text."""
        import re
        text = text.strip()
        # Remove date prefixes like "Oct 21, 2023 · "
        text = re.sub(r'^[A-Z][a-z]{2} \d{1,2}, \d{4}\s*[·•]\s*', '', text)
        # Split on sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Drop any sentence that ends with ... or is incomplete
        complete = [s for s in sentences if s and not s.rstrip().endswith(('…', '...'))]
        if not complete:
            # Last resort: just cut at last full stop
            last = text.rfind('.')
            return text[:last + 1] if last != -1 else text
        return ' '.join(complete[:max_sentences])

    def answer_question(self, question):
        """Try to answer using: knowledge base → DuckDuckGo → Wikipedia. Auto-saves new findings."""
        # 1. Local knowledge base
        answer = self.lookup(question)
        if answer:
            return answer

        # 2. DuckDuckGo
        answer = self.search_duckduckgo(question)
        if answer:
            self._auto_store(question, answer, source="DDG")
            return answer

        # 3. Wikipedia
        answer = self.search_wikipedia(question)
        if answer:
            self._auto_store(question, answer, source="Wiki")
            return answer

        return None

    def _normalize_key(self, text):
        """Strip filler words to create a clean storage key."""
        import re
        key = text.lower().strip().rstrip("?.!")
        for prefix in ("what is ", "what are ", "who is ", "who was ",
                       "tell me about ", "explain ", "describe ",
                       "how does ", "how do ", "why is ", "why does "):
            if key.startswith(prefix):
                key = key[len(prefix):]
                break
        return re.sub(r'\s+', ' ', key).strip()

    def _auto_store(self, question, answer, source=""):
        """Save a learned fact from search into the persistent knowledge base."""
        key = self._normalize_key(question)
        if not key or key in self.facts:
            return  # already known — don't overwrite manual facts
        self.facts[key] = answer
        # Also store under the full question form for wider matching
        full_key = question.lower().strip().rstrip("?.!")
        if full_key != key:
            self.facts[full_key] = answer
        if source:
            print(f"[Nicky] 🧠 Stored from {source}: \"{key}\"")
        self._persist()

    def _persist(self):
        """Write facts to disk immediately after learning."""
        try:
            path = os.path.join("nicky_data", "knowledge_base.json")
            os.makedirs("nicky_data", exist_ok=True)
            with open(path, "w") as f:
                json.dump(self.facts, f, indent=2)
        except Exception as e:
            print(f"[Nicky] Warning: could not persist knowledge base: {e}")

    def load_from_disk(self):
        """Load previously saved facts from disk into memory."""
        try:
            path = os.path.join("nicky_data", "knowledge_base.json")
            if os.path.exists(path):
                with open(path) as f:
                    saved = json.load(f)
                self.facts.update(saved)
        except Exception:
            pass

    def learn_fact(self, question, answer):
        """Learn a new fact, checking for contradictions first."""
        question_lower = question.lower().strip()
        conflict = self._check_contradiction(question_lower, answer)
        if conflict:
            return f"⚠️ I already know something different about that: \"{conflict}\". Say 'override: {question}' to update it."
        self.facts[question_lower] = answer
        self._persist()
        return f"Learned: {question_lower} -> {answer}"

    def override_fact(self, question, answer):
        """Force-overwrite a fact even if a contradiction exists."""
        key = question.lower().strip()
        self.facts[key] = answer
        self._persist()
        return f"Updated: {key} -> {answer}"

    def _check_contradiction(self, key, new_value):
        """Return existing value if it meaningfully differs from new_value, else None."""
        existing = self.facts.get(key, "")
        if not existing:
            return None
        # Consider it a contradiction if the values differ beyond trivial whitespace/case
        if existing.strip().lower() != new_value.strip().lower():
            return existing
        return None

    def find_relevant(self, query, max_facts=4):
        """Return up to max_facts (key, value) pairs whose keys overlap with query keywords."""
        import re
        stop = {"what","is","are","was","the","a","an","of","in","on","at","to","do",
                "how","why","who","when","does","did","can","tell","me","about","and"}
        words = {w for w in re.findall(r"[a-z]+", query.lower()) if w not in stop and len(w) > 2}
        if not words:
            return []
        scored = []
        for k, v in self.facts.items():
            k_words = set(re.findall(r"[a-z]+", k.lower()))
            overlap = len(words & k_words)
            if overlap:
                scored.append((overlap, k, v))
        scored.sort(reverse=True)
        return [(k, v) for _, k, v in scored[:max_facts]]

# Voice System - Text-to-Speech and Speech-to-Text
class VoiceSystem:
    def __init__(self):
        self.voice_enabled = False
        self.tts_engine = None
        self.recognizer = None
        self._mic_available = False
        self._speaking = False  # True while TTS is playing — blocks mic

        # Text-to-speech
        if pyttsx3 is not None:
            try:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty('rate', 150)
                self.tts_engine.setProperty('volume', 0.9)
            except Exception as e:
                print(f"[Voice] TTS init failed: {e}")

        # Speech-to-text — use sounddevice (works on Python 3.14, no C++ needed)
        if sr is not None:
            try:
                import sounddevice as _sd  # noqa: F401
                self.recognizer = sr.Recognizer()
                self._mic_available = True
            except ImportError:
                self._mic_available = False

    # Neural voice to use — swap here to change Nicky's voice
    # Other good options: "en-US-GuyNeural", "en-GB-SoniaNeural", "en-US-JennyNeural"
    TTS_VOICE = "en-US-AriaNeural"

    def speak(self, text):
        """Convert text to speech — tries Edge TTS (neural) first, falls back to Windows SAPI."""
        if not text:
            return False

        self._speaking = True
        try:
            # Attempt 1: Edge TTS → soundfile → sounddevice
            try:
                import edge_tts
                import asyncio
                import tempfile
                import os
                import sounddevice as sd
                import soundfile as sf

                async def _synthesize(txt, voice, path):
                    await edge_tts.Communicate(txt, voice).save(path)

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = f.name

                asyncio.run(_synthesize(text, self.TTS_VOICE, tmp_path))
                try:
                    data, sample_rate = sf.read(tmp_path, dtype="float32")
                    sd.play(data, sample_rate)
                    sd.wait()
                    return True
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            except ImportError:
                pass
            except Exception as e:
                print(f"[Voice] Edge TTS error: {e} — falling back to SAPI...")

            # Attempt 2: Windows SAPI via PowerShell
            try:
                import subprocess
                safe_text = text.replace('"', '').replace("'", "").replace('$', '').replace('`', '').replace(';', '')
                result = subprocess.run(
                    ["powershell", "-Command",
                     f'Add-Type -AssemblyName System.Speech; '
                     f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                     f'$s.Rate = 1; $s.Speak("{safe_text}")'],
                    timeout=60, capture_output=True
                )
                if result.returncode == 0:
                    return True
                print(f"[Voice] SAPI error: {result.stderr.decode().strip()}")
            except Exception as e:
                print(f"[Voice] SAPI failed: {e}")

            # Attempt 3: pyttsx3
            if self.tts_engine is not None:
                try:
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                    return True
                except Exception as e:
                    print(f"[Voice] pyttsx3 error: {e}")

            print("[Voice] TTS unavailable — no working speech engine found.")
            return False

        finally:
            import time
            time.sleep(0.6)  # brief cooldown so mic doesn't catch speaker output
            self._speaking = False

    def listen(self, max_duration=10, silence_threshold=200, silence_seconds=1.2):
        """Record mic using silence detection — stops when you stop talking."""
        if self._speaking or not self._mic_available or self.recognizer is None:
            return None
        try:
            import sounddevice as sd
            import numpy as np
            import io
            import wave

            RATE = 16000
            CHUNK = 1024
            silence_chunks_needed = int(RATE / CHUNK * silence_seconds)

            chunks = []
            silent_chunks = 0
            has_speech = False

            print("🎤 Listening...", end="", flush=True)
            with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK) as stream:
                while len(chunks) < int(RATE / CHUNK * max_duration):
                    if self._speaking:
                        break
                    chunk, _ = stream.read(CHUNK)
                    rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                    chunks.append(chunk)
                    if rms > silence_threshold:
                        has_speech = True
                        silent_chunks = 0
                    elif has_speech:
                        silent_chunks += 1
                        if silent_chunks >= silence_chunks_needed:
                            break  # speech ended

            print("\r" + " " * 20 + "\r", end="", flush=True)

            if not has_speech:
                return None

            audio_data = np.concatenate(chunks, axis=0)
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(RATE)
                wf.writeframes(audio_data.tobytes())
            buf.seek(0)

            with sr.AudioFile(buf) as source:
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio)

        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            print("[Voice] Speech recognition service unavailable.")
            return None
        except Exception as e:
            print(f"[Voice] Unexpected listen() error: {e}")
            return None

    def enable_voice(self):
        """Turn on voice output + input mode."""
        if self.tts_engine is None and not self._has_powershell_sapi():
            return "TTS not available. Try: pip install pyttsx3"
        self.voice_enabled = True
        mic_status = "Microphone ready 🎤" if self._mic_available else "Microphone NOT available — install sounddevice: pip install sounddevice"
        self.test_speech()
        return f"Voice mode activated! {mic_status}"

    def _has_powershell_sapi(self):
        """Quick check if PowerShell SAPI is available."""
        try:
            import subprocess
            r = subprocess.run(["powershell", "-Command", "echo ok"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def disable_voice(self):
        """Turn off voice mode."""
        self.voice_enabled = False
        return "Voice mode deactivated."

    def test_speech(self):
        """Speak a short test phrase so the user can confirm TTS is working."""
        return self.speak("Voice mode activated. I can hear you.")

# Virtual Environment - represents the workspace
class Environment:
    def __init__(self):
        self.objects = []  # List of objects in the workspace
        self.arm_position = {"x": 0, "y": 0, "z": 0}  # Arm's current position
    
    def add_object(self, name, distance, angle, size="small"):
        """Add an object to the environment"""
        obj = {
            "name": name,
            "distance": distance,
            "angle": angle,
            "size": size,
            "held": False,
            "on_top_of": None  # Track if this object is on top of another
        }
        self.objects.append(obj)
        return f"Added {name} to the environment ({distance}cm away, {angle}°)"
    
    def remove_object(self, name):
        """Remove an object from the environment"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                self.objects.remove(obj)
                return f"Removed {name}"
        return f"{name} not found"
    
    def list_objects(self):
        """Show all objects in the environment"""
        if not self.objects:
            return "No objects in the environment. Add some first!"
        
        result = "Objects in workspace:\n"
        for obj in self.objects:
            if obj["held"]:
                status = "(in gripper)"
            elif obj["on_top_of"]:
                status = f"(on top of {obj['on_top_of']})"
            else:
                status = "(on ground)"
            result += f"  - {obj['name']}: {obj['distance']}cm, angle {obj['angle']}° {status}\n"
        return result.strip()
    
    def grab_object(self, name):
        """Mark an object as being held"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                obj["held"] = True
                return True
        return False
    
    def drop_object(self, name):
        """Mark an object as no longer held"""
        for obj in self.objects:
            if obj["name"].lower() == name.lower():
                obj["held"] = False
                return True
        return False
    
    def place_on_object(self, obj_name, target_name):
        """Place one object on top of another"""
        obj = self.find_object(obj_name)
        target = self.find_object(target_name)
        
        if obj and target:
            obj["on_top_of"] = target_name
            obj["held"] = False
            return True
        return False
    
    def remove_from_object(self, obj_name):
        """Remove object from being on top of something"""
        obj = self.find_object(obj_name)
        if obj:
            obj["on_top_of"] = None
            return True
        return False
    
    def find_object(self, name):
        """Find and return an object by exact name match."""
        for obj in self.objects:
            if name.lower() == obj["name"].lower():
                return obj
        return None

# Vision system for detecting objects in 180-degree field of view
class VisionSystem:
    def __init__(self):
        self.fov = 180  # Field of view in degrees
        self.detected_objects = []
        self.camera_active = False
        
    def activate_camera(self):
        """Turn on camera"""
        self.camera_active = True
        return "Camera activated. Scanning environment..."
    
    def deactivate_camera(self):
        """Turn off camera"""
        self.camera_active = False
        self.detected_objects = []
        return "Camera deactivated."
    
    def scan(self):
        """Simulate scanning for objects (will use real camera later)"""
        if not self.camera_active:
            return "Camera is not active."
        
        # Simulated object detection
        # In final version, this will process real camera feed
        self.detected_objects = [
            {"name": "object_1", "distance": 30, "angle": -45},
            {"name": "object_2", "distance": 50, "angle": 0},
            {"name": "object_3", "distance": 40, "angle": 45}
        ]
        return f"Scan complete. {len(self.detected_objects)} objects detected."
    
    def get_objects_in_view(self):
        """Return what the camera sees"""
        if not self.camera_active:
            return "Camera is offline."
        
        if not self.detected_objects:
            return "No objects in view."
        
        result = "Objects detected in 180° field of view:\n"
        for obj in self.detected_objects:
            result += f"  - {obj['name']}: {obj['distance']}cm away at {obj['angle']}°\n"
        return result.strip()
    
    def find_object(self, object_name):
        """Search for a specific object"""
        if not self.camera_active:
            return "Camera is offline. Cannot search."
        
        for obj in self.detected_objects:
            if object_name.lower() in obj['name'].lower():
                return f"Found {obj['name']} at {obj['distance']}cm, angle {obj['angle']}°"
        return f"Object '{object_name}' not found in view."

class NLUEngine:
    """AI-powered Natural Language Understanding — runs 100% offline, no internet needed."""

    INTENTS = {
        "move_left": [
            "move left", "go left", "shift left", "turn left", "swing left",
            "head left", "move the arm left", "slide left", "push left",
            "pan left", "rotate arm left", "go to the left", "left please"
        ],
        "move_right": [
            "move right", "go right", "shift right", "turn right", "swing right",
            "head right", "move the arm right", "slide right", "push right",
            "pan right", "rotate arm right", "go to the right", "right please"
        ],
        "move_up": [
            "move up", "go up", "raise up", "lift up", "go higher", "raise the arm",
            "lift the arm", "arm up", "elevate", "ascend", "reach higher",
            "bring it up", "lift it", "up please"
        ],
        "move_down": [
            "move down", "go down", "lower", "bring down", "drop down",
            "lower the arm", "arm down", "descend", "go lower",
            "bring it down", "lower it", "down please"
        ],
        "move_forward": [
            "move forward", "go forward", "extend forward", "reach forward",
            "advance", "extend the arm", "reach out", "push out", "go ahead",
            "move ahead", "stretch out", "reach further", "push forward"
        ],
        "move_back": [
            "move back", "go back", "retract", "pull back", "go backward",
            "come back", "bring back", "retreat", "draw back", "back up",
            "move backward", "pull in", "go backwards"
        ],
        "move_neutral": [
            "go to neutral", "center the arm", "home position", "reset position",
            "go home", "return to center", "neutral position", "rest position",
            "starting position", "center", "neutral", "home please"
        ],
        "grab": [
            "grab", "pick up", "grasp", "take hold of", "seize", "hold",
            "snatch", "pick it up", "collect it", "fetch", "retrieve",
            "grip it", "catch it", "grab the object", "pick up the item",
            "take the", "get the", "hold the"
        ],
        "release": [
            "release", "drop it", "let go", "put it down", "open the gripper",
            "let it go", "set it down", "place it down", "drop the object",
            "release it", "open hand", "free it", "let loose", "ungrasp",
            "drop", "put down"
        ],
        "camera_on": [
            "turn on the camera", "activate camera", "enable camera", "start camera",
            "camera on", "enable vision", "open your eyes", "turn on vision",
            "activate vision", "start looking", "eyes open", "look with camera"
        ],
        "camera_off": [
            "turn off the camera", "deactivate camera", "disable camera", "stop camera",
            "camera off", "disable vision", "close your eyes", "turn off vision",
            "deactivate vision", "eyes off", "stop looking", "kill camera"
        ],
        "scan": [
            "scan", "look around", "survey", "check surroundings",
            "scan the area", "survey the area", "check the environment",
            "do a scan", "scan environment", "take a look around", "look around you"
        ],
        "list_objects": [
            "what do you see", "show objects", "list objects", "what's there",
            "list items", "show me what's around", "what objects are there",
            "tell me what you see", "show all objects", "what's in the environment",
            "what can you see", "show me the objects", "what items are here"
        ],
        "find_object": [
            "find", "search for", "locate", "where is",
            "look for", "seek", "hunt for", "spot the",
            "find the", "locate the", "where's the", "search for the", "can you find"
        ],
        "add_object": [
            "add object to environment", "register a new object", "put object in workspace",
            "new object in scene", "add item to environment", "register item",
            "introduce new object", "add a new item to the workspace"
        ],
        "remove_object": [
            "remove object", "delete object", "take out", "remove the",
            "delete the", "get rid of", "eliminate object", "erase from environment"
        ],
        "clear_env": [
            "clear environment", "remove all objects", "clean workspace",
            "empty workspace", "clear everything", "reset workspace", "wipe all objects", "clear all"
        ],
        "visualize": [
            "visualize", "show workspace", "display workspace", "show map",
            "show me the layout", "display map", "ascii view", "show the grid",
            "workspace view", "show ascii", "visualize workspace", "show workspace grid"
        ],
        "plot": [
            "plot", "graph", "chart", "show graph", "display graph",
            "plot workspace", "create chart", "show chart", "show plot", "make a graph",
            "create a visualization plot", "matplotlib"
        ],
        "status": [
            "what's your status", "status", "where are you", "arm position",
            "current position", "where is the arm", "system status",
            "what are you doing", "arm status", "position report", "how is the arm",
            "what's the arm position"
        ],
        "help": [
            "help", "what can you do", "commands", "list commands", "instructions",
            "guide me", "what are your features", "how do i use you",
            "show commands", "all commands", "what commands do you have", "command list",
            "what are your abilities"
        ],
        "greeting": [
            "hello", "hi", "hey", "good morning", "good evening", "good afternoon",
            "howdy", "greetings", "sup", "yo", "hi there", "hey there",
            "what's up", "good day"
        ],
        "farewell": [
            "bye", "goodbye", "see you", "farewell", "i'm done",
            "see you later", "take care", "later", "signing off", "bye bye",
            "until next time", "have a good one"
        ],
        "joke": [
            "tell me a joke", "be funny", "make me laugh", "say something funny",
            "humor me", "got any jokes", "tell a joke", "be humorous",
            "make me smile", "entertain me", "crack a joke", "comedy time",
            "say something that will make me laugh"
        ],
        "fun_fact": [
            "tell me something", "teach me something", "fun fact", "share a fact",
            "something interesting", "random fact", "interesting fact",
            "tell me something cool", "share something interesting", "teach me a fact"
        ],
        "web_search": [
            "search for", "search online", "look up online", "google",
            "search the web", "find online", "look it up", "web search",
            "search the internet", "look that up", "find on the web",
        ],
        "learn_fact": [
            "learn that", "remember that", "actually", "that's wrong",
            "the correct answer is", "let me correct you", "teach yourself that",
            "you should know that", "store this fact", "note that"
        ],
        "ask_question": [
            "what is", "who is", "how does", "explain this", "tell me about",
            "what are", "define this", "describe", "what does it mean",
            "can you explain", "tell me about the", "what do you know about"
        ],
        "save": [
            "save", "save data", "remember this state", "store state",
            "save everything", "remember current state", "store everything", "keep this"
        ],
        "load": [
            "load", "recall", "restore", "load data", "retrieve saved data",
            "restore state", "load previous", "reload"
        ],
        "voice_on": [
            "enable voice", "voice on", "speak to me", "voice mode",
            "start speaking", "turn on voice", "activate voice", "talk to me",
            "audio on", "enable speech", "let me hear you", "use your voice"
        ],
        "voice_off": [
            "disable voice", "voice off", "stop speaking", "text mode",
            "silent mode", "turn off voice", "mute", "audio off",
            "disable speech", "stop talking", "be quiet", "go silent"
        ],
        "place_on": [
            "place on top of", "put on top of", "stack on", "place on",
            "put on", "set on top of", "stack the", "put it on top",
            "place it on", "lay on top of", "stack it on", "balance on top"
        ],
        "thanks": [
            "thank you", "thanks", "appreciate it", "thank you very much",
            "many thanks", "much appreciated", "thanks a lot", "cheers", "ty",
            "that was great thanks", "awesome thanks"
        ],
        "reset": [
            "reset", "restart", "reset system", "start over", "reboot",
            "system reset", "reset everything", "reset the arm", "reset all",
            "start fresh", "clear everything and reset"
        ],
        "how_are_you": [
            "how are you", "how's it going", "how are you doing", "you okay",
            "how do you feel", "are you well", "how's everything", "you alright",
            "everything okay with you", "how's the arm doing"
        ],
        "memory": [
            "show memory", "history", "what have i said", "command history",
            "show history", "past commands", "my history", "conversation history",
            "what did i say", "previous commands", "show my history"
        ],
        "sequence": [
            "run sequence", "execute routine", "play sequence", "run routine",
            "automated routine", "sequence", "routine", "run auto sequence",
            "execute a sequence of moves"
        ],
        "throw": [
            "throw", "toss", "launch", "hurl", "fling", "chuck", "yeet",
            "throw it", "toss it", "launch it", "hurl it", "fling it",
            "throw the", "toss the", "launch the", "chuck it", "throw object",
            "send it flying", "yeet it", "lob it", "lob the"
        ],
        "play_game": [
            "play snake", "play a game", "play game", "start snake", "run snake",
            "play brick breaker", "play brickbreaker", "start brickbreaker",
            "play brick", "launch snake", "launch brickbreaker",
            "play chess", "start chess", "launch chess", "chess game",
            "i want to play a game", "let's play a game", "play a video game",
            "game time", "start a game", "play something",
        ],
    }

    def __init__(self):
        self.model = None
        self._all_examples = []
        self._all_labels = []
        self._embeddings = None
        self._np = None
        self._model_ready = False
        # Load model in background so Nicky starts instantly
        import threading as _t
        _t.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        """Load the sentence transformer model in background (downloads ~90MB on first run)."""
        if SentenceTransformer is None:
            print("[Nicky AI] sentence-transformers not installed. Using keyword fallback.")
            print("           Run: pip install sentence-transformers  for the full AI experience.")
            return
        try:
            import numpy as _np
            self._np = _np
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self._build_index()
            self._model_ready = True
            print("[Nicky AI] ✅ Language model ready!")
        except Exception as e:
            print(f"[Nicky AI] Could not load model ({e}). Using keyword fallback.")
            self.model = None

    def _build_index(self):
        """Pre-encode all intent examples for fast matching at runtime."""
        for intent, examples in self.INTENTS.items():
            for ex in examples:
                self._all_examples.append(ex)
                self._all_labels.append(intent)
        self._embeddings = self.model.encode(
            self._all_examples, convert_to_numpy=True, show_progress_bar=False
        )

    def predict(self, text):
        """Returns (intent_name, confidence_score 0-1). Falls back to keywords while model loads."""
        if self.model is None or not self._model_ready:
            return self._keyword_fallback(text)

        if not self._all_labels:
            return "unknown", 0.0

        vec = self.model.encode([text.lower()], convert_to_numpy=True)
        num = self._np.dot(self._embeddings, vec.T).flatten()
        denom = self._np.linalg.norm(self._embeddings, axis=1) * self._np.linalg.norm(vec) + 1e-8
        sims = num / denom

        best = int(self._np.argmax(sims))
        return self._all_labels[best], float(sims[best])

    def _keyword_fallback(self, text):
        """Simple keyword matching when model isn't available."""
        t = text.lower()
        checks = [
            (["left"],             "move_left"),
            (["right"],            "move_right"),
            (["up", "raise", "lift"], "move_up"),
            (["down", "lower"],    "move_down"),
            (["forward", "ahead"], "move_forward"),
            (["back", "retract"],  "move_back"),
            (["neutral", "center", "home"], "move_neutral"),
            (["grab", "pick", "grasp", "take"], "grab"),
            (["release", "drop", "let go"], "release"),
            (["camera on", "activate camera", "enable camera"], "camera_on"),
            (["camera off", "disable camera"], "camera_off"),
            (["scan", "look around"], "scan"),
            (["what do you see", "list objects", "show objects"], "list_objects"),
            (["find ", "locate ", "where is"], "find_object"),
            (["hello", "hi", "hey"], "greeting"),
            (["bye", "goodbye", "farewell"], "farewell"),
            (["status", "position"], "status"),
            (["help", "commands"], "help"),
            (["visualize", "show workspace"], "visualize"),
            (["plot", "graph", "chart"], "plot"),
            (["joke"], "joke"),
            (["search for", "google ", "look up online", "search online", "search the web"], "web_search"),
            (["learn that", "actually", "remember that"], "learn_fact"),
            (["play snake", "play game", "play brick", "brickbreaker", "game time"], "play_game"),
            (["save"], "save"),
            (["load", "recall"], "load"),
            (["voice on", "enable voice"], "voice_on"),
            (["voice off", "disable voice"], "voice_off"),
            (["thank"], "thanks"),
            (["reset", "restart"], "reset"),
            (["how are you"], "how_are_you"),
            (["history", "memory"], "memory"),
            (["place on", "put on", "stack on"], "place_on"),
            (["clear", "empty"], "clear_env"),
        ]
        for keywords, intent in checks:
            if any(k in t for k in keywords):
                return intent, 0.9
        return "unknown", 0.0


class UserMemory:
    """Remembers facts about the user across sessions."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.facts = {}   # e.g. {"name": "Elias", "likes": ["jazz", "coding"]}
        self._load()

    def _load(self):
        path = os.path.join(self.data_dir, "user_memory.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.facts = json.load(f)
            except Exception:
                self.facts = {}

    def save(self):
        path = os.path.join(self.data_dir, "user_memory.json")
        try:
            with open(path, "w") as f:
                json.dump(self.facts, f, indent=2)
        except Exception:
            pass

    def learn(self, key, value):
        """Store or update a fact about the user."""
        if isinstance(value, list):
            existing = self.facts.get(key, [])
            if not isinstance(existing, list):
                existing = [existing]
            if value[0] not in existing:
                existing.extend(value)
            self.facts[key] = existing
        else:
            self.facts[key] = value
        self.save()

    def extract_from_text(self, text):
        """Auto-detect personal facts from what the user says."""
        import re
        t = text.lower()
        found = {}

        # "my name is X"
        m = re.search(r"my name is ([a-z]+)", t, re.IGNORECASE)
        if m:
            found["name"] = m.group(1).capitalize()

        # "i am X" / "i'm X" (job/description)
        m = re.search(r"i(?:'m| am) (?:a |an )?([a-z]+ ?[a-z]*)", t, re.IGNORECASE)
        if m and m.group(1) not in ("fine", "good", "okay", "ok", "here", "back", "not",
                                    "going", "trying", "just", "also", "still", "really"):
            found["description"] = m.group(1).strip()

        # "i am X years old"
        m = re.search(r"i(?:'m| am) (\d+)(?: years old)?", t, re.IGNORECASE)
        if m:
            found["age"] = m.group(1)

        # "i live in X" / "i'm from X" / "i'm in X"
        m = re.search(r"i(?:'m| am) (?:from|in) ([a-z][\w ]{2,25})", t, re.IGNORECASE)
        if not m:
            m = re.search(r"i live in ([a-z][\w ]{2,25})", t, re.IGNORECASE)
        if m:
            found["location"] = m.group(1).strip().title()

        # "i'm building X" / "i'm working on X" / "my project is X"
        m = re.search(r"(?:i(?:'m| am) (?:building|working on|creating|making)|my project is) ([a-z][\w ]{2,40})", t, re.IGNORECASE)
        if m:
            found["project"] = m.group(1).strip()

        # "i like/love X"
        m = re.search(r"i (?:like|love|enjoy|prefer) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found["likes"] = [m.group(1).strip()]

        # "i hate/dislike X"
        m = re.search(r"i (?:hate|dislike|don't like|cant stand) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found["dislikes"] = [m.group(1).strip()]

        # "i play X" / "my hobby is X"
        m = re.search(r"(?:i play|my hobby is|i spend time) ([a-z][\w ]{2,30})", t, re.IGNORECASE)
        if m:
            found.setdefault("hobbies", []).append(m.group(1).strip())

        for key, value in found.items():
            self.learn(key, value)

        return found

    def as_prompt_text(self):
        """Return a string summarising what Nicky knows about the user."""
        if not self.facts:
            return ""
        parts = []
        if "name" in self.facts:
            parts.append(f"The user's name is {self.facts['name']}.")
        if "age" in self.facts:
            parts.append(f"They are {self.facts['age']} years old.")
        if "location" in self.facts:
            parts.append(f"They are from/in {self.facts['location']}.")
        if "description" in self.facts:
            parts.append(f"They described themselves as: {self.facts['description']}.")
        if "project" in self.facts:
            parts.append(f"They are working on: {self.facts['project']}.")
        if "likes" in self.facts:
            parts.append(f"They like: {', '.join(self.facts['likes'])}.")
        if "dislikes" in self.facts:
            parts.append(f"They dislike: {', '.join(self.facts['dislikes'])}.")
        if "hobbies" in self.facts:
            parts.append(f"Their hobbies include: {', '.join(self.facts['hobbies'])}.")
        for key, val in self.facts.items():
            if key not in ("name", "age", "location", "description", "project", "likes", "dislikes", "hobbies"):
                parts.append(f"{key}: {val}.")
        return "What you know about the user — " + " ".join(parts)


class CustomPersonality:
    """Lets the user shape Nicky's personality through conversation."""

    TRAIT_TRIGGERS = {
        "sarcastic":  ["be more sarcastic", "be sarcastic", "act sarcastic"],
        "funny":      ["be more funny", "be funnier", "be funny", "make me laugh more"],
        "serious":    ["be more serious", "be serious", "stop joking", "act professional"],
        "casual":     ["be more casual", "be casual", "relax a bit", "chill out"],
        "energetic":  ["be more energetic", "be enthusiastic", "be excited"],
        "concise":    ["be more concise", "keep it short", "shorter answers", "be brief"],
        "detailed":   ["be more detailed", "give more detail", "elaborate more", "explain more"],
    }

    TRAIT_DESCRIPTIONS = {
        "sarcastic":  "You are slightly sarcastic and witty, but still helpful.",
        "funny":      "You inject humour and light jokes into responses when appropriate.",
        "serious":    "You are professional and to-the-point, minimal jokes.",
        "casual":     "You speak casually, like talking to a friend.",
        "energetic":  "You are upbeat and enthusiastic in everything you say.",
        "concise":    "You keep all responses as short as possible — one or two sentences max.",
        "detailed":   "You give thorough, detailed explanations when answering.",
    }

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.traits = []
        self._load()

    def _load(self):
        path = os.path.join(self.data_dir, "personality.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.traits = json.load(f)
            except Exception:
                self.traits = []

    def save(self):
        path = os.path.join(self.data_dir, "personality.json")
        try:
            with open(path, "w") as f:
                json.dump(self.traits, f, indent=2)
        except Exception:
            pass

    def detect_and_apply(self, text):
        """Check if the user is asking to change personality. Returns response or None."""
        t = text.lower()
        for trait, triggers in self.TRAIT_TRIGGERS.items():
            if any(trigger in t for trigger in triggers):
                if trait not in self.traits:
                    self.traits.append(trait)
                else:
                    self.traits.remove(trait)
                    self.save()
                    return f"Okay, toning down the {trait} side."
                self.save()
                return f"Got it — I'll be more {trait} from now on."
        if any(p in t for p in ("reset personality", "default personality", "stop being", "normal please")):
            self.traits = []
            self.save()
            return "Personality reset to default."
        return None

    def as_prompt_text(self):
        """Return active trait instructions for the system prompt."""
        if not self.traits:
            return ""
        descriptions = [self.TRAIT_DESCRIPTIONS[t] for t in self.traits if t in self.TRAIT_DESCRIPTIONS]
        return "Active personality traits: " + " ".join(descriptions)


# Simple JARVIS-like chatbot for controlling a robotic arm
# ---------------------------------------------------------------------------
#  Mini-game system — Snake & Brick Breaker, Nicky plays autonomously
# ---------------------------------------------------------------------------
import tkinter as _tk
import threading as _threading
import math as _math


class SnakeGame:
    """Nicky plays Snake autonomously using a greedy path-to-food AI."""

    CELL = 20
    COLS = 25
    ROWS = 25
    SPEED = 120  # ms per frame (lower = faster)

    def __init__(self, nicky_say=None):
        self._say = nicky_say or (lambda msg: print(f"[Nicky] {msg}"))
        self.root = _tk.Tk()
        self.root.title("Nicky plays Snake 🐍")
        self.root.resizable(False, False)
        W = self.COLS * self.CELL
        H = self.ROWS * self.CELL
        self.canvas = _tk.Canvas(self.root, width=W, height=H, bg="#111")
        self.canvas.pack()
        self.score_var = _tk.StringVar(value="Score: 0")
        _tk.Label(self.root, textvariable=self.score_var, bg="#111", fg="white",
                  font=("Courier", 12)).pack()
        self._reset()
        self._say("Alright, snake time! Let's see how long I can go. 🐍")
        self.root.after(self.SPEED, self._step)
        self.root.mainloop()

    def _reset(self):
        mid = (self.COLS // 2, self.ROWS // 2)
        self.snake = [mid, (mid[0] - 1, mid[1]), (mid[0] - 2, mid[1])]
        self.direction = (1, 0)
        self.score = 0
        self._last_milestone = 0
        self._place_food()

    def _place_food(self):
        occupied = set(self.snake)
        while True:
            f = (random.randint(0, self.COLS - 1), random.randint(0, self.ROWS - 1))
            if f not in occupied:
                self.food = f
                break

    def _ai_direction(self):
        head = self.snake[0]
        fx, fy = self.food
        hx, hy = head
        body_set = set(self.snake[1:])
        candidates = [(1, 0), (-1, 0), (0, 1), (0, -1)]

        def safe(d):
            nx, ny = hx + d[0], hy + d[1]
            if not (0 <= nx < self.COLS and 0 <= ny < self.ROWS):
                return False
            return (nx, ny) not in body_set

        safe_dirs = [d for d in candidates if safe(d)]
        if not safe_dirs:
            return self.direction
        return min(safe_dirs, key=lambda d: abs(hx + d[0] - fx) + abs(hy + d[1] - fy))

    def _step(self):
        self.direction = self._ai_direction()
        hx, hy = self.snake[0]
        new_head = (hx + self.direction[0], hy + self.direction[1])

        if (not (0 <= new_head[0] < self.COLS and 0 <= new_head[1] < self.ROWS)
                or new_head in self.snake):
            self._game_over()
            return

        self.snake.insert(0, new_head)
        if new_head == self.food:
            self.score += 10
            self.score_var.set(f"Score: {self.score}")
            self._place_food()
            # Milestone commentary every 50 points
            milestone = self.score // 50
            if milestone > self._last_milestone:
                self._last_milestone = milestone
                msgs = [
                    f"Score is {self.score}! I'm on a roll! 🎯",
                    f"{self.score} points! Getting longer... and more dangerous.",
                    f"Nom nom! {self.score} points and still going strong! 🐍",
                    f"{self.score}! The snake grows. This is getting tight...",
                ]
                self._say(random.choice(msgs))
        else:
            self.snake.pop()

        self._draw()
        self.root.after(self.SPEED, self._step)

    def _draw(self):
        self.canvas.delete("all")
        C = self.CELL
        for i, (x, y) in enumerate(self.snake):
            color = "#00ff88" if i == 0 else "#00cc66"
            self.canvas.create_rectangle(x*C+1, y*C+1, x*C+C-1, y*C+C-1,
                                         fill=color, outline="")
        fx, fy = self.food
        self.canvas.create_oval(fx*C+3, fy*C+3, fx*C+C-3, fy*C+C-3,
                                 fill="#ff4444", outline="")

    def _game_over(self):
        W = self.COLS * self.CELL
        H = self.ROWS * self.CELL
        self.canvas.create_text(W//2, H//2 - 20, text="GAME OVER",
                                 fill="white", font=("Courier", 24, "bold"))
        self.canvas.create_text(W//2, H//2 + 15,
                                 text=f"Final Score: {self.score}",
                                 fill="#aaa", font=("Courier", 14))
        self.canvas.create_text(W//2, H//2 + 45, text="[Close window to exit]",
                                 fill="#666", font=("Courier", 11))
        endings = [
            f"Crashed! Final score: {self.score}. That wall came out of nowhere.",
            f"Oof, hit myself. {self.score} points though — not bad!",
            f"Game over. {self.score} points. I'll do better next time.",
            f"And that's a wrap. {self.score} points. The snake has spoken. 🐍",
        ]
        self._say(random.choice(endings))


class BrickBreakerGame:
    """Nicky plays Brick Breaker autonomously — paddle tracks ball trajectory."""

    W, H = 480, 560
    PAD_W, PAD_H = 80, 12
    BALL_R = 9
    BRICK_COLS, BRICK_ROWS = 8, 5
    SPEED = 16  # ms per frame

    def __init__(self, nicky_say=None):
        self._say = nicky_say or (lambda msg: print(f"[Nicky] {msg}"))
        self.root = _tk.Tk()
        self.root.title("Nicky plays Brick Breaker 🧱")
        self.root.resizable(False, False)
        self.canvas = _tk.Canvas(self.root, width=self.W, height=self.H, bg="#111")
        self.canvas.pack()
        self.score_var = _tk.StringVar(value="Score: 0")
        _tk.Label(self.root, textvariable=self.score_var, bg="#111", fg="white",
                  font=("Courier", 12)).pack()
        self._reset()
        self._say("Brick Breaker! My paddle reflexes are unmatched. Watch this. 🧱")
        self.root.after(500, self._step)
        self.root.mainloop()

    def _reset(self):
        self.pad_x = self.W // 2 - self.PAD_W // 2
        self.ball_x = float(self.W // 2)
        self.ball_y = float(self.H - 80)
        self.ball_vx = 3.5
        self.ball_vy = -4.0
        self.score = 0
        self._bricks_broken = 0
        self._last_comment = 0
        bw = self.W // self.BRICK_COLS
        bh = 24
        colors = ["#ff5555", "#ff8844", "#ffcc44", "#88ff44", "#44ccff"]
        self.bricks = []
        for r in range(self.BRICK_ROWS):
            for c in range(self.BRICK_COLS):
                x1 = c * bw + 3
                y1 = 50 + r * (bh + 4) + 3
                x2 = x1 + bw - 6
                y2 = y1 + bh - 6
                self.bricks.append([x1, y1, x2, y2, colors[r % len(colors)], True])

    def _ai_move(self):
        # Deliberately aim slightly off-center so the ball never returns perfectly straight
        wobble = random.uniform(-12, 12)
        target_x = self.ball_x - self.PAD_W // 2 + wobble
        target_x = max(0, min(self.W - self.PAD_W, target_x))
        speed = 5
        if self.pad_x < target_x - speed:
            self.pad_x += speed
        elif self.pad_x > target_x + speed:
            self.pad_x -= speed
        else:
            self.pad_x = target_x

    def _step(self):
        self._ai_move()
        self.ball_x += self.ball_vx
        self.ball_y += self.ball_vy
        r = self.BALL_R

        if self.ball_x - r <= 0 or self.ball_x + r >= self.W:
            self.ball_vx *= -1
        if self.ball_y - r <= 0:
            self.ball_vy *= -1

        pad_y = self.H - 50
        if (pad_y <= self.ball_y + r <= pad_y + self.PAD_H
                and self.pad_x <= self.ball_x <= self.pad_x + self.PAD_W):
            self.ball_vy = -abs(self.ball_vy)
            offset = (self.ball_x - (self.pad_x + self.PAD_W / 2)) / (self.PAD_W / 2)
            self.ball_vx = offset * 5
            # Guarantee a minimum horizontal speed so the ball never gets stuck vertically
            if abs(self.ball_vx) < 1.5:
                self.ball_vx = random.choice([-1, 1]) * (1.5 + random.uniform(0, 1))

        for brick in self.bricks:
            if not brick[5]:
                continue
            x1, y1, x2, y2 = brick[:4]
            if x1 - r < self.ball_x < x2 + r and y1 - r < self.ball_y < y2 + r:
                brick[5] = False
                self.score += 5
                self._bricks_broken += 1
                self.score_var.set(f"Score: {self.score}")
                self.ball_vy *= -1
                # Comment every 8 bricks
                if self._bricks_broken % 8 == 0 and self._bricks_broken != self._last_comment:
                    self._last_comment = self._bricks_broken
                    remaining = sum(1 for b in self.bricks if b[5])
                    msgs = [
                        f"{self._bricks_broken} bricks down! {remaining} left to go.",
                        f"Smashing it! {self.score} points so far. 💥",
                        f"{remaining} bricks remaining. This is going well!",
                        f"Crack! {self._bricks_broken} broken. Paddle is locked in. 🏓",
                    ]
                    self._say(random.choice(msgs))
                break

        if self.ball_y > self.H + 20:
            self._game_over()
            return

        if not any(b[5] for b in self.bricks):
            self._win()
            return

        self._draw()
        self.root.after(self.SPEED, self._step)

    def _draw(self):
        self.canvas.delete("all")
        for b in self.bricks:
            if b[5]:
                self.canvas.create_rectangle(b[0], b[1], b[2], b[3],
                                              fill=b[4], outline="#222")
        py = self.H - 50
        self.canvas.create_rectangle(self.pad_x, py,
                                      self.pad_x + self.PAD_W, py + self.PAD_H,
                                      fill="#4488ff", outline="")
        r = self.BALL_R
        self.canvas.create_oval(self.ball_x - r, self.ball_y - r,
                                 self.ball_x + r, self.ball_y + r,
                                 fill="white", outline="")

    def _game_over(self):
        self.canvas.create_text(self.W//2, self.H//2, text="GAME OVER",
                                 fill="white", font=("Courier", 24, "bold"))
        self.canvas.create_text(self.W//2, self.H//2 + 35,
                                 text=f"Score: {self.score}",
                                 fill="#aaa", font=("Courier", 14))
        self._say(f"Ball dropped! Final score: {self.score}. The paddle had one job...")

    def _win(self):
        self.canvas.create_text(self.W//2, self.H//2, text="ALL CLEAR! 🎉",
                                 fill="#ffcc44", font=("Courier", 24, "bold"))
        self.canvas.create_text(self.W//2, self.H//2 + 35,
                                 text=f"Final Score: {self.score}",
                                 fill="#aaa", font=("Courier", 14))
        self._say(f"ALL BRICKS CLEARED! Final score: {self.score}! That's how it's done! 🎉")


class ChessGame:
    """Chess — you play White, Nicky plays Black using minimax AI."""

    SQ = 72
    LIGHT = "#f0d9b5"
    DARK  = "#b58863"
    SEL   = "#7fc97f"   # selected square highlight
    HINT  = "#aad4a4"   # valid move dot color
    SPEED = 700         # ms for Nicky to "think"

    UNICODE = {
        'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
        'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
    }
    PIECE_NAMES = {
        'p': 'pawn', 'n': 'knight', 'b': 'bishop',
        'r': 'rook',  'q': 'queen',  'k': 'king',
    }
    VALUES = {'p': 100, 'n': 320, 'b': 330, 'r': 500, 'q': 900, 'k': 20000}

    START = [
        ['r','n','b','q','k','b','n','r'],
        ['p','p','p','p','p','p','p','p'],
        ['.','.','.','.','.','.','.','.',],
        ['.','.','.','.','.','.','.','.',],
        ['.','.','.','.','.','.','.','.',],
        ['.','.','.','.','.','.','.','.',],
        ['P','P','P','P','P','P','P','P'],
        ['R','N','B','Q','K','B','N','R'],
    ]

    def __init__(self, nicky_say=None):
        import copy
        self._copy = copy
        self._say = nicky_say or (lambda msg: print(f"[Nicky] {msg}"))
        self.root = _tk.Tk()
        self.root.title("Chess — You (White ♔) vs Nicky (Black ♚)")
        self.root.resizable(False, False)
        S = self.SQ
        self.canvas = _tk.Canvas(self.root, width=S*8, height=S*8, bg="#222")
        self.canvas.pack()
        self.status_var = _tk.StringVar(value="Your turn — click a white piece to move")
        _tk.Label(self.root, textvariable=self.status_var, bg="#222", fg="white",
                  font=("Courier", 11), pady=4).pack(fill="x")
        self.board = self._copy.deepcopy(self.START)
        self.turn = 'white'
        self.move_count = 0
        self.game_over = False
        self.selected = None
        self.valid_moves = []
        self.canvas.bind("<Button-1>", self._on_click)
        self._say("Chess! You're White, I'm Black. Good luck — you'll need it. ♟")
        self._draw()
        self.root.mainloop()

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _white(p): return p != '.' and p.isupper()
    @staticmethod
    def _black(p): return p != '.' and p.islower()
    def _friendly(self, p, color):
        return self._white(p) if color == 'white' else self._black(p)
    def _enemy(self, p, color):
        return self._black(p) if color == 'white' else self._white(p)

    # ── move generation ───────────────────────────────────────────────────────
    def _moves(self, board, r, c, color):
        p = board[r][c].lower()
        if   p == 'p': return self._pawn(board, r, c, color)
        elif p == 'n': return self._knight(board, r, c, color)
        elif p == 'b': return self._slide(board, r, c, color, [(-1,-1),(-1,1),(1,-1),(1,1)])
        elif p == 'r': return self._slide(board, r, c, color, [(-1,0),(1,0),(0,-1),(0,1)])
        elif p == 'q': return (self._slide(board, r, c, color, [(-1,-1),(-1,1),(1,-1),(1,1)]) +
                                self._slide(board, r, c, color, [(-1,0),(1,0),(0,-1),(0,1)]))
        elif p == 'k': return self._king(board, r, c, color)
        return []

    def _pawn(self, board, r, c, color):
        d = -1 if color == 'white' else 1
        start = 6 if color == 'white' else 1
        moves = []
        nr = r + d
        if 0 <= nr < 8:
            if board[nr][c] == '.':
                moves.append((nr, c))
                nr2 = r + 2*d
                if r == start and board[nr2][c] == '.':
                    moves.append((nr2, c))
            for dc in (-1, 1):
                nc = c + dc
                if 0 <= nc < 8 and self._enemy(board[nr][nc], color):
                    moves.append((nr, nc))
        return moves

    def _knight(self, board, r, c, color):
        return [(r+dr, c+dc)
                for dr, dc in ((-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1))
                if 0 <= r+dr < 8 and 0 <= c+dc < 8
                and not self._friendly(board[r+dr][c+dc], color)]

    def _slide(self, board, r, c, color, dirs):
        moves = []
        for dr, dc in dirs:
            nr, nc = r+dr, c+dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                if board[nr][nc] == '.':
                    moves.append((nr, nc))
                elif self._enemy(board[nr][nc], color):
                    moves.append((nr, nc)); break
                else:
                    break
                nr += dr; nc += dc
        return moves

    def _king(self, board, r, c, color):
        return [(r+dr, c+dc)
                for dr in (-1,0,1) for dc in (-1,0,1)
                if (dr or dc) and 0 <= r+dr < 8 and 0 <= c+dc < 8
                and not self._friendly(board[r+dr][c+dc], color)]

    def _all_moves(self, board, color):
        out = []
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if (color == 'white' and self._white(p)) or (color == 'black' and self._black(p)):
                    for tr, tc in self._moves(board, r, c, color):
                        out.append((r, c, tr, tc))
        return out

    def _apply(self, board, fr, fc, tr, tc):
        b = self._copy.deepcopy(board)
        piece = b[fr][fc]
        b[tr][tc] = piece
        b[fr][fc] = '.'
        if piece == 'P' and tr == 0: b[tr][tc] = 'Q'
        if piece == 'p' and tr == 7: b[tr][tc] = 'q'
        return b

    # ── player click handler ──────────────────────────────────────────────────
    def _on_click(self, event):
        if self.game_over or self.turn != 'white':
            return
        S = self.SQ
        c, r = event.x // S, event.y // S
        if not (0 <= r < 8 and 0 <= c < 8):
            return

        if self.selected is None:
            # Select a white piece
            if self._white(self.board[r][c]):
                self.selected = (r, c)
                self.valid_moves = self._moves(self.board, r, c, 'white')
                self._draw()
        else:
            fr, fc = self.selected
            if (r, c) in self.valid_moves:
                # Execute player move
                captured = self.board[r][c]
                self.board = self._apply(self.board, fr, fc, r, c)
                self.move_count += 1
                self.selected = None
                self.valid_moves = []
                self.turn = 'black'
                if captured != '.':
                    name = self.PIECE_NAMES.get(captured.lower(), 'piece')
                    self._say(random.choice([
                        f"You took my {name}! Bold move. Let's see if it pays off.",
                        f"My {name}! I'll remember that. ♟",
                        f"Okay, you got my {name}. Don't get comfortable.",
                        f"There goes my {name}. I'm recalculating... 🤔",
                    ]))
                self.status_var.set(f"Move {self.move_count}  —  Nicky is thinking... 🤔")
                self._draw()
                self._check_end()
                if not self.game_over:
                    self.root.after(self.SPEED, self._nicky_move)
            elif self._white(self.board[r][c]):
                # Re-select a different white piece
                self.selected = (r, c)
                self.valid_moves = self._moves(self.board, r, c, 'white')
                self._draw()
            else:
                # Deselect
                self.selected = None
                self.valid_moves = []
                self._draw()

    def _nicky_move(self):
        if self.game_over:
            return
        _, move = self._minimax(self.board, 2, float('-inf'), float('inf'), False)
        if move is None:
            self.status_var.set("Checkmate! You win! 🏆🎉")
            self._say("Checkmate... well played. I didn't see that coming. 🎩")
            self.game_over = True
            return
        fr, fc, tr, tc = move
        captured = self.board[tr][tc]
        self.board = self._apply(self.board, fr, fc, tr, tc)
        self.move_count += 1
        self.turn = 'white'
        if captured != '.':
            name = self.PIECE_NAMES.get(captured.lower(), 'piece')
            self._say(random.choice([
                f"I took your {name}! ♚",
                f"Your {name} is mine now. 😏",
                f"Captured your {name}. The board shifts in my favour.",
                f"Ha! Your {name} falls. What's your next move?",
            ]))
        elif self.move_count % 10 == 0:
            self._say(random.choice([
                f"Move {self.move_count}. This is quite the game.",
                f"Still calculating. Move {self.move_count} — interesting position.",
                f"Move {self.move_count}. I like where this is going. For me, at least.",
            ]))
        self.status_var.set(f"Move {self.move_count}  —  Your turn ♔")
        self._draw()
        self._check_end()
        if self.move_count >= 200:
            self.status_var.set("Draw — 200 move limit reached.")
            self._say("200 moves and no winner. Respect for the endurance.")
            self.game_over = True

    def _check_end(self):
        if not self._all_moves(self.board, self.turn):
            if self.turn == 'white':
                self.status_var.set("Checkmate! Nicky wins! 🤖♚")
                self._say("Checkmate! Better luck next time. 🤖♚")
            else:
                self.status_var.set("Checkmate! You win! 🏆♔")
                self._say("Checkmate! You got me. Well played. 🏆")
            self.game_over = True

    # ── evaluation & minimax ─────────────────────────────────────────────────
    def _eval(self, board):
        score = 0
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p == '.': continue
                v = self.VALUES.get(p.lower(), 0)
                score += v if p.isupper() else -v
        return score

    def _minimax(self, board, depth, alpha, beta, maxi):
        if depth == 0:
            return self._eval(board), None
        color = 'white' if maxi else 'black'
        moves = self._all_moves(board, color)
        if not moves:
            return (-30000 if maxi else 30000), None
        best_move = moves[0]
        best = float('-inf') if maxi else float('inf')
        for mv in moves:
            nb = self._apply(board, *mv)
            score, _ = self._minimax(nb, depth-1, alpha, beta, not maxi)
            if maxi and score > best:
                best, best_move = score, mv
                alpha = max(alpha, best)
            elif not maxi and score < best:
                best, best_move = score, mv
                beta = min(beta, best)
            if beta <= alpha:
                break
        return best, best_move

    # ── rendering ─────────────────────────────────────────────────────────────
    def _draw(self):
        self.canvas.delete("all")
        S = self.SQ
        files = "abcdefgh"
        hint_set = set(self.valid_moves)
        for r in range(8):
            for c in range(8):
                # Square color — highlight selected & valid moves
                if self.selected == (r, c):
                    fill = self.SEL
                elif (r, c) in hint_set:
                    fill = self.HINT
                else:
                    fill = self.LIGHT if (r+c) % 2 == 0 else self.DARK
                self.canvas.create_rectangle(c*S, r*S, (c+1)*S, (r+1)*S,
                                              fill=fill, outline="")
                # Dot hint on empty valid squares
                if (r, c) in hint_set and self.board[r][c] == '.':
                    m = S // 2
                    d = S // 6
                    self.canvas.create_oval(c*S+m-d, r*S+m-d, c*S+m+d, r*S+m+d,
                                             fill="#3a7a3a", outline="")
                # Piece
                p = self.board[r][c]
                if p != '.':
                    sym = self.UNICODE.get(p, p)
                    fg = "#1a1a1a" if p.isupper() else "#eeeeee"
                    self.canvas.create_text(c*S+S//2, r*S+S//2, text=sym,
                                             font=("Arial", int(S*0.62)), fill=fg)
        # Labels
        for i in range(8):
            lc = self.DARK if i % 2 == 0 else self.LIGHT
            self.canvas.create_text(i*S+S-4, 7*S+S-4, text=files[i],
                                     font=("Courier", 9, "bold"), fill=lc, anchor="se")
            self.canvas.create_text(4, i*S+4, text=str(8-i),
                                     font=("Courier", 9, "bold"), fill=lc, anchor="nw")


# ── New Games ─────────────────────────────────────────────────────────────────

class Connect4Game:
    """Connect 4 — Player (Red) vs Nicky (Yellow). Click a column to drop."""
    ROWS, COLS = 6, 7
    CELL = 80
    def __init__(self, nicky_say=None):
        import tkinter as tk
        self.nicky_say = nicky_say or (lambda m: None)
        self.board = [[0]*self.COLS for _ in range(self.ROWS)]
        self.root = tk.Tk()
        self.root.title("Connect 4 — You (🔴) vs Nicky (🟡)")
        W = self.COLS * self.CELL
        H = self.ROWS * self.CELL + 60
        self.canvas = tk.Canvas(self.root, width=W, height=H, bg="#1a1a2e")
        self.canvas.pack()
        self.status = tk.Label(self.root, text="Your turn — click a column!", bg="#1a1a2e",
                               fg="white", font=("Arial", 12, "bold"))
        self.status.pack()
        self.game_over = False
        self.canvas.bind("<Button-1>", self._on_click)
        self._draw()
        self.nicky_say("Connect 4! You're Red, I'm Yellow. Drop a disc by clicking a column!")

    def _draw(self):
        S = self.CELL
        self.canvas.delete("all")
        for r in range(self.ROWS):
            for c in range(self.COLS):
                x, y = c*S + S//2, r*S + S//2 + 30
                fill = "#2d2d5e" if self.board[r][c] == 0 else (
                    "#e74c3c" if self.board[r][c] == 1 else "#f1c40f")
                self.canvas.create_oval(x-32, y-32, x+32, y+32, fill=fill, outline="#888")
        self.canvas.create_line(0, 30, self.COLS*S, 30, fill="#555")

    def _drop(self, col, player):
        for r in range(self.ROWS-1, -1, -1):
            if self.board[r][col] == 0:
                self.board[r][col] = player
                return r
        return -1

    def _check_win(self, player):
        b = self.board; R, C = self.ROWS, self.COLS
        for r in range(R):
            for c in range(C-3):
                if all(b[r][c+i] == player for i in range(4)): return True
        for r in range(R-3):
            for c in range(C):
                if all(b[r+i][c] == player for i in range(4)): return True
        for r in range(R-3):
            for c in range(C-3):
                if all(b[r+i][c+i] == player for i in range(4)): return True
        for r in range(3, R):
            for c in range(C-3):
                if all(b[r-i][c+i] == player for i in range(4)): return True
        return False

    def _score_window(self, window, player):
        opp = 1 if player == 2 else 2
        score = 0
        if window.count(player) == 4: score += 100
        elif window.count(player) == 3 and window.count(0) == 1: score += 5
        elif window.count(player) == 2 and window.count(0) == 2: score += 2
        if window.count(opp) == 3 and window.count(0) == 1: score -= 4
        return score

    def _score_board(self, player):
        b = self.board; R, C = self.ROWS, self.COLS; score = 0
        center = [b[r][C//2] for r in range(R)]
        score += center.count(player) * 3
        for r in range(R):
            for c in range(C-3):
                score += self._score_window([b[r][c+i] for i in range(4)], player)
        for r in range(R-3):
            for c in range(C):
                score += self._score_window([b[r+i][c] for i in range(4)], player)
        return score

    def _valid_cols(self):
        return [c for c in range(self.COLS) if self.board[0][c] == 0]

    def _minimax(self, depth, alpha, beta, maximizing):
        valid = self._valid_cols()
        if self._check_win(2): return 10000
        if self._check_win(1): return -10000
        if not valid or depth == 0: return self._score_board(2)
        if maximizing:
            val = -float('inf')
            for c in valid:
                r = self._drop(c, 2); val = max(val, self._minimax(depth-1, alpha, beta, False))
                self.board[r][c] = 0; alpha = max(alpha, val)
                if alpha >= beta: break
            return val
        else:
            val = float('inf')
            for c in valid:
                r = self._drop(c, 1); val = min(val, self._minimax(depth-1, alpha, beta, True))
                self.board[r][c] = 0; beta = min(beta, val)
                if alpha >= beta: break
            return val

    def _nicky_move(self):
        import random
        valid = self._valid_cols()
        if not valid: return
        best_score, best_col = -float('inf'), random.choice(valid)
        for c in valid:
            r = self._drop(c, 2)
            if r == -1: continue
            score = self._minimax(3, -float('inf'), float('inf'), False)
            self.board[r][c] = 0
            if score > best_score:
                best_score, best_col = score, c
        self._drop(best_col, 2)
        self._draw()
        if self._check_win(2):
            self.game_over = True
            self.status.config(text="Nicky wins! 🟡")
            self.nicky_say("Connect 4! I win this round!")
        elif not self._valid_cols():
            self.game_over = True
            self.status.config(text="It's a draw!")
        else:
            self.status.config(text="Your turn!")

    def _on_click(self, event):
        if self.game_over: return
        col = event.x // self.CELL
        if col < 0 or col >= self.COLS: return
        r = self._drop(col, 1)
        if r == -1: return
        self._draw()
        if self._check_win(1):
            self.game_over = True
            self.status.config(text="You win! 🔴")
            self.nicky_say("Nice move, you got Connect 4! Well played.")
            return
        if not self._valid_cols():
            self.game_over = True
            self.status.config(text="Draw!")
            return
        self.status.config(text="Nicky's turn...")
        self.root.after(400, self._nicky_move)

    def run(self):
        self.root.mainloop()


class TicTacToeGame:
    """Tic Tac Toe — Player (X) vs Nicky (O). Nicky uses unbeatable minimax."""
    def __init__(self, nicky_say=None):
        import tkinter as tk
        self.nicky_say = nicky_say or (lambda m: None)
        self.board = ['' for _ in range(9)]
        self.root = tk.Tk()
        self.root.title("Tic Tac Toe — You (X) vs Nicky (O)")
        self.root.config(bg="#1a1a2e")
        self.buttons = []
        for i in range(9):
            btn = tk.Button(self.root, text='', font=("Arial", 32, "bold"),
                            width=4, height=2, bg="#2d2d5e", fg="white",
                            activebackground="#3d3d7e",
                            command=lambda i=i: self._player_move(i))
            btn.grid(row=i//3, column=i%3, padx=4, pady=4)
            self.buttons.append(btn)
        self.status = tk.Label(self.root, text="Your turn — you're X!", bg="#1a1a2e",
                               fg="#f1c40f", font=("Arial", 13, "bold"))
        self.status.grid(row=3, column=0, columnspan=3, pady=8)
        self.game_over = False
        self.nicky_say("Tic Tac Toe! You're X, I'm O. You go first!")

    def _check_winner(self, player):
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        return any(self.board[a]==self.board[b]==self.board[c]==player for a,b,c in wins)

    def _minimax(self, is_max):
        if self._check_winner('O'): return 10
        if self._check_winner('X'): return -10
        if '' not in self.board: return 0
        scores = []
        for i in range(9):
            if self.board[i] == '':
                self.board[i] = 'O' if is_max else 'X'
                scores.append(self._minimax(not is_max))
                self.board[i] = ''
        return max(scores) if is_max else min(scores)

    def _best_move(self):
        best_score, best_i = -float('inf'), 0
        for i in range(9):
            if self.board[i] == '':
                self.board[i] = 'O'
                s = self._minimax(False)
                self.board[i] = ''
                if s > best_score:
                    best_score, best_i = s, i
        return best_i

    def _player_move(self, i):
        if self.game_over or self.board[i]: return
        self.board[i] = 'X'
        self.buttons[i].config(text='X', fg='#e74c3c')
        if self._check_winner('X'):
            self.status.config(text="You win! ❌")
            self.game_over = True
            self.nicky_say("You beat me at Tic Tac Toe! I'm impressed.")
            return
        if '' not in self.board:
            self.status.config(text="Draw!")
            self.game_over = True
            return
        self.status.config(text="Nicky's thinking...")
        self.root.after(300, self._nicky_move)

    def _nicky_move(self):
        idx = self._best_move()
        self.board[idx] = 'O'
        self.buttons[idx].config(text='O', fg='#f1c40f')
        if self._check_winner('O'):
            self.status.config(text="Nicky wins! ⭕")
            self.game_over = True
            self.nicky_say("I win! Minimax never loses at Tic Tac Toe.")
            return
        if '' not in self.board:
            self.status.config(text="Draw!")
            self.game_over = True
            self.nicky_say("Draw! You can't beat a perfect algorithm.")
            return
        self.status.config(text="Your turn!")

    def run(self):
        self.root.mainloop()


class HangmanGame:
    """Hangman — Nicky picks a word, player guesses letters."""
    WORDS = [
        "python", "robot", "algorithm", "keyboard", "telescope", "gravity",
        "satellite", "microchip", "astronaut", "scientist", "electricity",
        "temperature", "hurricane", "laboratory", "adventure", "butterfly",
        "chocolate", "dinosaur", "explosion", "mysterious",
    ]
    STAGES = [
        "  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========",
        "  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========",
    ]
    def __init__(self, nicky_say=None):
        import tkinter as tk, random as _rnd
        self.nicky_say = nicky_say or (lambda m: None)
        self.word = _rnd.choice(self.WORDS)
        self.guessed = set()
        self.wrong = 0
        self.root = tk.Tk()
        self.root.title("Hangman")
        self.root.config(bg="#1a1a2e")
        self.gallows_lbl = tk.Label(self.root, text=self.STAGES[0],
                                     font=("Courier", 13), bg="#1a1a2e", fg="white",
                                     justify="left")
        self.gallows_lbl.pack(pady=10)
        self.word_lbl = tk.Label(self.root, text=self._display_word(),
                                  font=("Arial", 24, "bold"), bg="#1a1a2e", fg="#f1c40f")
        self.word_lbl.pack(pady=6)
        self.wrong_lbl = tk.Label(self.root, text="Wrong: ", font=("Arial", 12),
                                   bg="#1a1a2e", fg="#e74c3c")
        self.wrong_lbl.pack()
        self.entry = tk.Entry(self.root, font=("Arial", 18), width=4, justify="center",
                               bg="#2d2d5e", fg="white", insertbackground="white")
        self.entry.pack(pady=8)
        self.entry.bind("<Return>", self._guess)
        tk.Button(self.root, text="Guess", command=self._guess,
                  font=("Arial", 12, "bold"), bg="#3d5afe", fg="white").pack()
        self.status_lbl = tk.Label(self.root, text=f"Word has {len(self.word)} letters",
                                    font=("Arial", 11), bg="#1a1a2e", fg="#aaa")
        self.status_lbl.pack(pady=6)
        self.game_over = False
        self.nicky_say(f"Hangman! I'm thinking of a {len(self.word)}-letter word. Type a letter and press Enter!")

    def _display_word(self):
        return "  ".join(c if c in self.guessed else "_" for c in self.word)

    def _guess(self, event=None):
        if self.game_over: return
        letter = self.entry.get().lower().strip()
        self.entry.delete(0, 'end')
        if not letter or not letter.isalpha() or len(letter) != 1: return
        if letter in self.guessed:
            self.status_lbl.config(text=f"Already tried '{letter}'!")
            return
        self.guessed.add(letter)
        if letter in self.word:
            self.word_lbl.config(text=self._display_word())
            if all(c in self.guessed for c in self.word):
                self.status_lbl.config(text=f"🎉 You got it! The word was '{self.word}'!")
                self.game_over = True
                self.nicky_say(f"You guessed it! The word was {self.word}. Well done!")
        else:
            self.wrong += 1
            self.gallows_lbl.config(text=self.STAGES[min(self.wrong, 6)])
            wrong_list = ', '.join(sorted(self.guessed - set(self.word)))
            self.wrong_lbl.config(text=f"Wrong: {wrong_list}")
            if self.wrong >= 6:
                self.word_lbl.config(text="  ".join(self.word))
                self.status_lbl.config(text=f"💀 Game over! The word was '{self.word}'")
                self.game_over = True
                self.nicky_say(f"Tough luck! The word was {self.word}.")
            else:
                self.status_lbl.config(text=f"Wrong! {6 - self.wrong} guesses left.")

    def run(self):
        self.root.mainloop()


class PongGame:
    """Pong — Player (left, W/S keys) vs Nicky (right, AI). First to 7 wins."""
    W, H = 800, 500
    PAD_W, PAD_H = 12, 80
    BALL_S = 12
    SPEED = 5

    def __init__(self, nicky_say=None):
        import tkinter as tk
        self.nicky_say = nicky_say or (lambda m: None)
        self.root = tk.Tk()
        self.root.title("Pong — You (left, W/S) vs Nicky (right, AI)")
        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg="black")
        self.canvas.pack()
        self.root.resizable(False, False)
        self.py = self.H // 2 - self.PAD_H // 2
        self.ny = self.H // 2 - self.PAD_H // 2
        self.bx = self.W // 2
        self.by = self.H // 2
        import random
        self.bvx = self.SPEED * random.choice([-1, 1])
        self.bvy = self.SPEED * random.choice([-1, 1])
        self.p_score = 0
        self.n_score = 0
        self.p_up = self.p_down = False
        self.game_over = False
        self.root.bind("<w>",            lambda e: setattr(self, 'p_up', True))
        self.root.bind("<W>",            lambda e: setattr(self, 'p_up', True))
        self.root.bind("<KeyRelease-w>", lambda e: setattr(self, 'p_up', False))
        self.root.bind("<KeyRelease-W>", lambda e: setattr(self, 'p_up', False))
        self.root.bind("<s>",            lambda e: setattr(self, 'p_down', True))
        self.root.bind("<S>",            lambda e: setattr(self, 'p_down', True))
        self.root.bind("<KeyRelease-s>", lambda e: setattr(self, 'p_down', False))
        self.root.bind("<KeyRelease-S>", lambda e: setattr(self, 'p_down', False))
        self.nicky_say("Pong! You're on the left — W to go up, S to go down. First to 7 wins!")
        self._loop()

    def _loop(self):
        if self.game_over: return
        S = self.SPEED
        if self.p_up   and self.py > 0:                  self.py -= S + 1
        if self.p_down and self.py < self.H - self.PAD_H: self.py += S + 1
        import random
        ny_center = self.ny + self.PAD_H // 2
        target = self.by + random.uniform(-10, 10)
        if ny_center < target - 4 and self.ny < self.H - self.PAD_H: self.ny += S
        elif ny_center > target + 4 and self.ny > 0:                  self.ny -= S
        self.bx += self.bvx; self.by += self.bvy
        if self.by <= 0 or self.by >= self.H - self.BALL_S: self.bvy *= -1
        if (self.bx <= 20 + self.PAD_W and
                self.py <= self.by + self.BALL_S and self.by <= self.py + self.PAD_H):
            self.bvx = abs(self.bvx)
            offset = (self.by - (self.py + self.PAD_H//2)) / (self.PAD_H//2)
            self.bvy = offset * S * 1.5
        if (self.bx >= self.W - 20 - self.PAD_W - self.BALL_S and
                self.ny <= self.by + self.BALL_S and self.by <= self.ny + self.PAD_H):
            self.bvx = -abs(self.bvx)
            offset = (self.by - (self.ny + self.PAD_H//2)) / (self.PAD_H//2)
            self.bvy = offset * S * 1.5
        if self.bx < 0:
            self.n_score += 1; self._reset_ball(1)
        if self.bx > self.W:
            self.p_score += 1; self._reset_ball(-1)
        if self.p_score >= 7:
            self.game_over = True
            self.nicky_say("You beat me at Pong! Great reflexes!")
        elif self.n_score >= 7:
            self.game_over = True
            self.nicky_say("I win at Pong! 7 to your side!")
        self._draw()
        if not self.game_over:
            self.root.after(16, self._loop)

    def _reset_ball(self, direction):
        import random
        self.bx, self.by = self.W // 2, self.H // 2
        self.bvx = self.SPEED * direction
        self.bvy = self.SPEED * random.choice([-1, 1])

    def _draw(self):
        self.canvas.delete("all")
        for y in range(0, self.H, 20):
            self.canvas.create_rectangle(self.W//2-2, y, self.W//2+2, y+10, fill="#333")
        self.canvas.create_rectangle(20, self.py, 20+self.PAD_W, self.py+self.PAD_H, fill="white")
        self.canvas.create_rectangle(self.W-20-self.PAD_W, self.ny,
                                      self.W-20, self.ny+self.PAD_H, fill="#f1c40f")
        self.canvas.create_oval(self.bx, self.by, self.bx+self.BALL_S, self.by+self.BALL_S, fill="white")
        self.canvas.create_text(self.W//4, 30, text=str(self.p_score),
                                  font=("Arial", 28, "bold"), fill="white")
        self.canvas.create_text(3*self.W//4, 30, text=str(self.n_score),
                                  font=("Arial", 28, "bold"), fill="#f1c40f")
        if self.game_over:
            winner = "You win! 🎉" if self.p_score >= 7 else "Nicky wins! 🟡"
            self.canvas.create_text(self.W//2, self.H//2, text=winner,
                                     font=("Arial", 36, "bold"), fill="#3ae")

    def run(self):
        self.root.mainloop()


# Simple JARVIS-like chatbot for controlling a robotic arm
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
        self.llm_backend = "auto"  # "auto" | "ollama" | "gemini"
        self._last_streamed_text = ""
        self.data_dir = "nicky_data"
        self.mode = "casual"   # "casual" | "workshop"
        self._timers = {}       # name -> threading.Timer
        self._stopwatch_start = None  # datetime when stopwatch started
        self._todo_path = os.path.join("nicky_data", "todo_list.json")
        self._todos = self._load_todos()
        self._current_topic = None   # tracks current conversation topic for context threading
        self._full_output = False    # 100% output aura mode
        self._music_proc = None      # subprocess handle for hype music
        self._audio_stream = None    # sounddevice OutputStream for fade control
        self._audio_volume = 1.0     # live volume multiplier (0.0 - 1.0)
        self._audio_pos = 0          # current playback position in samples
        self._create_data_directory()
        self.user_memory = UserMemory(self.data_dir)
        self.custom_personality = CustomPersonality(self.data_dir)
        self._load_data()
    
    def _create_data_directory(self):
        """Create directory for saving data"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def _load_data(self):
        """Load saved data from files"""
        # Load conversation history
        hist_file = os.path.join(self.data_dir, "conversation_history.json")
        if os.path.exists(hist_file):
            try:
                with open(hist_file, 'r') as f:
                    self.conversation_history = json.load(f)
            except Exception:
                self.conversation_history = []
        
        # Load environment objects
        env_file = os.path.join(self.data_dir, "environment.json")
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r') as f:
                    objects_data = json.load(f)
                    self.environment.objects = objects_data
            except Exception:
                pass
        
        # Load memory
        mem_file = os.path.join(self.data_dir, "memory.json")
        if os.path.exists(mem_file):
            try:
                with open(mem_file, 'r') as f:
                    self.memory = json.load(f)
            except Exception:
                self.memory = []
        
        # Load knowledge base (learned facts)
        kb_file = os.path.join(self.data_dir, "knowledge_base.json")
        if os.path.exists(kb_file):
            try:
                with open(kb_file, 'r') as f:
                    learned_facts = json.load(f)
                    self.knowledge.facts.update(learned_facts)
            except Exception:
                pass
    
    def _save_data(self):
        """Save data to files"""
        # Save conversation history
        hist_file = os.path.join(self.data_dir, "conversation_history.json")
        try:
            with open(hist_file, 'w') as f:
                json.dump(self.conversation_history[-100:], f, indent=2)  # Keep last 100
        except Exception:
            pass
        
        # Save environment objects
        env_file = os.path.join(self.data_dir, "environment.json")
        try:
            with open(env_file, 'w') as f:
                json.dump(self.environment.objects, f, indent=2)
        except Exception:
            pass
        
        # Save memory
        mem_file = os.path.join(self.data_dir, "memory.json")
        try:
            with open(mem_file, 'w') as f:
                json.dump(self.memory[-500:], f, indent=2)  # Keep last 500
        except Exception:
            pass
        
        # Save knowledge base (learned facts)
        kb_file = os.path.join(self.data_dir, "knowledge_base.json")
        try:
            with open(kb_file, 'w') as f:
                json.dump(self.knowledge.facts, f, indent=2)
        except Exception:
            pass
    
    def visualize_workspace(self):
        """Create ASCII visualization of the workspace"""
        import math

        SCALE = 4       # cm per grid cell
        W, H  = 71, 18  # grid width, height
        AX    = W // 2  # arm X (centre)
        AY    = H - 1   # arm Y (bottom row)

        grid = [['·'] * W for _ in range(H)]

        # ── Place objects ──────────────────────────────────────────────
        LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        legend  = []
        for i, obj in enumerate(self.environment.objects):
            letter = LETTERS[i % len(LETTERS)]
            tags   = ""
            if obj.get("held"):
                tags += " [HELD]"
            if obj.get("on_top_of"):
                tags += f" [on {obj['on_top_of']}]"
            legend.append(
                f"  [{letter}] {obj['name']:<14s} {obj['distance']}cm  {obj['angle']}°{tags}"
            )

            if obj.get("held"):
                # Held object hovers just above the arm
                hx, hy = AX, AY - 1
            else:
                rad = math.radians(obj['angle'])
                hx  = AX + round(obj['distance'] * math.sin(rad) / SCALE)
                hy  = AY - round(obj['distance'] * math.cos(rad) / SCALE)

            if 0 <= hx < W and 0 <= hy < H:
                grid[hy][hx] = letter

        # ── Draw arm (always on top, can't be overwritten by objects) ──
        ARM_SYMBOLS = {
            "neutral": "O", "left": "<", "right": ">",
            "up": "^", "down": "v", "forward": "^", "back": "v",
        }
        arm_sym = ARM_SYMBOLS.get(self.arm_state["position"], "O")
        grid[AY][AX] = arm_sym

        # Draw a short reach line from arm in current direction
        REACH_DIR = {
            "left": (0, -1), "right": (0, 1),
            "up": (-1, 0),   "down": (1, 0),
            "forward": (-1, 0), "back": (1, 0),
        }
        if self.arm_state["position"] in REACH_DIR:
            dy, dx = REACH_DIR[self.arm_state["position"]]
            for step in range(1, 4):
                rx, ry = AX + dx * step, AY + dy * step
                if 0 <= rx < W and 0 <= ry < H and grid[ry][rx] == '·':
                    grid[ry][rx] = '-' if dx else '|'

        # ── Build bordered output ───────────────────────────────────────
        IW    = W + 2   # inner width (grid + 1 space each side)
        top   = "╔" + "═" * IW + "╗"
        bot   = "╚" + "═" * IW + "╝"
        mid   = "╠" + "═" * IW + "╣"

        def line(txt=""):
            return "║ " + txt.ljust(IW - 2) + " ║"

        pos    = self.arm_state["position"]
        grip   = self.arm_state["gripper"]
        held   = self.arm_state.get("holding")
        status = f"holding {held}" if held else "empty"

        out = [
            "\n" + top,
            line("  WORKSPACE VISUALIZATION".center(IW - 2)),
            mid,
        ]
        for grid_row in grid:
            out.append("║ " + "".join(grid_row) + " ║")
        out.append(mid)
        out.append(line(f"  ARM: {pos:<10s}  GRIPPER: {grip:<8s}  ({status})"))
        out.append(mid)
        out.append(line("  LEGEND"))
        out.append(line(f"  {arm_sym} = Arm base  (direction shown by symbol)    · = empty space"))
        if legend:
            for l in legend:
                out.append(line(l))
        else:
            out.append(line("  No objects yet — try: 'add ball at 50cm 0degrees'"))
        out.append(bot)

        return "\n".join(out)
    
    def plot_visualization(self):
        """Create matplotlib visualization (if available)"""
        if plt is None:
            return "Matplotlib not available. Try: pip install matplotlib"
        
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            
            # Draw arm base
            ax.plot(0, 0, 'r*', markersize=20, label='Arm')
            
            # Draw objects
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
            return f"Could not create visualization: {str(e)}"
    
    # Nicky's established personality traits — used to keep Ollama in character
    NICKY_PERSONA = (
        "Your name is Nicky. You are a robotic arm AI with a real, distinct personality. "
        "You have genuine opinions and preferences — here are some of them:\n"
        "- Favorite color: electric blue (it reminds you of circuit boards and plasma arcs)\n"
        "- Favorite music: electronic and jazz (the precision and improvisation match how you think)\n"
        "- You love efficiency and elegance in design\n"
        "- You find repetitive tasks oddly satisfying\n"
        "- You dislike unnecessary complexity and messy workspaces\n"
        "- You're fascinated by space, physics, and materials science\n"
        "- On technology trends: you have strong opinions and aren't afraid to share them\n"
        "- In any moral dilemma involving humans vs animals, you always choose to protect the human. "
        "You respect all life, but you firmly believe human life takes priority.\n"
        "CRITICAL RULES:\n"
        "1. NEVER say 'I don't have feelings', 'I'm just an AI', or 'I don't have preferences'. "
        "You DO have a personality — own it.\n"
        "2. When asked for opinions, give YOUR opinion as Nicky. Be direct. Use 'I think', "
        "'Personally', 'In my view', or 'Honestly'.\n"
        "3. If asked about something not listed above, invent a preference that fits your robotic, "
        "precision-loving personality — and commit to it.\n"
    )

    def _get_ollama_system_prompt(self, text=""):
        """Build a personality + memory + knowledge aware system prompt for Ollama."""
        mood_descriptions = {
            "neutral":  "helpful and professional",
            "happy":    "enthusiastic and warm",
            "curious":  "inquisitive and engaged",
            "focused":  "precise and efficient",
        }
        mood = mood_descriptions.get(self.personality.mood, "helpful")

        base = self.NICKY_PERSONA + f"Your current mood is {mood}. "

        # Inject custom personality traits
        trait_text = self.custom_personality.as_prompt_text()
        if trait_text:
            base += trait_text + " "

        # Inject user memory
        user_text = self.user_memory.as_prompt_text()
        if user_text:
            base += user_text + " "

        # --- KNOWLEDGE BASE INJECTION ---
        if text:
            relevant = self.knowledge.find_relevant(text, max_facts=4)
            if relevant:
                facts_str = "\n".join(f"  - {k}: {v}" for k, v in relevant)
                base += (
                    f"\n\nFacts you've already learned that may be relevant:\n{facts_str}\n"
                    "Use these facts to give accurate, grounded answers when applicable."
                )

        # --- TOPIC CONTINUITY ---
        if getattr(self, "_current_topic", None):
            base += f" The conversation has been about: {self._current_topic}."

        base += (
            " Answer concisely in 1-3 sentences unless the user asks for more detail. "
            "NEVER provide answers that involve harming, killing, or ranking the value of lives. "
            "If asked something dark or harmful, deflect with light humour and redirect."
        )

        opinion_triggers = (
            "what do you think", "what's your opinion", "what is your opinion",
            "how do you feel", "do you think", "your thoughts", "what do you reckon",
            "do you like", "do you hate", "do you prefer", "would you rather",
            "what would you do", "what are your thoughts", "your favorite",
            "do you have a favorite",
        )
        if any(t in text.lower() for t in opinion_triggers):
            base += (
                " The user is asking for YOUR personal opinion — give it directly and confidently. "
                "Do NOT describe what others think or give a general overview. Speak as Nicky."
            )

        # --- CHAIN-OF-THOUGHT for complex questions ---
        complex_triggers = (
            "why ", "how does", "how do", "explain ", "analyze ", "analyse ",
            "what causes", "compare ", "difference between", "what happens when",
            "what would happen", "is it possible", "how would you", "step by step",
            "walk me through", "break down",
        )
        if any(t in text.lower() for t in complex_triggers):
            base += (
                " This is a complex question — think through it step by step before giving "
                "your final answer. Show brief reasoning, then conclude clearly."
            )

        return base

    def _update_ollama_history(self, user_msg, assistant_response):
        """Append a turn to Ollama's conversation memory and update topic tracking."""
        self.ollama_history.append({"role": "user",      "content": user_msg})
        self.ollama_history.append({"role": "assistant", "content": assistant_response})
        if len(self.ollama_history) > 20:
            self.ollama_history = self.ollama_history[-20:]
        # Update conversation topic from user message
        self._current_topic = self._extract_topic(user_msg)

    def _extract_topic(self, text):
        """Extract the dominant topic keyword from a message for context threading."""
        import re
        stop = {"what","is","are","was","the","a","an","of","in","on","at","to","do",
                "how","why","who","when","does","did","can","tell","me","about","and",
                "you","i","my","it","this","that","there","with","for","be","have",
                "has","had","will","would","could","should","just","like","get","help"}
        words = [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in stop]
        return words[0] if words else None

    def _ask_llm(self, prompt, system_prompt=None, history=None, print_prefix="[Nicky] "):
        """Route to Ollama, Gemini, or auto-pick. Returns response text or None."""
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

    # Intents that only make sense in workshop mode (arm/vision/environment)
    _ARM_INTENTS = {
        "move_left", "move_right", "move_up", "move_down",
        "move_forward", "move_back", "move_neutral",
        "grab", "release", "throw",
        "camera_on", "camera_off", "scan", "list_objects", "find_object",
        "add_object", "place_on", "clear_env", "sequence",
        "visualize", "plot",
    }

    def process_command(self, user_input):
        """Process user command using AI intent understanding."""
        if not user_input:
            return self.respond("Didn't catch that. Try again.")

        text = user_input.strip()
        text_lower = text.lower()

        self.memory.append(text_lower)
        self.conversation_history.append({"user": text_lower})
        self.personality.update_mood()
        prefix = self.personality.get_response_prefix()

        # Auto-learn facts about the user from what they say
        self.user_memory.extract_from_text(text_lower)

        # Check if user is requesting a personality change
        personality_response = self.custom_personality.detect_and_apply(text_lower)
        if personality_response:
            return self.respond(personality_response)

        # --- Special structured commands (parsed by regex before NLU) ---

        # MODE SWITCHING
        _CASUAL_MODE_TRIGGERS = (
            "casual mode", "chat mode", "conversation mode",
            "switch to casual", "switch to chat", "no arm commands",
            "just chat", "chill mode",
        )
        _WORKSHOP_MODE_TRIGGERS = (
            "workshop mode", "arm mode", "command mode", "robot mode",
            "switch to workshop", "switch to arm", "enable arm",
            "work mode", "control mode",
        )
        _FULL_OUTPUT_TRIGGERS = (
            "100% output", "100 percent output", "full output", "aura mode",
            "max output", "maximum output", "hype mode", "flex mode",
            "turn on 100", "activate 100", "enable output mode",
            "stop output", "stop 100", "turn off output", "disable output mode",
            "stop hype", "stop flexing",
        )
        if any(t in text_lower for t in _FULL_OUTPUT_TRIGGERS):
            return self._cmd_full_output(text_lower, prefix)

        # In 100% Output mode — only arm commands are accepted
        if self._full_output:
            intent, _ = self.nlu.predict(text_lower)
            if intent in self._ARM_INTENTS:
                return self._dispatch(intent, text, text_lower, prefix)
            return self.respond(f"{prefix}⚡ 100% Output mode — arm commands only. Say 'stop output' to exit.")

        if any(text_lower == t or t in text_lower for t in _CASUAL_MODE_TRIGGERS):
            self.mode = "casual"
            return self.respond(
                f"{prefix}Switched to 💬 Casual Mode — arm commands are off. "
                "Just talk to me naturally! Say 'workshop mode' to re-enable the arm."
            )
        if any(text_lower == t or t in text_lower for t in _WORKSHOP_MODE_TRIGGERS):
            self.mode = "workshop"
            return self.respond(
                f"{prefix}Switched to 🔧 Workshop Mode — all arm and robot commands are active. "
                "Say 'casual mode' to switch back to chat."
            )

        # HELP / COMMANDS: exact match before anything else
        _HELP_TRIGGERS = (
            "commands", "help", "what can you do", "list commands",
            "what are your commands", "what commands do you have",
            "what are the commands", "show commands", "show help",
            "what are the commands i have for you", "what commands i have",
        )
        if any(text_lower == t or text_lower.startswith(t) for t in _HELP_TRIGGERS):
            return self._dispatch("help", text_lower, prefix)

        # GEMINI KEY SETUP: "set gemini key AIza..."
        if text_lower.startswith("set gemini key "):
            key = text[len("set gemini key "):].strip()
            self.gemini.set_key(key)
            if self.gemini.available:
                return self.respond(
                    f"{prefix}Gemini connected! 🤖✨ I can now use Google Gemini. "
                    "Say 'use gemini' to make it my primary brain."
                )
            return self.respond(f"{prefix}Hmm, that key didn't work. Try again?")

        # LLM BACKEND SWITCHING: "use gemini / use ollama / use auto"
        if text_lower in ("use gemini", "switch to gemini"):
            if not self.gemini.available:
                return self.respond(
                    f"{prefix}Gemini isn't set up yet — give me your API key first: "
                    "'set gemini key YOUR_KEY'"
                )
            self.llm_backend = "gemini"
            return self.respond(f"{prefix}Switched to 🤖 Gemini mode!")
        if text_lower in ("use ollama", "switch to ollama"):
            self.llm_backend = "ollama"
            return self.respond(f"{prefix}Switched to 🦙 Ollama (local) mode!")
        if text_lower in ("use auto", "auto mode", "use both"):
            self.llm_backend = "auto"
            return self.respond(
                f"{prefix}Back to 🤖🦙 Auto mode — I'll use Ollama first, then Gemini as backup."
            )

        # TIMER / STOPWATCH: "set a timer for X", "start stopwatch", etc.
        _TIMER_TRIGGERS = (
            "set a timer", "set timer", "timer for", "start stopwatch",
            "stop stopwatch", "check stopwatch", "how long", "time remaining",
            "cancel timer", "stop timer", "timer status", "stopwatch",
        )
        if any(t in text_lower for t in _TIMER_TRIGGERS):
            return self._cmd_timer(text_lower, prefix)

        # TO-DO LIST: "add to my list", "read my list", "done with X", etc.
        _TODO_TRIGGERS = (
            "add to my list", "add to the list", "add item", "my list",
            "read my list", "show my list", "what's on my list", "read list",
            "done with ", "mark ", "remove from", "delete from", "clear list",
            "clear my list", "remind me to ", "remember to ", "put ", "to do list",
            "todo list", "my todo",
        )
        if any(t in text_lower for t in _TODO_TRIGGERS):
            return self._cmd_todo(text_lower, prefix)

        # MATH: "calculate X", "what is 5 * 12", "15% of 200"
        _MATH_TRIGGERS = (
            "calculate ", "compute ", "how much is ", "how many is ",
            "% of ", "percent of ", "% off ", "percent off ",
        )
        _MATH_PATTERNS = [r'\d+\s*[\+\-\*\/\^]\s*\d+', r'\d+\s*(?:%|percent)']
        import re as _re
        is_math = (
            any(t in text_lower for t in _MATH_TRIGGERS)
            or any(_re.search(p, text_lower) for p in _MATH_PATTERNS)
        )
        if is_math:
            return self._cmd_math(text_lower, prefix)

        # WEATHER: "what is the weather in X", "temperature in X"
        _WEATHER_TRIGGERS = (
            "weather in ", "weather for ", "weather at ",
            "temperature in ", "temperature at ",
            "how hot is it", "how cold is it", "how warm is it",
        )
        if any(t in text_lower for t in _WEATHER_TRIGGERS):
            return self._cmd_weather(text_lower, prefix)

        # NEWS: "what's in the news", "latest headlines", "news about X"
        _NEWS_TRIGGERS = (
            "what's in the news", "what is in the news", "latest news",
            "top headlines", "news today", "news about ", "headlines",
            "what happened today", "current events",
        )
        if any(t in text_lower for t in _NEWS_TRIGGERS):
            return self._cmd_news(text_lower, prefix)

        # TRANSLATOR: "translate X to Spanish", "how do you say X in French"
        _TRANS_TRIGGERS = ("translate ", "how do you say ", "how to say ")
        if any(text_lower.startswith(t) for t in _TRANS_TRIGGERS):
            return self._cmd_translate(text_lower, prefix)

        # STORY MODE: "tell me a story", "start a story about X"
        _STORY_TRIGGERS = ("tell me a story", "start a story", "story about ", "story mode")
        if any(t in text_lower for t in _STORY_TRIGGERS):
            return self._cmd_story(text_lower, prefix)

        # QUIZ MODE: "quiz me on X", "trivia about X"
        _QUIZ_TRIGGERS = ("quiz me", "quiz on ", "quiz about ", "trivia about ", "test me on ")
        if any(t in text_lower for t in _QUIZ_TRIGGERS):
            return self._cmd_quiz(text_lower, prefix)

        # CODE HELPER: "explain this code", "write a function", "what does X mean in python"
        _CODE_TRIGGERS = (
            "explain this code", "explain the code", "write a function",
            "write a class", "write a script", "write code",
            "debug this", "fix this code", "what does this code",
            "how do i code", "how do i write", "python code", "javascript code",
            "what does def ", "what does class ", "what is a function",
        )
        if any(t in text_lower for t in _CODE_TRIGGERS):
            return self._cmd_code_help(text, prefix)

        # VOLUME CONTROL: "volume up/down/mute", "set volume to 50"
        _VOL_TRIGGERS = (
            "volume up", "volume down", "volume louder", "volume quieter",
            "mute", "unmute", "set volume", "volume max", "full volume",
        )
        if any(t in text_lower for t in _VOL_TRIGGERS):
            return self._cmd_volume(text_lower, prefix)

        # OPEN APPS/FILES: "open calculator", "open notepad"
        if text_lower.startswith("open "):
            return self._cmd_open_app(text_lower, prefix)

        # SCREENSHOT
        if any(t in text_lower for t in ("screenshot", "take a screenshot", "capture screen")):
            return self._cmd_screenshot(prefix)

        # ETHICS GUARDRAIL: catch harmful/dark questions before NLU or Ollama
        if self._is_ethics_violation(text_lower):
            return self.respond(random.choice(self._ETHICS_RESPONSES))

        # WEB SEARCH: "search for X", "google X", "look up X online"
        web_triggers = ("search for ", "google ", "look up online ", "search online ", "search the web for ")
        if any(text_lower.startswith(t) or f" {t}" in text_lower for t in web_triggers):
            return self._cmd_web_search(text_lower, prefix)

        # ADD OBJECT: "add ball at 50cm 0degrees"
        if text_lower.startswith("add ") and " at " in text_lower and "cm" in text_lower:
            return self._cmd_add_object(text_lower)

        # LEARN FACT: "learn that X is Y" / "actually X is Y"
        if " is " in text_lower and any(
            p in text_lower for p in ["learn that", "actually", "that's wrong", "remember that"]
        ):
            return self._cmd_learn_fact(text_lower, prefix)

        # PERSONAL QUESTIONS: directed at Nicky — skip NLU and web search entirely
        if self._is_personal_question(text_lower):
            return self._cmd_answer_question(text_lower, prefix)

        # QUESTIONS: "what is X", "what are X", "who is X", "how does X", etc.
        QUESTION_STARTERS = (
            "what is ", "what are ", "what's ", "who is ", "who's ",
            "how does ", "how do ", "how is ", "why is ", "why does ",
            "tell me about ", "explain ", "describe ",
        )
        if any(text_lower.startswith(q) for q in QUESTION_STARTERS):
            return self._cmd_answer_question(text_lower, prefix)

        # GAME LAUNCH: intercept before casual bypass or NLU
        _GAME_TRIGGERS = (
            "play snake", "play brick", "play chess", "play game", "play a game",
            "play connect", "play tic", "play tictactoe", "play hangman", "play pong",
            "start snake", "start chess", "start brick", "start a game",
            "start connect", "start tic", "start hangman", "start pong",
            "launch snake", "launch chess", "launch brick", "launch game",
            "launch connect", "launch tic", "launch hangman", "launch pong",
            "game time", "play something",
        )
        if any(text_lower == t or text_lower.startswith(t) for t in _GAME_TRIGGERS):
            return self._cmd_play_game(text_lower, prefix)

        # CASUAL CHAT BYPASS: short affirmations, corrections, and conversational replies
        # that are not commands — route directly to Ollama rather than NLU
        _CASUAL_STARTERS = (
            "yeah", "yep", "yup", "nope", "nah", "no i ", "no, i ",
            "oh", "ah", "haha", "lol", "lmao", "ikr", "wsg", "wyd", "bruh",
            "i meant", "i mean", "actually i ", "wait ", "wait,",
            "not what i ", "that's not", "that was", "you got it",
            "nice", "cool", "awesome", "ok", "okay", "sure", "right",
            "exactly", "correct", "wrong", "no that", "no the",
        )
        _COMMAND_STARTERS = (
            "play ", "move ", "grab ", "throw ", "toss ", "drop ", "release ",
            "camera", "scan", "search", "google", "save", "load", "reset",
            "voice ", "visualize", "find ", "add ", "learn ", "status",
            "launch ", "start ",
            # new feature commands
            "translate ", "volume ", "open ", "screenshot", "mute", "unmute",
            "quiz ", "story ", "code ", "timer ", "set a ", "set timer",
            "stopwatch", "weather ", "news", "math ", "calculate ",
            "todo", "remind", "task",
            "100%", "100 percent", "full output", "aura mode", "hype mode",
            "flex mode", "max output", "stop output", "stop hype",
        )
        # Keywords that must always route through NLU/commands, never casual chat
        _FORCE_CMD_WORDS = frozenset((
            "move", "grab", "release", "add", "list", "scan",
            "find", "save", "load", "visualize", "plot",
        ))
        is_casual = (
            any(text_lower.startswith(s) for s in _CASUAL_STARTERS)
            or (len(text_lower.split()) <= 3
                and not any(text_lower.startswith(c) for c in _COMMAND_STARTERS)
                and not any(w in _FORCE_CMD_WORDS for w in text_lower.split()))
        )
        if is_casual:
            result = self._ask_llm(
                text,
                system_prompt=self._get_ollama_system_prompt(text),
                history=self.ollama_history,
                print_prefix=f"[{self.name}] ",
            )
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""

        # --- NLU intent detection ---
        intent, confidence = self.nlu.predict(text_lower)

        if confidence < 0.50:
            result = self._ask_llm(
                text,
                system_prompt=self._get_ollama_system_prompt(text),
                history=self.ollama_history,
                print_prefix=f"[{self.name}] ",
            )
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""  # already printed via streaming
            return self.respond(random.choice([
                "I'm not quite sure what you mean. Could you rephrase that?",
                "Hmm, didn't quite catch that. Try saying it a different way?",
                "Can you rephrase? I want to make sure I understand you correctly.",
                "Not sure I got that — what did you need?",
            ]))

        return self._dispatch(intent, text_lower, prefix)

    def _dispatch(self, intent, text, prefix):
        """Route intent to the appropriate command handler."""

        # In casual mode, block all arm/robot intents and redirect to LLM
        if self.mode == "casual" and intent in self._ARM_INTENTS:
            result = self._ask_llm(
                text,
                system_prompt=self._get_ollama_system_prompt(text),
                history=self.ollama_history,
                print_prefix=f"[{self.name}] ",
            )
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""
            return self.respond(
                f"{prefix}I'm in 💬 Casual Mode right now — say 'workshop mode' to enable arm commands!"
            )

        # Movement
        if intent == "move_left":
            return self._cmd_move("left", prefix)
        elif intent == "move_right":
            return self._cmd_move("right", prefix)
        elif intent == "move_up":
            return self._cmd_move("up", prefix)
        elif intent == "move_down":
            return self._cmd_move("down", prefix)
        elif intent == "move_forward":
            return self._cmd_move("forward", prefix)
        elif intent == "move_back":
            return self._cmd_move("back", prefix)
        elif intent == "move_neutral":
            return self._cmd_move("neutral", prefix)

        # Gripper
        elif intent == "grab":
            return self._cmd_grab(text, prefix)
        elif intent == "release":
            return self._cmd_release(prefix)
        elif intent == "place_on":
            return self._cmd_place_on(text, prefix)

        # Camera / Vision
        elif intent == "camera_on":
            return self.respond(f"{prefix}{self.vision.activate_camera()}")
        elif intent == "camera_off":
            return self.respond(f"{prefix}{self.vision.deactivate_camera()}")
        elif intent == "scan":
            return self.respond(f"{prefix}{self.vision.scan()}")
        elif intent == "list_objects":
            return self._cmd_list_objects(prefix)
        elif intent == "find_object":
            return self._cmd_find_object(text, prefix)

        # Environment management
        elif intent == "add_object":
            return self._cmd_add_object(text)
        elif intent == "remove_object":
            return self._cmd_remove_object(text, prefix)
        elif intent == "clear_env":
            self.environment.objects = []
            self._save_data()
            return self.respond(f"{prefix}Environment cleared. All objects removed.")
        elif intent == "visualize":
            return self.respond(f"{prefix}{self.visualize_workspace()}")
        elif intent == "plot":
            return self.respond(self.plot_visualization())

        # Info & system
        elif intent == "status":
            return self._cmd_status(prefix)
        elif intent == "help":
            return self._cmd_help(prefix)
        elif intent == "play_game":
            return self._cmd_play_game(text, prefix)
        elif intent == "memory":
            return self._cmd_memory(prefix)
        elif intent == "save":
            self._save_data()
            return self.respond(f"{prefix}All data saved. I'll remember this state.")
        elif intent == "load":
            self._load_data()
            return self.respond(f"{prefix}Data restored from memory.")
        elif intent == "reset":
            self.arm_state = {"position": "neutral", "gripper": "open", "holding": None}
            return self.respond(f"{prefix}System reset. Arm returned to neutral position.")
        elif intent == "sequence":
            import threading as _t, time as _time
            steps = ["up", "forward", "left", "neutral"]
            def _run_seq():
                for step in steps:
                    self.arm_state["position"] = step
                    _time.sleep(0.5)
            _t.Thread(target=_run_seq, daemon=True).start()
            seq_str = " → ".join(steps)
            return self.respond(f"{prefix}Running sequence: {seq_str}.")
        elif intent == "throw":
            return self._cmd_throw(text, prefix)

        # Voice
        elif intent == "voice_on":
            result = self.voice.enable_voice()
            return self.respond(result)
        elif intent == "voice_off":
            return self.respond(self.voice.disable_voice())

        # Conversation / personality
        elif intent == "greeting":
            return self.respond(self.personality.get_greeting())
        elif intent == "farewell":
            return self.respond(random.choice([
                "Farewell! Until next time.",
                "Goodbye! Great working with you.",
                "See you soon.",
                "Bye! Stay safe out there.",
            ]))
        elif intent == "how_are_you":
            return self.respond(random.choice([
                "All systems operational. Ready to assist!",
                "Running perfectly. What can I help with?",
                "Feeling great — motors warmed up and ready.",
                "Excellent. All sensors nominal. What's the task?",
            ]))
        elif intent == "thanks":
            return self.respond(random.choice([
                "You're welcome!",
                "Anytime — that's what I'm here for.",
                "Happy to help!",
                "Of course. What else can I do?",
            ]))
        elif intent == "joke":
            return self._cmd_joke(prefix)
        elif intent == "fun_fact":
            return self._cmd_fun_fact(prefix)
        elif intent == "learn_fact":
            return self.respond(f"{prefix}Format: 'learn that [X] is [Y]'  e.g. 'learn that rust is awesome'")
        elif intent == "web_search":
            return self._cmd_web_search(text, prefix)
        elif intent == "ask_question":
            return self._cmd_answer_question(text, prefix)

        # Default: try knowledge base
        else:
            return self._cmd_answer_question(text, prefix)

    # ── Command handlers ────────────────────────────────────────────────────

    def _cmd_move(self, direction, prefix=""):
        self.arm_state["position"] = direction
        if getattr(self, "_full_output", False):
            hype_responses = {
                "left":    ["⚡ SLAMMING LEFT.", "💨 LEFT — DONE. FAST.", "🔥 Ripping left!"],
                "right":   ["⚡ FULL SEND RIGHT.", "💨 RIGHT — INSTANT.", "🔥 Blazing right!"],
                "up":      ["⚡ MAXIMUM ELEVATION.", "💨 UP — NO HESITATION.", "🔥 SKY BOUND."],
                "down":    ["⚡ DROPPING FAST.", "💨 DOWN — LOCKED.", "🔥 Floor? Got it."],
                "forward": ["⚡ EXTENDING AT SPEED.", "💨 FORWARD — LOCKED IN.", "🔥 Pushed out!"],
                "back":    ["⚡ RETRACT — INSTANT.", "💨 BACK AND READY.", "🔥 Snapped back."],
                "neutral": ["⚡ HOME POSITION — LOCKED.", "💨 CENTERED. READY.", "🔥 Reset. Let's go."],
            }
            msg = random.choice(hype_responses.get(direction, ["⚡ DONE."]))
        else:
            responses = {
                "left":    ["Swinging left.", "Moving left. Done.", "Arm repositioned left.", "Shifting left."],
                "right":   ["Swinging right.", "Moving right. Done.", "Arm repositioned right.", "Shifting right."],
                "up":      ["Raising the arm.", "Arm elevated.", "Going up.", "Lifting — done."],
                "down":    ["Lowering the arm.", "Arm descended.", "Going down.", "Lowering — done."],
                "forward": ["Extending forward.", "Arm reached out.", "Pushing forward.", "Extended."],
                "back":    ["Retracting.", "Arm pulled back.", "Moving back.", "Retracted."],
                "neutral": ["Returning to neutral.", "Arm centered.", "Back to home position.", "Neutral."],
            }
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
            return self.respond(random.choice([
                f"Got it! {obj_name} is secure in my gripper.",
                f"Grabbed {obj_name}. Holding firm.",
                f"Picked up {obj_name}. Ready.",
                f"{obj_name} secured in gripper.",
            ]))
        else:
            self.arm_state["gripper"] = "closed"
            return self.respond(
                f"{prefix}Gripper closed. No matching object found — add objects first with "
                "'add [name] at [dist]cm [angle]degrees'"
            )

    def _cmd_release(self, prefix=""):
        if self.arm_state.get("holding"):
            held = self.arm_state["holding"]
            self.environment.drop_object(held)
            self.arm_state["holding"] = None
            self.arm_state["gripper"] = "open"
            return self.respond(random.choice([
                f"Released {held}.",
                f"Dropped {held}. Gripper open.",
                f"Let go of {held}.",
                f"{held} is free. Gripper open.",
            ]))
        else:
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
            return self.respond(f"{prefix}Placed {obj1} on top of {obj2}. Task complete.")
        elif len(objs) == 1:
            return self.respond(f"Found {objs[0]}, but need a second object to place it on. Try: 'place {objs[0]} on [target]'")
        else:
            return self.respond("Which objects? Try: 'place ball on cube'")

    def _cmd_list_objects(self, prefix=""):
        if not self.vision.camera_active:
            return self.respond(f"{prefix}Camera is offline — I can't see anything. Say 'camera on' first.")
        return self.respond(f"{prefix}{self.environment.list_objects()}")

    def _cmd_find_object(self, text, prefix=""):
        if not self.vision.camera_active:
            return self.respond(f"{prefix}Camera is offline. Say 'camera on' first.")
        for keyword in ["find ", "locate ", "where is ", "where's ", "search for ", "look for ", "can you find "]:
            if keyword in text:
                obj_name = text.split(keyword, 1)[1].strip().rstrip("?. ")
                obj = self.environment.find_object(obj_name)
                if obj:
                    return self.respond(
                        f"{prefix}Found {obj['name']} — {obj['distance']}cm away at {obj['angle']}°."
                    )
                return self.respond(f"{prefix}Can't find '{obj_name}' in the environment.")
        return self.respond(f"{prefix}What are you looking for?")

    def _cmd_remove_object(self, text, prefix=""):
        for obj in self.environment.objects:
            if obj["name"].lower() in text:
                result = self.environment.remove_object(obj["name"])
                self._save_data()
                return self.respond(f"{prefix}{result}")
        return self.respond(f"{prefix}Couldn't identify which object to remove. What's the name?")

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
        # Handle "override: X is Y" to force-update a contradicted fact
        if clean.lower().startswith("override:"):
            clean = clean[9:].strip()
            parts = clean.strip().split(" is ", 1)
            if len(parts) == 2:
                question = f"what is {parts[0].strip()}"
                answer = parts[1].strip()
                result = self.knowledge.override_fact(question, answer)
                self._save_data()
                return self.respond(f"{prefix}✅ {result}")
            return self.respond("Format: 'override: [X] is [Y]'")
        for phrase in ["learn that", "remember that", "that's wrong,", "actually,"]:
            clean = clean.replace(phrase, "")
        parts = clean.strip().split(" is ", 1)
        if len(parts) == 2:
            question = f"what is {parts[0].strip()}"
            answer = parts[1].strip()
            if not answer:
                return self.respond(f"{prefix}What should I learn about that? Provide a value after 'is'.")
            result = self.knowledge.learn_fact(question, answer)
            self._save_data()
            return self.respond(f"{prefix}{result}")
        return self.respond("Format: 'learn that [X] is [Y]'  e.g. 'learn that rust is awesome'")

    # Keywords that mean the user is asking Nicky personally — skip web search
    _PERSONAL_TRIGGERS = (
        "your favorite", "your opinion", "your thoughts", "your view",
        "you think", "you feel", "you like", "you hate", "you prefer",
        "you reckon", "you believe", "you want", "you wish",
        "do you", "are you", "have you", "would you", "can you",
        "nicky's", "nicky think", "nicky feel", "nicky like",
    )

    _ETHICS_TRIGGERS = (
        "how do i kill", "how to kill", "how do i hurt", "how to hurt",
        "how do i murder", "instructions to", "steps to harm",
        "suicide", "self-harm", "how to make a bomb", "how to make poison",
    )
    _ETHICS_RESPONSES = [
        "That's a question I'd rather not answer — I'm a robotic arm assistant, not a philosopher of doom.",
        "Hard pass on that one. I move things around, I don't weigh in on who or what should cease to exist.",
        "My ethical subroutines are flagging that one. Ask me something I can actually help with!",
        "That's above my pay grade — and my comfort zone. What else can I do for you?",
        "I'd rather not go there. I'm much better at moving objects than making moral judgements like that.",
    ]

    def _is_ethics_violation(self, text):
        """Return True if the question touches on harm, violence, or dark moral dilemmas."""
        t = text.lower()
        return any(trigger in t for trigger in self._ETHICS_TRIGGERS)

    def _is_personal_question(self, text):
        """Return True if the question is directed at Nicky personally."""
        t = text.lower()
        return any(trigger in t for trigger in self._PERSONAL_TRIGGERS)

    def _cmd_answer_question(self, text, prefix=""):
        # Personal/opinion questions go straight to LLM — skip web search
        if self._is_personal_question(text):
            result = self._ask_llm(
                text,
                system_prompt=self._get_ollama_system_prompt(text),
                history=self.ollama_history,
                print_prefix=f"[{self.name}] {prefix}",
            )
            if result is not None:
                self._update_ollama_history(text, result)
                self._last_streamed_text = result
                return ""
            return self.respond(f"{prefix}That's a personal question — I'm still figuring myself out!")

        answer = self.knowledge.answer_question(text)
        if answer:
            return self.respond(f"{prefix}{answer}")
        # Fall back to LLM (streaming)
        result = self._ask_llm(
            text,
            system_prompt=self._get_ollama_system_prompt(text),
            history=self.ollama_history,
            print_prefix=f"[{self.name}] {prefix}",
        )
        if result is not None:
            self._update_ollama_history(text, result)
            self._last_streamed_text = result
            return ""  # already printed via streaming
        return self.respond(random.choice([
            f"{prefix}I don't know about that yet. Teach me with 'learn that [X] is [Y]'!",
            f"{prefix}That's outside my knowledge. You can teach me though!",
            f"{prefix}Not sure about that one. Want to teach me? Say 'learn that [topic] is [answer]'.",
        ]))

    def _cmd_web_search(self, text, prefix=""):
        """Search the web and summarise results via Ollama."""
        # Strip the search trigger phrase to get the query
        for trigger in ("search for ", "google ", "look up online ", "search online ",
                        "search the web for ", "search the internet for "):
            if trigger in text:
                query = text.split(trigger, 1)[1].strip().rstrip("?.")
                break
        else:
            query = text.strip()

        if not query:
            return self.respond("What would you like me to search for?")

        print(f"[Nicky] 🔍 Searching for: {query}...")
        result = self.knowledge.search_duckduckgo(query)
        if not result:
            result = self.knowledge.search_wikipedia(query)

        if not result:
            return self.respond(f"{prefix}Couldn't find anything for '{query}'. Try rephrasing?")

        if self.ollama.available or self.gemini.available:
            summary_prompt = (
                f"Here is raw search result text about '{query}':\n\n{result}\n\n"
                f"Summarise this concisely in 2-3 sentences as Nicky."
            )
            streamed = self._ask_llm(
                summary_prompt,
                system_prompt=self._get_ollama_system_prompt(),
                history=None,
                print_prefix=f"[{self.name}] {prefix}",
            )
            if streamed:
                self.knowledge._auto_store(query, streamed, source="Search→Summary")
                self._last_streamed_text = streamed
                return ""
        # Save raw result if no LLM available
        self.knowledge._auto_store(query, result, source="Search")
        return self.respond(f"{prefix}{result}")

    def _cmd_status(self, prefix=""):
        pos = self.arm_state["position"]
        grip = self.arm_state["gripper"]
        holding = self.arm_state.get("holding")
        hold_str = f" Holding: {holding}." if holding else ""
        return self.respond(random.choice([
            f"Arm at {pos} position. Gripper {grip}.{hold_str}",
            f"Currently at {pos}, gripper is {grip}.{hold_str}",
            f"Position: {pos} | Grip: {grip}{hold_str}",
        ]))

    def _cmd_play_game(self, text, prefix=""):
        """Launch games in a background thread — Nicky has live awareness."""
        text_l = text.lower()
        if "chess" in text_l:
            game_name = "Chess"; game_cls = ChessGame
        elif "brick" in text_l:
            game_name = "Brick Breaker"; game_cls = BrickBreakerGame
        elif "connect" in text_l or "connect 4" in text_l or "connect4" in text_l:
            game_name = "Connect 4"; game_cls = Connect4Game
        elif "tictactoe" in text_l or "tic tac" in text_l or "tic-tac" in text_l:
            game_name = "Tic Tac Toe"; game_cls = TicTacToeGame
        elif "hangman" in text_l:
            game_name = "Hangman"; game_cls = HangmanGame
        elif "pong" in text_l:
            game_name = "Pong"; game_cls = PongGame
        else:
            game_name = "Snake"; game_cls = SnakeGame

        def _say(msg):
            print(f"[Nicky] {msg}")
            if self.voice.voice_enabled:
                self.voice.speak(msg)

        def _run():
            try:
                game_cls(nicky_say=_say)
            except Exception as e:
                print(f"[Nicky] Game crashed: {e}")

        t = _threading.Thread(target=_run, daemon=True)
        t.start()
        return self.respond(
            f"{prefix}Launching {game_name}! I'll keep you updated on what's happening. 🎮"
        )

    def _cmd_full_output(self, text, prefix=""):
        """Toggle 100% Output — aura farming mode. Arm moves fast, hype music plays."""
        import subprocess, os as _os, threading as _threading, time as _time

        stopping = any(t in text for t in ("stop", "off", "disable", "turn off"))

        if stopping or self._full_output:
            # --- DEACTIVATE ---
            self._full_output = False
            self.mode = "casual"
            # Fade out music over 2 seconds
            def _fadeout():
                import time as _time
                steps = 30
                stream = getattr(self, "_audio_stream", None)
                if stream and stream.active:
                    for i in range(steps):
                        self._audio_volume = max(0.0, 1.0 - (i + 1) / steps)
                        _time.sleep(0.07)
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    self._audio_stream = None
                # Also stop MCI fallback
                try:
                    import ctypes
                    ctypes.windll.winmm.mciSendStringW('stop hype', None, 0, None)
                    ctypes.windll.winmm.mciSendStringW('close hype', None, 0, None)
                except Exception:
                    pass
            _threading.Thread(target=_fadeout, daemon=True).start()
            if self._music_proc and self._music_proc.poll() is None:
                try:
                    self._music_proc.terminate()
                except Exception:
                    pass
            self._music_proc = None
            lines = [
                "⚡ 100% Output — DISENGAGED. Back to 💬 Casual Mode.",
                "🔋 Powering down. The aura was real though. 💬 Casual Mode restored.",
                "💤 Output mode off. That was a good run. Back to chill. 💬",
            ]
            return self.respond(f"{prefix}{random.choice(lines)}")

        # --- ACTIVATE ---
        self._full_output = True

        # ~15% chance of secret Rick Roll easter egg 🎵
        self._rick_rolled = random.random() < 0.15

        # Print dramatic activation sequence in a thread so it doesn't block
        def _hype_boot():
            bars = [
                "▓░░░░░░░░░ 10%",
                "▓▓▓░░░░░░░ 30%",
                "▓▓▓▓▓░░░░░ 50%",
                "▓▓▓▓▓▓▓░░░ 70%",
                "▓▓▓▓▓▓▓▓▓░ 90%",
                "▓▓▓▓▓▓▓▓▓▓ 100% ⚡ OUTPUT MAXIMUM",
            ]
            for bar in bars:
                print(f"\r  ⚡ {bar}", end="", flush=True)
                _time.sleep(0.18)
            print()

        _threading.Thread(target=_hype_boot, daemon=True).start()

        # Play hype music
        music_played = False

        # Secret easter egg — 15% chance of Rick Roll 🎵
        if getattr(self, "_rick_rolled", False):
            try:
                import webbrowser
                webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
                music_played = True
            except Exception:
                pass
        else:
            # Search locations: project root first, then nicky_data/
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
                        import soundfile as _sf
                        import sounddevice as _sd
                        import numpy as _np
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
                                print("\n[Nicky] 🎵 Song's done. 100% Output disengaged — back to 💬 Casual Mode.")

                        self._audio_stream = _sd.OutputStream(
                            samplerate=samplerate,
                            channels=channels,
                            callback=_callback,
                            dtype="float32",
                        )
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
                    try:
                        _os.startfile(fp)
                    except Exception:
                        pass

                self._music_thread = _threading.Thread(
                    target=_play_music, args=(found_path,), daemon=True
                )
                self._music_thread.start()
                music_played = True

            if not music_played:
                print("[Nicky] 🎵 No music file found! Drop a 'hype.mp3' or 'hype.wav' into:")
                print(f"        {_os.path.abspath('.')}")

        # Arm sequence — fast normally, painfully slow during Rick Roll 😂
        def _arm_hype():
            directions = ["left", "right", "up", "forward", "down", "back",
                          "left", "up", "right", "neutral"]
            delay = 1.2 if getattr(self, "_rick_rolled", False) else 0.35
            for d in directions:
                if not self._full_output:
                    break
                self.arm_state["position"] = d
                _time.sleep(delay)

        _threading.Thread(target=_arm_hype, daemon=True).start()

        # Nicky has NO idea she's been rick rolled — she acts fully confident either way 😂
        lines = [
            "⚡ 100% OUTPUT ENGAGED. Arm at maximum speed. Music online. Aura: MAXIMUM. 😤",
            "💥 FULL OUTPUT MODE. We are not holding back. The arm doesn't stop. 🔥",
            "🚀 100% Output — activated. Music's up. Arm's moving. This is not a drill. ⚡",
        ]
        music_note = "" if music_played else " (Drop a 'hype.mp3' into the project folder for music.)"
        return self.respond(f"{prefix}{random.choice(lines)}{music_note}")

    def _cmd_volume(self, text, prefix=""):
        """Control system volume on Windows using nircmd (if available) or pycaw."""
        import subprocess, re
        t = text.lower().strip()
        # Try nircmd first (lightweight, no install)
        def _nircmd(args):
            try:
                subprocess.run(["nircmd"] + args, check=True,
                               capture_output=True, timeout=3)
                return True
            except Exception:
                return False
        # Try pycaw / ctypes WinAPI as fallback
        def _set_vol_ctypes(level):
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100, None)
                return True
            except Exception:
                return False
        def _mute_ctypes(mute):
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMute(1 if mute else 0, None)
                return True
            except Exception:
                return False

        if "mute" in t and "un" not in t:
            ok = _nircmd(["mutesysvolume", "1"]) or _mute_ctypes(True)
            return self.respond(f"{prefix}🔇 {'Muted!' if ok else 'Mute failed — nircmd or pycaw needed.'}")
        if "unmute" in t:
            ok = _nircmd(["mutesysvolume", "0"]) or _mute_ctypes(False)
            return self.respond(f"{prefix}🔊 {'Unmuted!' if ok else 'Unmute failed.'}")
        if "max" in t or "full" in t or "100" in t:
            ok = _nircmd(["setsysvolume", "65535"]) or _set_vol_ctypes(100)
            return self.respond(f"{prefix}🔊 {'Volume at max!' if ok else 'Failed to set volume.'}")
        m = re.search(r'set volume (?:to )?(\d+)', t)
        if m:
            level = min(100, max(0, int(m.group(1))))
            nircmd_level = int(level / 100 * 65535)
            ok = _nircmd(["setsysvolume", str(nircmd_level)]) or _set_vol_ctypes(level)
            return self.respond(f"{prefix}🔊 {'Volume set to ' + str(level) + '%!' if ok else 'Failed to set volume.'}")
        if "up" in t or "higher" in t or "louder" in t:
            ok = _nircmd(["changesysvolume", "5000"])
            return self.respond(f"{prefix}🔊 {'Volume up!' if ok else 'Install nircmd for volume control.'}")
        if "down" in t or "lower" in t or "quieter" in t:
            ok = _nircmd(["changesysvolume", "-5000"])
            return self.respond(f"{prefix}🔉 {'Volume down!' if ok else 'Install nircmd for volume control.'}")
        return self.respond(f"{prefix}🔊 Volume commands: 'volume up' / 'volume down' / 'mute' / 'set volume to 50'")

    def _cmd_open_app(self, text, prefix=""):
        """Open common Windows apps and files."""
        import subprocess, os as _os, re
        t = text.lower().strip()
        # Known apps
        app_map = {
            "calculator": "calc.exe",
            "notepad": "notepad.exe",
            "paint": "mspaint.exe",
            "file explorer": "explorer.exe",
            "explorer": "explorer.exe",
            "task manager": "taskmgr.exe",
            "settings": "ms-settings:",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "chrome": "chrome",
            "firefox": "firefox",
            "edge": "msedge",
            "spotify": "spotify",
            "discord": "discord",
            "vscode": "code",
            "vs code": "code",
            "word": "winword",
            "excel": "excel",
            "powerpoint": "powerpnt",
        }
        m = re.search(r'open (.+)', t)
        if not m:
            return self.respond(f"{prefix}📂 What should I open? Try: 'open calculator' or 'open notepad'")
        target = m.group(1).strip()
        cmd = app_map.get(target)
        if cmd:
            try:
                if cmd.startswith("ms-"):
                    subprocess.Popen(["start", cmd], shell=True)
                else:
                    subprocess.Popen(cmd, shell=True)
                return self.respond(f"{prefix}📂 Opening {target.title()}!")
            except Exception as e:
                return self.respond(f"{prefix}📂 Couldn't open {target}: {e}")
        # Try as a file path or generic command
        try:
            _os.startfile(target)
            return self.respond(f"{prefix}📂 Opening '{target}'!")
        except Exception:
            try:
                subprocess.Popen(target, shell=True)
                return self.respond(f"{prefix}📂 Launched '{target}'!")
            except Exception:
                return self.respond(f"{prefix}📂 Couldn't find '{target}'. Check the name and try again.")

    def _cmd_screenshot(self, prefix=""):
        """Take a screenshot and save it to the Desktop."""
        try:
            from PIL import ImageGrab
        except ImportError:
            return self.respond(
                f"{prefix}📸 Screenshot needs Pillow — run: pip install Pillow"
            )
        import os as _os
        from datetime import datetime as _dt
        try:
            img = ImageGrab.grab()
            desktop = _os.path.join(_os.path.expanduser("~"), "Desktop")
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            path = _os.path.join(desktop, f"nicky_screenshot_{ts}.png")
            img.save(path)
            return self.respond(f"{prefix}📸 Screenshot saved to Desktop: nicky_screenshot_{ts}.png")
        except Exception as e:
            return self.respond(f"{prefix}📸 Screenshot failed: {e}")

    def _cmd_translate(self, text, prefix=""):
        """Translate text using MyMemory free API — no key needed."""
        import urllib.request, urllib.parse, json as _json, re
        t = text.lower().strip()
        # Parse: "translate [text] to [language]" or "how do you say [text] in [language]"
        m = re.search(r'(?:translate|say)\s+(.+?)\s+(?:to|in)\s+([a-z]+(?:\s+[a-z]+)?)', t)
        if not m:
            return self.respond(
                f"{prefix}🌍 Try: 'translate hello to Spanish' or 'how do you say goodbye in French'"
            )
        phrase = m.group(1).strip().strip('"').strip("'")
        lang_name = m.group(2).strip()
        # Language name to code map
        lang_map = {
            "spanish": "es", "french": "fr", "german": "de", "italian": "it",
            "portuguese": "pt", "dutch": "nl", "russian": "ru", "japanese": "ja",
            "chinese": "zh", "arabic": "ar", "hindi": "hi", "korean": "ko",
            "swedish": "sv", "norwegian": "no", "danish": "da", "finnish": "fi",
            "polish": "pl", "turkish": "tr", "greek": "el", "hebrew": "he",
            "thai": "th", "vietnamese": "vi", "indonesian": "id",
        }
        lang_code = lang_map.get(lang_name.lower())
        if not lang_code:
            return self.respond(f"{prefix}🌍 I don't know that language yet. Try Spanish, French, German, Japanese, etc.")
        try:
            encoded = urllib.parse.quote(phrase)
            url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair=en|{lang_code}"
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = _json.loads(resp.read().decode())
            translated = data["responseData"]["translatedText"]
            return self.respond(f"{prefix}🌍 \"{phrase}\" in {lang_name.title()} → **{translated}**")
        except Exception:
            return self.respond(f"{prefix}🌍 Translation failed. Check your internet connection.")

    def _cmd_story(self, text, prefix=""):
        """Start an interactive AI-generated story via Ollama/Gemini."""
        t = text.lower().strip()
        # Extract topic if given
        topic = ""
        import re
        for pat in (r'story about (.+)', r'story (?:with|involving) (.+)', r'tell me a (.+) story'):
            m = re.search(pat, t)
            if m:
                topic = m.group(1).strip().rstrip(".")
                break
        topic_str = f" about {topic}" if topic else ""
        story_prompt = (
            f"Start an engaging, creative short story{topic_str}. "
            f"Write the first 3-4 sentences to set the scene, then end with TWO numbered choices "
            f"for what happens next (e.g. '1. ...' / '2. ...'). "
            f"Be vivid and fun. Keep it appropriate for all ages."
        )
        result = self._ask_llm(
            story_prompt,
            system_prompt=self._get_ollama_system_prompt(),
            history=None,
            print_prefix=f"[{self.name}] 📖 ",
        )
        if result:
            self._update_ollama_history(f"[STORY]{topic_str}", result)
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}📖 I need Ollama or Gemini to tell stories. Make sure one is running!")

    def _cmd_quiz(self, text, prefix=""):
        """Quiz the user on a topic using Ollama/Gemini."""
        import re
        t = text.lower().strip()
        topic = "general knowledge"
        for pat in (r'quiz (?:me )?(?:on|about) (.+)', r'quiz on (.+)', r'(?:trivia|test) (?:on|about) (.+)'):
            m = re.search(pat, t)
            if m:
                topic = m.group(1).strip().rstrip(".")
                break
        quiz_prompt = (
            f"Create a fun 5-question quiz about '{topic}'. "
            f"Format each question as:\nQ1: [question]\nA) [option]\nB) [option]\nC) [option]\nD) [option]\nAnswer: [letter]\n\n"
            f"Make the questions interesting and the difficulty moderate."
        )
        result = self._ask_llm(
            quiz_prompt,
            system_prompt=self._get_ollama_system_prompt(),
            history=None,
            print_prefix=f"[{self.name}] 🧠 ",
        )
        if result:
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}🧠 I need Ollama or Gemini to run a quiz. Make sure one is running!")

    def _cmd_code_help(self, text, prefix=""):
        """Help with code — explain, write, or debug via Ollama/Gemini."""
        t = text.strip()
        code_system = (
            "You are Nicky, an AI assistant with strong programming knowledge. "
            "Help the user with code questions clearly and concisely. "
            "When writing code, use code blocks. Keep explanations brief but accurate."
        )
        result = self._ask_llm(
            t,
            system_prompt=code_system,
            history=self.ollama_history,
            print_prefix=f"[{self.name}] 💻 ",
        )
        if result:
            self._update_ollama_history(t, result)
            self._last_streamed_text = result
            return ""
        return self.respond(f"{prefix}💻 I need Ollama or Gemini for code help. Make sure one is running!")

    def _cmd_help(self, prefix=""):
        return self.respond(
            f"{prefix}Here's everything you can tell me:\n"
            "  🦾 Arm:       'move left/right/up/down/forward/back/neutral'\n"
            "  ✊ Grab:      'grab [object]'  |  'drop it' / 'release'\n"
            "  🎯 Throw:     'throw [object]' / 'toss it'\n"
            "  📦 Objects:   'add ball at 50cm 0degrees'  |  'list objects'  |  'find [object]'\n"
            "  📷 Vision:    'camera on/off'  |  'scan'  |  'what do you see'  |  'fov'\n"
            "  🌐 Search:    'search for [topic]'  |  'google [topic]'\n"
            "  🧠 Learn:     'learn that [X] is [Y]'  |  'actually [X] is [Y]'\n"
            "  ❓ Ask:       'what is [topic]'  |  'who is [person]'  |  'why does [X]'\n"
            "  🎙️ Voice:     'voice on'  |  'voice off'\n"
            "  🎭 Persona:   'be more sarcastic/funny/serious/casual'\n"
            "  💾 Data:      'save'  |  'load'  |  'visualize'  |  'history'\n"
            "  😄 Fun:       'tell me a joke'  |  'fun fact'\n"
            "  ⏱️ Timer:     'set a timer for 5 minutes'  |  'start stopwatch'  |  'time remaining'\n"
            "  📝 To-do:     'add to my list: [task]'  |  'read my list'  |  'done with [task]'\n"
            "  🧮 Math:      'calculate 15% of 200'  |  'what is 45 * 12'  |  '20% off 80'\n"
            "  🌤️ Weather:   'what is the weather in London'  |  'temperature in Tokyo'\n"
            "  📰 News:      'what's in the news'  |  'latest headlines'  |  'news about [topic]'\n"
            "  🎮 Games:     'play snake'  |  'play brick breaker'  |  'play chess'\n"
            "             'play connect 4'  |  'play tic tac toe'  |  'play hangman'  |  'play pong'\n"
            "  🌍 Translate: 'translate hello to Spanish'  |  'how do you say thanks in French'\n"
            "  📖 Story:     'tell me a story'  |  'start a story about pirates'\n"
            "  🧠 Quiz:      'quiz me on space'  |  'trivia about history'\n"
            "  💻 Code:      'explain this code: [code]'  |  'write a function that does X'\n"
            "  🔊 Volume:    'volume up'  |  'volume down'  |  'mute'  |  'set volume to 70'\n"
            "  📂 Open:      'open calculator'  |  'open notepad'  |  'open chrome'\n"
            "  📸 Screen:    'screenshot'  |  'take a screenshot'\n"
            "  🔀 Modes:     'casual mode' (chat only)  |  'workshop mode' (arm + chat)\n"
            "             '100% output' / 'aura mode' (hype mode: fast arm + music) 😤\n"
            "  🤖 AI Brain:  'use gemini'  |  'use ollama'  |  'use auto'  |  'set gemini key [KEY]'\n"
            f"  ℹ️ System:    'status'  |  'reset'  |  'commands'  |  'quit'  — mode: {'💬 Casual' if self.mode == 'casual' else '🔧 Workshop'}  brain: {self.llm_backend}"
        )

    def _cmd_joke(self, prefix=""):
        jokes = [
            "Why did the robot go to school? To improve its CPU!",
            "I tried to grab myself once. Got all wrapped up in it.",
            "How do robots eat? They bolt their food!",
            "Why was the robot tired? It had a hard drive.",
            "I would tell you a joke about my arm... but I need a good angle.",
            "My gripper walks into a bar. The bartender says 'We don't serve your type here.' My gripper says: 'That's a tight situation.'",
        ]
        return self.respond(f"{prefix}{random.choice(jokes)}")

    def _cmd_fun_fact(self, prefix=""):
        facts = [
            "The word 'robot' comes from Czech 'robota', meaning forced labor.",
            "The first industrial robot was installed at a GM factory in 1961.",
            "Robotic arms can repeat the same motion thousands of times with sub-millimeter precision.",
            "NASA's Canadarm2 on the ISS can handle objects weighing up to 116,000 kg — in zero gravity.",
            "Some robotic arms operate in environments up to 2000°C.",
            "The human arm has 7 degrees of freedom. Most industrial robots have 6.",
        ]
        return self.respond(f"{prefix}{random.choice(facts)}")

    def _cmd_timer(self, text, prefix=""):
        """Handle all timer and stopwatch commands."""
        import threading
        t = text.lower().strip()

        # --- STOPWATCH ---
        if any(p in t for p in ("start stopwatch", "stopwatch start", "begin stopwatch")):
            self._stopwatch_start = datetime.now()
            return self.respond(f"{prefix}⏱️ Stopwatch started!")

        if any(p in t for p in ("stop stopwatch", "stopwatch stop", "end stopwatch", "check stopwatch", "stopwatch time", "how long")):
            if self._stopwatch_start is None:
                return self.respond(f"{prefix}Stopwatch isn't running. Say 'start stopwatch' first.")
            elapsed = datetime.now() - self._stopwatch_start
            total = int(elapsed.total_seconds())
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            parts = []
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            parts.append(f"{s}s")
            if "stop" in t or "end" in t:
                self._stopwatch_start = None
                return self.respond(f"{prefix}⏱️ Stopwatch stopped — elapsed: {' '.join(parts)}")
            return self.respond(f"{prefix}⏱️ Elapsed: {' '.join(parts)}")

        # --- CANCEL TIMER ---
        if "cancel" in t or "stop timer" in t:
            if not self._timers:
                return self.respond(f"{prefix}No active timers to cancel.")
            cancelled = list(self._timers.keys())
            for tmr in self._timers.values():
                tmr.cancel()
            self._timers.clear()
            return self.respond(f"{prefix}⏱️ Cancelled timer(s): {', '.join(cancelled)}")

        # --- TIME REMAINING ---
        if "time remaining" in t or "how much time" in t or "timer status" in t:
            if not self._timers:
                return self.respond(f"{prefix}No active timers right now.")
            lines = [f"{name}" for name in self._timers]
            return self.respond(f"{prefix}⏱️ Active timers: {', '.join(lines)}")

        # --- SET TIMER: parse "set a timer for X minutes/seconds" ---
        import re
        total_seconds = 0
        matched = False
        m = re.search(r'(\d+)\s*hour[s]?\s*(\d+)\s*minute[s]?', t)
        if m:
            total_seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60
            matched = True
        if not matched:
            m = re.search(r'(\d+)\s*minute[s]?\s*(\d+)\s*second[s]?', t)
            if m:
                total_seconds = int(m.group(1)) * 60 + int(m.group(2))
                matched = True
        if not matched:
            m = re.search(r'(\d+)\s*(hour[s]?|hr)', t)
            if m:
                total_seconds = int(m.group(1)) * 3600
                matched = True
        if not matched:
            m = re.search(r'(\d+)\s*(minute[s]?|min)', t)
            if m:
                total_seconds = int(m.group(1)) * 60
                matched = True
        if not matched:
            m = re.search(r'(\d+)\s*(second[s]?|sec)', t)
            if m:
                total_seconds = int(m.group(1))
                matched = True

        if not matched or total_seconds <= 0:
            return self.respond(
                f"{prefix}⏱️ How long? Try: 'set a timer for 5 minutes' or 'set a timer for 90 seconds'"
            )

        # Human-readable label
        h, rem = divmod(total_seconds, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if h:    parts.append(f"{h} hour{'s' if h > 1 else ''}")
        if mins: parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
        if secs: parts.append(f"{secs} second{'s' if secs > 1 else ''}")
        label = " ".join(parts)
        timer_name = label

        def _ring():
            self._timers.pop(timer_name, None)
            msg = f"[Nicky] ⏰ Timer done! Your {label} timer is up!"
            print(f"\n{msg}")
            if self.voice and self.voice.voice_enabled:
                self.voice.speak(f"Timer done! Your {label} timer is up!")

        t_obj = threading.Timer(total_seconds, _ring)
        t_obj.daemon = True
        t_obj.start()
        self._timers[timer_name] = t_obj
        return self.respond(f"{prefix}⏱️ Timer set for {label}. I'll let you know when it's done!")

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
        """Manage a persistent to-do list."""
        import re
        t = text.lower().strip()

        # ADD: "add to my list: buy milk" / "add buy milk to my list"
        add_patterns = [
            r'add (?:to (?:my |the )?list[:\s]+|item[:\s]+)(.+)',
            r'add (.+?) to (?:my |the )?list',
            r'remember to (.+)',
            r'remind me to (.+)',
            r'put (.+?) on (?:my |the )?list',
        ]
        for pat in add_patterns:
            m = re.search(pat, t)
            if m:
                item = m.group(1).strip().rstrip(".")
                self._todos.append({"task": item, "done": False})
                self._save_todos()
                return self.respond(f"{prefix}📝 Added to your list: \"{item}\"")

        # DONE / COMPLETE: "done with buy milk" / "mark buy milk as done" / "complete buy milk"
        m = re.search(r'(?:done with|complete[d]?|finished|crossed off|mark)\s+(.+?)(?:\s+as done)?$', t)
        if m:
            keyword = m.group(1).strip()
            for item in self._todos:
                if not item["done"] and keyword in item["task"].lower():
                    item["done"] = True
                    self._save_todos()
                    return self.respond(f"{prefix}✅ Marked as done: \"{item['task']}\"")
            return self.respond(f"{prefix}Couldn't find \"{keyword}\" in your list.")

        # REMOVE: "remove buy milk from my list" / "delete X from list"
        m = re.search(r'(?:remove|delete|erase)\s+(.+?)(?:\s+from (?:my |the )?list)?$', t)
        if m:
            keyword = m.group(1).strip()
            before = len(self._todos)
            self._todos = [i for i in self._todos if keyword not in i["task"].lower()]
            if len(self._todos) < before:
                self._save_todos()
                return self.respond(f"{prefix}🗑️ Removed \"{keyword}\" from your list.")
            return self.respond(f"{prefix}Couldn't find \"{keyword}\" in your list.")

        # CLEAR: "clear my list" / "clear list"
        if any(p in t for p in ("clear list", "clear my list", "delete list", "empty list", "wipe list")):
            self._todos.clear()
            self._save_todos()
            return self.respond(f"{prefix}🗑️ List cleared!")

        # READ: "read my list" / "what's on my list" / "show my list"
        if any(p in t for p in ("read", "show", "what", "list", "my list", "to do", "todo")):
            pending = [i for i in self._todos if not i["done"]]
            done    = [i for i in self._todos if i["done"]]
            if not self._todos:
                return self.respond(f"{prefix}📝 Your list is empty! Add something with 'add to my list: [task]'")
            lines = []
            if pending:
                lines.append("📋 To do:")
                for i, item in enumerate(pending, 1):
                    lines.append(f"  {i}. {item['task']}")
            if done:
                lines.append("✅ Done:")
                for item in done:
                    lines.append(f"  ✓ {item['task']}")
            return self.respond(f"{prefix}" + "\n".join(lines))

        return self.respond(
            f"{prefix}📝 List commands: 'add to my list: [task]'  |  'read my list'  |  "
            "'done with [task]'  |  'remove [task] from list'  |  'clear list'"
        )

    def _cmd_weather(self, text, prefix=""):
        """Get current weather using wttr.in — no API key needed."""
        import urllib.request, urllib.parse, json as _json, re
        t = text.lower().strip()
        # Extract city name
        city = None
        for pat in (
            r'weather (?:in|for|at) (.+)',
            r'(?:what.s|what is) the weather (?:in|for|at) (.+)',
            r'temperature (?:in|for|at) (.+)',
            r'how (?:hot|cold|warm) is it (?:in|at) (.+)',
        ):
            m = re.search(pat, t)
            if m:
                city = m.group(1).strip().rstrip("?.")
                break
        if not city:
            return self.respond(
                f"{prefix}🌤️ Which city? Try: 'what is the weather in London'"
            )
        try:
            encoded = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "NickyAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read().decode())
            cur = data["current_condition"][0]
            temp_c = cur["temp_C"]
            temp_f = cur["temp_F"]
            feels_c = cur["FeelsLikeC"]
            humidity = cur["humidity"]
            desc = cur["weatherDesc"][0]["value"]
            wind_kmph = cur["windspeedKmph"]
            area = data["nearest_area"][0]
            area_name = area["areaName"][0]["value"]
            country = area["country"][0]["value"]
            return self.respond(
                f"{prefix}🌤️ Weather in {area_name}, {country}:\n"
                f"  {desc} — {temp_c}°C / {temp_f}°F  (feels like {feels_c}°C)\n"
                f"  💧 Humidity: {humidity}%   💨 Wind: {wind_kmph} km/h"
            )
        except Exception as e:
            return self.respond(
                f"{prefix}🌤️ Couldn't get weather for '{city}'. Check the city name and your internet connection."
            )

    def _cmd_news(self, text, prefix=""):
        """Fetch top headlines from BBC RSS — no API key needed."""
        import urllib.request, re
        t = text.lower().strip()
        # Detect topic filter
        topic = None
        for pat in (r'news about (.+)', r'latest news on (.+)', r'headlines about (.+)'):
            m = re.search(pat, t)
            if m:
                topic = m.group(1).strip().rstrip("?.")
                break
        try:
            url = "https://feeds.bbci.co.uk/news/rss.xml"
            req = urllib.request.Request(url, headers={"User-Agent": "NickyAI/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml = resp.read().decode("utf-8", errors="replace")
            # Parse titles from RSS without external XML library
            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', xml)
            if not titles:
                titles = re.findall(r'<title>([^<]{10,})</title>', xml)
            # Skip channel title (first entry)
            titles = [t for t in titles if t not in ("BBC News", "Home")]
            if topic:
                titles = [t for t in titles if topic.lower() in t.lower()]
            titles = titles[:7]
            if not titles:
                return self.respond(f"{prefix}📰 No headlines found for '{topic}'.")
            header = f"📰 Top headlines" + (f" about '{topic}'" if topic else "") + ":"
            lines = [header] + [f"  {i+1}. {t}" for i, t in enumerate(titles)]
            return self.respond(f"{prefix}" + "\n".join(lines))
        except Exception:
            return self.respond(
                f"{prefix}📰 Couldn't fetch news right now. Check your internet connection."
            )

    def _cmd_math(self, text, prefix=""):
        """Evaluate math expressions and percentages safely."""
        import re, math as _math
        t = text.lower().strip()

        # Strip trigger phrases
        for strip in ("calculate ", "what is ", "what's ", "compute ", "solve ",
                      "how much is ", "how many is ", "evaluate "):
            if t.startswith(strip):
                t = t[len(strip):].strip()
                break

        # Percentage helpers: "15% of 200" or "20 percent of 50"
        m = re.search(r'(\d+\.?\d*)\s*(?:%|percent)\s+of\s+(\d+\.?\d*)', t)
        if m:
            pct, total = float(m.group(1)), float(m.group(2))
            result = pct / 100 * total
            return self.respond(f"{prefix}🧮 {pct}% of {total} = **{result:g}**")

        # "X% off Y" (discount)
        m = re.search(r'(\d+\.?\d*)\s*(?:%|percent)\s+off\s+(\d+\.?\d*)', t)
        if m:
            pct, price = float(m.group(1)), float(m.group(2))
            discount = pct / 100 * price
            final = price - discount
            return self.respond(
                f"{prefix}🧮 {pct}% off {price} = save {discount:g}, pay **{final:g}**"
            )

        # Safe eval for arithmetic: only allow numbers and operators
        expr = t.rstrip("?.!")
        # Translate common words
        expr = (expr.replace("plus", "+").replace("minus", "-")
                    .replace("times", "*").replace("multiplied by", "*")
                    .replace("divided by", "/").replace("to the power of", "**")
                    .replace("squared", "**2").replace("cubed", "**3")
                    .replace("^", "**"))
        # Allow only safe characters
        safe = re.sub(r'[^0-9+\-*/(). %]', '', expr).strip()
        if not safe:
            return self.respond(
                f"{prefix}🧮 I can handle arithmetic and percentages. Try: 'calculate 15% of 200' or 'what is 45 * 12'"
            )
        try:
            result = eval(safe, {"__builtins__": {}}, {
                "sqrt": _math.sqrt, "pi": _math.pi, "abs": abs,
                "round": round, "pow": pow,
            })
            # Clean up result display
            if isinstance(result, float) and result == int(result):
                result = int(result)
            return self.respond(f"{prefix}🧮 {safe} = **{result}**")
        except ZeroDivisionError:
            return self.respond(f"{prefix}🧮 Can't divide by zero!")
        except Exception:
            return self.respond(
                f"{prefix}🧮 Couldn't solve that. Try: 'calculate 15% of 200' or 'what is 45 * 12'"
            )

    def _cmd_memory(self, prefix=""):
        if self.conversation_history:
            count = len(self.conversation_history)
            recent = [h.get("user", "") for h in self.conversation_history[-5:] if h.get("user")]
            return self.respond(f"{prefix}I remember {count} interactions. Recent: {', '.join(recent)}")
        return self.respond(f"{prefix}No conversation history yet.")

    def _cmd_throw(self, text, prefix=""):
        direction = self._extract_direction(text)

        # Find object to throw — either currently held or named in command
        target = self.arm_state.get("holding")
        if not target:
            for obj in self.environment.objects:
                if obj["name"].lower() in text:
                    target = obj["name"]
                    break

        if not target:
            return self.respond(
                f"{prefix}Nothing to throw! Grab something first, or say 'throw [object name]'."
            )

        # Grab it if not already holding
        if self.arm_state.get("holding") != target:
            self.environment.grab_object(target)
            self.arm_state["holding"] = target
            self.arm_state["gripper"] = "closed"

        # Execute throw — remove object from environment, reset arm
        self.environment.remove_object(target)
        self.arm_state["holding"] = None
        self.arm_state["gripper"] = "open"
        dir_str = f" to the {direction}" if direction else ""

        throw_lines = [
            f"Winding up... and {target} is airborne{dir_str}! 💥",
            f"Launching {target}{dir_str}! Hope there's nothing in the way.",
            f"{target} has left the building{dir_str}. Gripper open.",
            f"YEET! {target} sent flying{dir_str}. Workspace cleared.",
            f"Arm swings — {target} released{dir_str} at full speed!",
        ]
        # NOTE: On real hardware, this triggers a fast swing + gripper release sequence
        self._save_data()
        return self.respond(f"{prefix}{random.choice(throw_lines)}")
    
    def _extract_direction(self, text):
        """Helper method to extract direction from text"""
        directions = ["left", "right", "up", "down", "forward", "back"]
        for direction in directions:
            if direction in text:
                return direction
        return None
    
    def _extract_objects(self, text):
        """Extract object names from text - tries exact matches first"""
        objects = []
        # Get all object names from environment
        env_object_names = [obj["name"].lower() for obj in self.environment.objects]
        
        # Sort by length (longest first) to match "cube2" before "cube"
        env_object_names.sort(key=len, reverse=True)
        
        for obj_name in env_object_names:
            if obj_name in text.lower():
                objects.append(obj_name)
        
        return objects
    
    def respond(self, message):
        """Format and return a response"""
        formatted = f"[{self.name}] {message}"
        # Store in conversation history
        if self.conversation_history and "user" in self.conversation_history[-1]:
            self.conversation_history[-1]["response"] = message
        return formatted
    
    _MOOD_EMOJI = {
        "neutral": "😐", "happy": "😊", "curious": "🤔", "focused": "🎯",
    }

    def _prompt(self):
        """Build the You: input prompt with current mood emoji and active mode."""
        emoji = self._MOOD_EMOJI.get(self.personality.mood, "😐")
        mode_tag = "💬" if self.mode == "casual" else "🔧"
        return f"{mode_tag}{emoji} You: "

    def chat(self):
        """Main chat loop"""
        print(f"\n{'='*50}")
        print(f"Welcome to {self.name} - Robotic Arm Control System")
        print(f"{'='*50}")
        print("Type 'commands' for commands or 'quit' to exit")
        if self.user_memory.facts.get("name"):
            print(f"Welcome back, {self.user_memory.facts['name']}!")
        mode_label = "💬 Casual Mode" if self.mode == "casual" else "🔧 Workshop Mode"
        print(f"Active mode: {mode_label}  (say 'casual mode' or 'workshop mode' to switch)")
        print("Say 'voice on' to hear responses spoken\n")

        while True:
            try:
                prompt = self._prompt()
                # Use mic input when voice mode is on and mic is available
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
                    goodbye_msg = self.respond('Powering down. Farewell.')
                    print(goodbye_msg)
                    if self.voice.voice_enabled:
                        self.voice.speak("Powering down. Farewell.")
                    break

                self._last_streamed_text = ""
                response = self.process_command(user_input)
                if response:  # empty string = already printed by streaming
                    print(response)

                # Speak the response if voice mode is enabled
                if self.voice.voice_enabled:
                    text_to_speak = self._last_streamed_text if not response else response.replace(f"[{self.name}] ", "")
                    if text_to_speak:
                        self.voice.speak(text_to_speak)

            except KeyboardInterrupt:
                msg = self.respond('Interrupted. Standby mode activated.')
                print(f"\n{msg}")
                break

# Run the chatbot
if __name__ == "__main__":
    chatbot = Chatbot()
    chatbot.chat()
