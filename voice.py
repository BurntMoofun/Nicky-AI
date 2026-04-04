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
