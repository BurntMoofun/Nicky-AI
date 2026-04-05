import os
import json


class OllamaClient:
    """Local LLM via Ollama — streaming, memory-aware answers for Nicky."""

    DEFAULT_MODEL = "llama3.2"
    MAX_HISTORY = 20  # max messages kept in context (10 exchanges)

    @property
    def API_BASE(self):
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def __init__(self):
        self.available = False
        self.model = self.DEFAULT_MODEL
        self.vision_model = None   # set to e.g. "llava" if a vision model is found
        self._stream_callback = None  # optional fn(token) called on each streamed token
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
                            break
                    if self.available:
                        break
                if not self.available:
                    self.model = models[0]
                    self.available = True
                    print(f"[Nicky AI] Ollama connected — using model: {self.model}")
                # Detect best available vision model
                _VISION_MODELS = ("moondream", "llava", "bakllava", "llama3.2-vision", "llava-llama3")
                for vm in _VISION_MODELS:
                    for m in models:
                        if m.startswith(vm):
                            self.vision_model = m
                            break
                    if self.vision_model:
                        break
                if self.vision_model:
                    print(f"[Nicky AI] Vision model available: {self.vision_model}")
                else:
                    print("[Nicky AI] No vision model found. For screen monitor, run: ollama pull llava")
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
                        if self._stream_callback:
                            self._stream_callback(token)
                    if chunk.get("done"):
                        break
            print()  # newline after stream ends
            return full_text.strip() or None
        except Exception:
            return None

    def ask_with_image(self, prompt: str, image_b64: str,
                       print_prefix: str = "[Nicky] ") -> str | None:
        """Send a prompt + screenshot to an Ollama vision model (e.g. llava)."""
        if not self.available:
            return None
        if not self.vision_model:
            return None   # no vision model — let caller fall back or show error
        import urllib.request
        import json
        try:
            messages = [{"role": "user", "content": prompt, "images": [image_b64]}]
            payload  = {"model": self.vision_model, "messages": messages, "stream": True}
            data = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(
                f"{self.API_BASE}/api/chat", data=data,
                headers={"Content-Type": "application/json"}, method="POST")
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
            print()
            return full_text.strip() or None
        except Exception as e:
            print(f"\n[Ollama Vision] Error: {e}")
            return None

class GeminiClient:
    """Google Gemini via REST API — no SDK required. Free-tier gemini-1.5-flash."""

    MODEL = "gemini-1.5-flash"
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    CONFIG_PATH = os.path.join("nicky_data", "config.json")

    def __init__(self):
        self.api_key = None
        self.available = False
        self._stream_callback = None  # optional fn(token) for web streaming
        self._load_key()

    def _load_key(self):
        try:
            # Check environment variable first (for cloud hosting)
            import os as _os
            env_key = _os.environ.get("GEMINI_API_KEY", "")
            if env_key:
                self.api_key = env_key
                self.available = True
                print(f"[Nicky AI] Gemini connected via env var — model: {self.MODEL}")
                return
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
                            if self._stream_callback:
                                self._stream_callback(token)
                    except Exception:
                        continue
            print()
            return full_text.strip() or None
        except Exception as e:
            print(f"\n[Gemini] Error: {e}")
            return None

    def ask_with_image(self, prompt: str, image_b64: str,
                       system_prompt: str = "",
                       print_prefix: str = "[Nicky] ") -> str | None:
        """Send a prompt + screenshot to Gemini vision. Returns streamed text."""
        if not self.available:
            return None
        import urllib.request
        try:
            contents = [{"role": "user", "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
            ]}]
            payload = {"contents": contents}
            if system_prompt:
                payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
            data = json.dumps(payload).encode("utf-8")
            url  = (f"{self.API_BASE}/{self.MODEL}:streamGenerateContent"
                    f"?alt=sse&key={self.api_key}")
            req  = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"}, method="POST")
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
                        token = (chunk.get("candidates", [{}])[0]
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
            print(f"\n[Gemini Vision] Error: {e}")
            return None
