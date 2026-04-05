"""
Nicky AI — Web UI (cloud-ready)
Run locally:  python web_ui.py
Cloud:        gunicorn web_ui:app  (set PORT env var if needed)

Environment variables:
  PORT            — port to listen on (default 5000)
  OLLAMA_HOST     — Ollama URL (default http://localhost:11434)
  SECRET_KEY      — Flask session secret (set a long random string in production)
"""

import os
import json
import threading
import queue
import uuid

from flask import Flask, request, jsonify, render_template, Response, session
from werkzeug.middleware.proxy_fix import ProxyFix
from chatbot import Chatbot

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.environ.get("SECRET_KEY", "nicky-dev-secret-change-in-production")

# ── Session management — one Chatbot per browser session ──────────────────────
_sessions: dict[str, Chatbot] = {}
_sessions_lock = threading.Lock()

def _get_chatbot() -> Chatbot:
    """Return (or create) the Chatbot for the current browser session."""
    sid = session.get("nicky_sid")
    if not sid:
        sid = str(uuid.uuid4())
        session["nicky_sid"] = sid
    with _sessions_lock:
        if sid not in _sessions:
            _sessions[sid] = Chatbot()
        return _sessions[sid]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    _get_chatbot()   # ensure session created on first visit
    return render_template("index.html")


@app.route("/health")
def health():
    """Health check endpoint for cloud platforms (Railway, Render, etc.)."""
    return jsonify({"status": "ok", "name": "Nicky AI"})


@app.route("/api/chat", methods=["POST"])
def chat():
    """Standard (non-streaming) chat endpoint."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "No message provided."}), 400

    bot = _get_chatbot()
    try:
        bot._last_streamed_text = ""
        response = bot.process_command(message)
        text = response or bot._last_streamed_text or ""
        # Strip terminal prefix like "[Nicky] "
        text = text.replace(f"[{bot.name}] ", "").strip()
        return jsonify({"response": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Server-Sent Events streaming endpoint — tokens arrive in real time."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "No message provided."}), 400

    bot = _get_chatbot()
    token_queue: queue.Queue = queue.Queue()

    # Inject streaming callback into both LLM clients
    def _on_token(token: str):
        token_queue.put(token)

    bot.ollama._stream_callback = _on_token
    bot.gemini._stream_callback = _on_token

    def _run():
        try:
            bot._last_streamed_text = ""
            response = bot.process_command(message)
            # For non-LLM responses (commands that return directly)
            if response:
                text = response.replace(f"[{bot.name}] ", "").strip()
                token_queue.put(text)
        except Exception as e:
            token_queue.put(f"⚠️ Error: {e}")
        finally:
            bot.ollama._stream_callback = None
            bot.gemini._stream_callback = None
            token_queue.put(None)  # sentinel — done

    threading.Thread(target=_run, daemon=True).start()

    def _generate():
        while True:
            token = token_queue.get()
            if token is None:
                yield "data: [DONE]\n\n"
                break
            payload = json.dumps({"token": token})
            yield f"data: {payload}\n\n"

    return Response(_generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/session/clear", methods=["POST"])
def clear_session():
    """Let the user start a fresh conversation."""
    sid = session.get("nicky_sid")
    if sid:
        with _sessions_lock:
            _sessions.pop(sid, None)
        session.pop("nicky_sid", None)
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Nicky AI — Web UI (cloud-ready)")
    print(f"  Open: http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=port)
