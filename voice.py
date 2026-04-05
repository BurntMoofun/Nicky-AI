import os
try:
    import pyttsx3
    import speech_recognition as sr  # noqa: F401
except ImportError as _e:
    print(f"Warning: Some libraries not installed. Run: pip install -r requirements.txt ({_e})")
    pyttsx3 = None
    sr = None


# Voice System - Text-to-Speech and Speech-to-Text
class VoiceSystem:
    def __init__(self):
        self.voice_enabled = False
        self.tts_engine = None
        self.recognizer = None
        self._mic_available = False
        self._speaking = False  # True while TTS is playing — blocks mic
        self._avatar = None    # AvatarWindow instance (optional)
        self.load_voice_pref()  # restore saved voice choice

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

    # Default neural voice — can be changed at runtime with "set voice"
    TTS_VOICE = "en-US-AriaNeural"

    # Curated shortlist shown by "list voices"
    VOICE_MENU = [
        ("Aria",    "en-US-AriaNeural",      "US Female — warm, conversational (default)"),
        ("Jenny",   "en-US-JennyNeural",     "US Female — friendly, clear"),
        ("Guy",     "en-US-GuyNeural",       "US Male — neutral, professional"),
        ("Sonia",   "en-GB-SoniaNeural",     "UK Female — crisp, articulate"),
        ("Ryan",    "en-GB-RyanNeural",      "UK Male — relaxed, natural"),
        ("Davis",   "en-US-DavisNeural",     "US Male — casual, young"),
        ("Emma",    "en-US-EmmaNeural",      "US Female — expressive"),
        ("Brian",   "en-US-BrianNeural",     "US Male — calm, deep"),
    ]

    def set_voice(self, name_or_num: str) -> str:
        """Change TTS voice by name or menu number. Returns confirmation string."""
        s = name_or_num.strip()
        # Match by number
        if s.isdigit():
            idx = int(s) - 1
            if 0 <= idx < len(self.VOICE_MENU):
                label, voice_id, _ = self.VOICE_MENU[idx]
                self.TTS_VOICE = voice_id
                self._save_voice_pref(voice_id)
                return f"Voice set to {label} ({voice_id})"
            return f"Number out of range — pick 1–{len(self.VOICE_MENU)}"
        # Match by label or voice ID (case-insensitive)
        for label, voice_id, _ in self.VOICE_MENU:
            if s.lower() in (label.lower(), voice_id.lower()):
                self.TTS_VOICE = voice_id
                self._save_voice_pref(voice_id)
                return f"Voice set to {label} ({voice_id})"
        # Accept any raw edge-tts voice ID directly
        if "Neural" in name_or_num:
            self.TTS_VOICE = name_or_num
            self._save_voice_pref(name_or_num)
            return f"Voice set to {name_or_num}"
        return f"Unknown voice '{name_or_num}'. Type 'list voices' to see options."

    def list_voices(self) -> str:
        lines = ["Available voices (say 'set voice [number or name]'):"]
        for i, (label, voice_id, desc) in enumerate(self.VOICE_MENU, 1):
            marker = " ◀ current" if voice_id == self.TTS_VOICE else ""
            lines.append(f"  {i}. {label:8} — {desc}{marker}")
        return "\n".join(lines)

    def _save_voice_pref(self, voice_id: str):
        """Persist the chosen voice to nicky_data/config.json."""
        import json as _json
        path = os.path.join("nicky_data", "voice_config.json")
        try:
            os.makedirs("nicky_data", exist_ok=True)
            with open(path, "w") as f:
                _json.dump({"tts_voice": voice_id}, f)
        except Exception:
            pass

    def load_voice_pref(self):
        """Load saved voice preference on startup."""
        import json as _json
        path = os.path.join("nicky_data", "voice_config.json")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    data = _json.load(f)
                self.TTS_VOICE = data.get("tts_voice", self.TTS_VOICE)
        except Exception:
            pass

    def speak(self, text):
        """Convert text to speech — tries Edge TTS (neural) first, falls back to Windows SAPI."""
        if not text:
            return False

        self._speaking = True
        if self._avatar:
            self._avatar.notify_speaking(True, text)
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
            if self._avatar:
                self._avatar.notify_speaking(False)

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

    def set_avatar(self, avatar):
        """Attach an AvatarWindow instance to animate during speech."""
        self._avatar = avatar

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

    def start_wake_word_detection(self, callback) -> bool:
        """Start background wake-word listener. Returns True if started."""
        try:
            from wakeword import WakeWordDetector
            if not hasattr(self, "_wake_detector") or self._wake_detector is None:
                self._wake_detector = WakeWordDetector()
            return self._wake_detector.start(callback)
        except Exception:
            return False

    def stop_wake_word_detection(self):
        """Stop the wake-word listener if running."""
        detector = getattr(self, "_wake_detector", None)
        if detector:
            detector.stop()
