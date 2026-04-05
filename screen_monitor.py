"""Nicky AI — Screen Monitor.

Captures the user's screen and sends it to a vision-capable LLM so Nicky
can see and describe what's on screen.

Requires Pillow:  pip install Pillow
Vision backends:
  - Gemini (best) — works out of the box with a Gemini API key
  - Ollama — requires a vision model: ollama pull llava
"""
import base64
import io

try:
    from PIL import ImageGrab
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# Max width to resize screenshots before sending (saves tokens / bandwidth)
_MAX_WIDTH  = 1280
_JPEG_QUAL  = 65


class ScreenMonitor:
    """Grabs screenshots and queries a vision LLM about them."""

    def __init__(self, gemini=None, ollama=None):
        self._gemini  = gemini
        self._ollama  = ollama
        self.active   = False   # continuous monitor mode flag

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return _PIL_OK

    def capture_base64(self, region=None) -> str | None:
        """Screenshot → JPEG → base64 string, or None on failure."""
        if not _PIL_OK:
            return None
        try:
            img = ImageGrab.grab(bbox=region, all_screens=True)
            w, h = img.size
            if w > _MAX_WIDTH:
                img = img.resize((_MAX_WIDTH, int(h * _MAX_WIDTH / w)))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=_JPEG_QUAL)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"[ScreenMonitor] Capture failed: {e}")
            return None

    def look(self, question: str = "", system_prompt: str = "",
             print_prefix: str = "[Nicky] ") -> str:
        """Capture screen and ask the LLM about it. Returns the response."""
        if not _PIL_OK:
            return ("Screen capture unavailable — install Pillow:\n"
                    "  pip install Pillow")

        img_b64 = self.capture_base64()
        if not img_b64:
            return "Failed to capture screen."

        prompt = question if question.strip() else (
            "Describe what you can see on this screen in 2-3 sentences. "
            "Be specific — mention app names, open windows, and any notable content."
        )

        # Prefer Gemini (native multimodal), fall back to Ollama vision
        if self._gemini and self._gemini.available:
            result = self._gemini.ask_with_image(
                prompt, img_b64, system_prompt, print_prefix)
            if result:
                return result

        if self._ollama and self._ollama.available:
            if not self._ollama.vision_model:
                return ("No vision model found in Ollama.\n"
                        "Run:  ollama pull moondream   (fast, ~1.7 GB)\n"
                        "  or: ollama pull llava        (larger, ~4 GB)\n"
                        "Then restart Nicky so it detects it.")
            result = self._ollama.ask_with_image(
                prompt, img_b64, print_prefix)
            if result:
                return result

        return ("No vision-capable LLM available.\n"
                "Run:  ollama pull moondream   (fast, ~1.7 GB)\n"
                "  or: ollama pull llava        (larger, ~4 GB)\n"
                "Then restart Nicky.")
