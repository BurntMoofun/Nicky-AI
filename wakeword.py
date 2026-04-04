"""Wake word detection for Nicky AI — listens for 'Hey Nicky' or 'Nicky'."""
import threading
import time


class WakeWordDetector:
    """Background mic listener that fires a callback when wake word is heard.

    Uses energy-based voice activity detection to grab short audio snippets,
    then runs them through speech_recognition for keyword matching.
    No API keys required — uses Google STT free tier.
    """

    WAKE_WORDS = {"nicky", "hey nicky", "ok nicky", "oi nicky"}
    ENERGY_THRESHOLD = 300      # mic energy level to consider as speech
    SNIPPET_DURATION = 2.5      # seconds to record per snippet
    COOLDOWN = 1.5              # seconds to wait after a detection before re-arming

    def __init__(self):
        self._callback = None
        self._thread = None
        self._stop_event = threading.Event()
        self._active = False
        self._recognizer = None
        self._mic_available = False
        self._init_recognizer()

    def _init_recognizer(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self.ENERGY_THRESHOLD
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.6
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.3)
            self._mic_available = True
        except Exception:
            self._mic_available = False

    def start(self, callback):
        """Start listening in background. callback() is called on wake word."""
        if not self._mic_available:
            return False
        if self._active:
            return True
        self._callback = callback
        self._stop_event.clear()
        self._active = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordThread")
        self._thread.start()
        return True

    def stop(self):
        """Stop the background listener."""
        self._active = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def _listen_loop(self):
        import speech_recognition as sr

        while not self._stop_event.is_set():
            try:
                with sr.Microphone() as source:
                    try:
                        audio = self._recognizer.listen(
                            source,
                            timeout=3,
                            phrase_time_limit=self.SNIPPET_DURATION
                        )
                    except sr.WaitTimeoutError:
                        continue

                try:
                    text = self._recognizer.recognize_google(audio).lower().strip()
                except Exception:
                    continue

                if any(w in text for w in self.WAKE_WORDS):
                    if self._callback:
                        self._callback()
                    # Cooldown so we don't double-trigger
                    time.sleep(self.COOLDOWN)

            except Exception:
                time.sleep(0.5)

    @property
    def is_active(self):
        return self._active

    @property
    def available(self):
        return self._mic_available
