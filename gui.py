"""Nicky AI — dark-themed tkinter GUI dashboard."""
import tkinter as tk
from tkinter import scrolledtext, font
import threading
import queue
import sys
import io
import time


# ── Colour palette ─────────────────────────────────────────────────────────
BG_DEEP    = "#0f0f1a"
BG_PANEL   = "#1a1a2e"
BG_BUBBLE_USER  = "#1e3a5f"
BG_BUBBLE_NICKY = "#1e2a1e"
BG_INPUT   = "#16213e"
BG_SIDEBAR = "#12121f"
BG_BTN     = "#0f3460"
BG_BTN_HOT = "#533483"
BG_BADGE_ROAST  = "#5a1a1a"
BG_BADGE_COMP   = "#1a3a1a"

FG_PRIMARY   = "#e0e0ff"
FG_SECONDARY = "#9090b0"
FG_USER      = "#a8d8ff"
FG_NICKY     = "#a8ffb0"
FG_TIME      = "#606080"
FG_BADGE     = "#ffdf80"
FG_GREEN     = "#50ff70"
FG_RED       = "#ff5050"
FG_YELLOW    = "#ffdf40"

FONT_MAIN   = ("Consolas", 11)
FONT_BUBBLE = ("Segoe UI", 11)
FONT_LABEL  = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_TITLE  = ("Segoe UI", 14, "bold")
FONT_MONO   = ("Consolas", 10)


class _PrintRedirector(io.TextIOBase):
    """Captures print() output and enqueues it for the GUI."""

    def __init__(self, queue_: queue.Queue, original):
        self._q = queue_
        self._original = original
        self._buf = ""

    def write(self, text):
        self._q.put(("print", text))
        return len(text)

    def flush(self):
        pass


class NickyGUI:
    """Dark-themed tkinter GUI for Nicky AI.

    Usage:
        gui = NickyGUI(chatbot)
        gui.run()
    """

    def __init__(self, chatbot):
        self._chatbot = chatbot
        self._root = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._input_enabled = True
        self._original_stdout = sys.stdout
        self._typing_dots = 0
        self._reminder_job = None
        self._wake_active = False

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def run(self):
        self._root = tk.Tk()
        self._root.title("Nicky AI")
        self._root.geometry("1100x700")
        self._root.minsize(800, 500)
        self._root.configure(bg=BG_DEEP)

        self._build_layout()
        self._redirect_print()
        self._schedule_poll()
        self._schedule_reminders()
        self._print_welcome()

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._root.mainloop()

    def _on_close(self):
        sys.stdout = self._original_stdout
        if self._reminder_job:
            self._root.after_cancel(self._reminder_job)
        self._root.destroy()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Top title bar
        title_bar = tk.Frame(self._root, bg=BG_PANEL, height=44)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        tk.Label(title_bar, text="🤖  Nicky AI", font=FONT_TITLE,
                 bg=BG_PANEL, fg=FG_PRIMARY).pack(side=tk.LEFT, padx=14, pady=8)
        self._lbl_mode = tk.Label(title_bar, text="● Casual", font=FONT_LABEL,
                                   bg=BG_PANEL, fg=FG_GREEN)
        self._lbl_mode.pack(side=tk.LEFT, padx=8)
        self._lbl_llm = tk.Label(title_bar, text="LLM: auto", font=FONT_SMALL,
                                  bg=BG_PANEL, fg=FG_SECONDARY)
        self._lbl_llm.pack(side=tk.RIGHT, padx=14)

        # Main area: chat (left) + sidebar (right)
        main_frame = tk.Frame(self._root, bg=BG_DEEP)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_chat_area(main_frame)
        self._build_sidebar(main_frame)
        self._build_input_bar()

    def _build_chat_area(self, parent):
        chat_outer = tk.Frame(parent, bg=BG_PANEL, bd=0)
        chat_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 4), pady=8)

        # Scrollable canvas for bubbles
        self._canvas = tk.Canvas(chat_outer, bg=BG_PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(chat_outer, orient="vertical", command=self._canvas.yview,
                                  bg=BG_PANEL, troughcolor=BG_DEEP)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._bubble_frame = tk.Frame(self._canvas, bg=BG_PANEL)
        self._bubble_window = self._canvas.create_window(
            (0, 0), window=self._bubble_frame, anchor="nw"
        )

        self._bubble_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Typing indicator
        self._typing_label = tk.Label(chat_outer, text="", font=FONT_SMALL,
                                       bg=BG_PANEL, fg=FG_SECONDARY)
        self._typing_label.pack(side=tk.BOTTOM, anchor="w", padx=8)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=BG_SIDEBAR, width=200)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=(4, 8), pady=8)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="STATUS", font=("Consolas", 9, "bold"),
                 bg=BG_SIDEBAR, fg=FG_SECONDARY).pack(anchor="w", padx=10, pady=(10, 2))

        # Mode badge
        self._badge_mode = tk.Label(sidebar, text="Casual Mode", font=FONT_LABEL,
                                     bg=BG_BTN, fg=FG_PRIMARY, relief="flat", padx=6, pady=3)
        self._badge_mode.pack(fill=tk.X, padx=8, pady=3)

        # Roast/Compliment badge
        self._badge_special = tk.Label(sidebar, text="", font=FONT_LABEL,
                                        bg=BG_SIDEBAR, fg=FG_BADGE)
        self._badge_special.pack(fill=tk.X, padx=8)

        tk.Frame(sidebar, bg=FG_SECONDARY, height=1).pack(fill=tk.X, padx=10, pady=6)

        tk.Label(sidebar, text="PERSONALITY", font=("Consolas", 9, "bold"),
                 bg=BG_SIDEBAR, fg=FG_SECONDARY).pack(anchor="w", padx=10, pady=(2, 2))
        self._traits_text = tk.Label(sidebar, text="(none)", font=FONT_SMALL,
                                      bg=BG_SIDEBAR, fg=FG_PRIMARY, justify=tk.LEFT,
                                      wraplength=175)
        self._traits_text.pack(anchor="w", padx=10, pady=2)

        tk.Frame(sidebar, bg=FG_SECONDARY, height=1).pack(fill=tk.X, padx=10, pady=6)

        # Voice toggle button
        self._voice_btn = tk.Button(
            sidebar, text="🎤  Voice: OFF", font=FONT_LABEL,
            bg=BG_BTN, fg=FG_PRIMARY, activebackground=BG_BTN_HOT,
            relief="flat", cursor="hand2", command=self._toggle_voice
        )
        self._voice_btn.pack(fill=tk.X, padx=8, pady=3)

        # Wake word toggle
        self._wake_btn = tk.Button(
            sidebar, text="💤  Wake Word: OFF", font=FONT_LABEL,
            bg=BG_BTN, fg=FG_PRIMARY, activebackground=BG_BTN_HOT,
            relief="flat", cursor="hand2", command=self._toggle_wake_word
        )
        self._wake_btn.pack(fill=tk.X, padx=8, pady=3)

        tk.Frame(sidebar, bg=FG_SECONDARY, height=1).pack(fill=tk.X, padx=10, pady=6)

        # Quick action buttons
        for label, cmd in [
            ("📋  Help", "help"),
            ("👤  Profile", "show profile"),
            ("📚  Knowledge", "show knowledge"),
            ("📅  Today", "what is on my calendar today"),
            ("🎵  YT Music", "open youtube music"),
        ]:
            tk.Button(
                sidebar, text=label, font=FONT_LABEL,
                bg=BG_BTN, fg=FG_PRIMARY, activebackground=BG_BTN_HOT,
                relief="flat", cursor="hand2",
                command=lambda c=cmd: self._quick_cmd(c)
            ).pack(fill=tk.X, padx=8, pady=2)

        tk.Frame(sidebar, bg=FG_SECONDARY, height=1).pack(fill=tk.X, padx=10, pady=6)

        # Stats
        self._lbl_kb = tk.Label(sidebar, text="KB: 0 facts", font=FONT_SMALL,
                                 bg=BG_SIDEBAR, fg=FG_SECONDARY)
        self._lbl_kb.pack(anchor="w", padx=10)
        self._lbl_history = tk.Label(sidebar, text="History: 0 msgs", font=FONT_SMALL,
                                      bg=BG_SIDEBAR, fg=FG_SECONDARY)
        self._lbl_history.pack(anchor="w", padx=10)

    def _build_input_bar(self):
        input_bar = tk.Frame(self._root, bg=BG_INPUT, height=54)
        input_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=(0, 8))

        self._mic_btn = tk.Button(
            input_bar, text="🎤", font=("Segoe UI Emoji", 14),
            bg=BG_INPUT, fg=FG_PRIMARY, activebackground=BG_BTN_HOT,
            relief="flat", cursor="hand2", command=self._voice_input
        )
        self._mic_btn.pack(side=tk.LEFT, padx=(8, 4), pady=8)

        self._entry = tk.Entry(
            input_bar, font=FONT_BUBBLE, bg="#0d1b2e", fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY, relief="flat", bd=0
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8, ipady=6)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Up>", self._history_up)
        self._entry.focus_set()

        self._send_btn = tk.Button(
            input_bar, text="Send ▶", font=FONT_LABEL,
            bg=BG_BTN, fg=FG_PRIMARY, activebackground=BG_BTN_HOT,
            relief="flat", cursor="hand2", command=self._on_send
        )
        self._send_btn.pack(side=tk.RIGHT, padx=8, pady=8, ipadx=8)

        self._input_history: list[str] = []
        self._input_hist_idx = -1

    # ── Chat bubble rendering ─────────────────────────────────────────────────

    def _add_bubble(self, text: str, speaker: str):
        """Render a chat bubble. speaker = 'user' | 'nicky' | 'system'."""
        is_user = speaker == "user"
        is_system = speaker == "system"

        outer = tk.Frame(self._bubble_frame, bg=BG_PANEL)
        outer.pack(fill=tk.X, padx=8, pady=3, anchor="e" if is_user else "w")

        if is_system:
            lbl = tk.Label(outer, text=text, font=FONT_SMALL, bg=BG_PANEL,
                           fg=FG_SECONDARY, justify=tk.LEFT, wraplength=640)
            lbl.pack(anchor="center", padx=20, pady=2)
            return

        bubble_bg  = BG_BUBBLE_USER if is_user else BG_BUBBLE_NICKY
        text_color = FG_USER if is_user else FG_NICKY
        anchor_dir = "e" if is_user else "w"
        align      = tk.RIGHT if is_user else tk.LEFT
        prefix     = "You" if is_user else "Nicky"

        frame = tk.Frame(outer, bg=bubble_bg, bd=0, padx=10, pady=6)
        frame.pack(anchor=anchor_dir, padx=(120 if is_user else 0, 0 if is_user else 120))

        tk.Label(frame, text=prefix, font=("Segoe UI", 9, "bold"),
                 bg=bubble_bg, fg=FG_BADGE).pack(anchor=anchor_dir)

        # Wrap long text
        msg_lbl = tk.Label(
            frame, text=text, font=FONT_BUBBLE,
            bg=bubble_bg, fg=text_color,
            justify=align, wraplength=540
        )
        msg_lbl.pack(anchor=anchor_dir)

        ts = time.strftime("%H:%M")
        tk.Label(frame, text=ts, font=FONT_SMALL, bg=bubble_bg, fg=FG_TIME).pack(anchor=anchor_dir)

        self._scroll_bottom()

    def _scroll_bottom(self):
        self._root.after(50, lambda: self._canvas.yview_moveto(1.0))

    # ── Canvas resize handling ────────────────────────────────────────────────

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._bubble_window, width=event.width)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Input handling ────────────────────────────────────────────────────────

    def _on_enter(self, event=None):
        if self._input_enabled:
            self._on_send()

    def _on_send(self):
        text = self._entry.get().strip()
        if not text or not self._input_enabled:
            return
        self._entry.delete(0, tk.END)
        self._input_history.append(text)
        self._input_hist_idx = -1
        self._submit(text)

    def _submit(self, text: str):
        self._add_bubble(text, "user")
        self._set_input_enabled(False)
        self._show_typing(True)
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _process(self, text: str):
        try:
            self._chatbot.process_command(text)
        except Exception as e:
            self._msg_queue.put(("bubble_nicky", f"[Error] {e}"))
        finally:
            self._msg_queue.put(("done", None))

    def _history_up(self, event=None):
        if not self._input_history:
            return
        self._input_hist_idx = min(self._input_hist_idx + 1, len(self._input_history) - 1)
        val = self._input_history[-(self._input_hist_idx + 1)]
        self._entry.delete(0, tk.END)
        self._entry.insert(0, val)

    def _quick_cmd(self, cmd: str):
        self._entry.delete(0, tk.END)
        self._entry.insert(0, cmd)
        self._on_send()

    # ── Voice controls ────────────────────────────────────────────────────────

    def _toggle_voice(self):
        if self._chatbot.voice.voice_enabled:
            self._chatbot.voice.disable_voice()
            self._voice_btn.config(text="🎤  Voice: OFF", bg=BG_BTN)
        else:
            self._chatbot.voice.enable_voice()
            self._voice_btn.config(text="🎤  Voice: ON", bg="#1a3a1a")

    def _toggle_wake_word(self):
        if self._wake_active:
            self._chatbot.voice.stop_wake_word_detection()
            self._wake_active = False
            self._wake_btn.config(text="💤  Wake Word: OFF", bg=BG_BTN)
        else:
            ok = self._chatbot.voice.start_wake_word_detection(self._on_wake_word)
            if ok:
                self._wake_active = True
                self._wake_btn.config(text="👂  Wake Word: ON", bg="#1a3a1a")
            else:
                self._add_bubble("Wake word detection unavailable — check your microphone.", "system")

    def _on_wake_word(self):
        """Called from background thread when wake word heard."""
        self._msg_queue.put(("wake", None))

    def _voice_input(self):
        """Mic button — record one utterance."""
        if not self._input_enabled:
            return
        self._set_input_enabled(False)
        self._add_bubble("🎤 Listening...", "system")

        def _do():
            try:
                text = self._chatbot.voice.listen()
                if text:
                    self._msg_queue.put(("voice_input", text))
                else:
                    self._msg_queue.put(("voice_input_fail", None))
            except Exception:
                self._msg_queue.put(("voice_input_fail", None))

        threading.Thread(target=_do, daemon=True).start()

    # ── Typing indicator ──────────────────────────────────────────────────────

    def _show_typing(self, visible: bool):
        if visible:
            self._typing_label.config(text="Nicky is typing •••")
        else:
            self._typing_label.config(text="")

    # ── Status sidebar updater ────────────────────────────────────────────────

    def _update_sidebar(self):
        c = self._chatbot
        # Mode badge
        mode_text = c.mode.capitalize()
        if getattr(c, "_roast_mode", False):
            mode_text += " 🔥"
            self._badge_mode.config(bg=BG_BADGE_ROAST)
            self._badge_special.config(text="🔥 Roast Mode ON", fg="#ff8080")
        elif getattr(c, "_compliment_mode", False):
            mode_text += " 💛"
            self._badge_mode.config(bg=BG_BADGE_COMP)
            self._badge_special.config(text="💛 Compliment Mode ON", fg="#80ff80")
        else:
            self._badge_mode.config(bg=BG_BTN)
            self._badge_special.config(text="")
        self._badge_mode.config(text=mode_text)
        self._lbl_mode.config(text=f"● {mode_text}")

        # Personality traits
        traits = getattr(c.custom_personality, "traits", [])
        if traits:
            self._traits_text.config(text=", ".join(traits[:5]))
        else:
            self._traits_text.config(text="(none)")

        # LLM backend
        self._lbl_llm.config(text=f"LLM: {c.llm_backend}")

        # KB size
        kb_count = len(getattr(c.knowledge, "facts", {}))
        self._lbl_kb.config(text=f"KB: {kb_count} facts")

        # History
        hist_count = len(c.conversation_history)
        self._lbl_history.config(text=f"History: {hist_count} msgs")

        # Voice button
        if c.voice.voice_enabled:
            self._voice_btn.config(text="🎤  Voice: ON", bg="#1a3a1a")
        else:
            self._voice_btn.config(text="🎤  Voice: OFF", bg=BG_BTN)

    # ── Print redirection ─────────────────────────────────────────────────────

    def _redirect_print(self):
        sys.stdout = _PrintRedirector(self._msg_queue, self._original_stdout)

    # ── Polling loop (runs on main thread via after()) ────────────────────────

    def _schedule_poll(self):
        self._poll()

    def _poll(self):
        accumulated = []
        try:
            for _ in range(50):  # drain up to 50 items per tick
                item = self._msg_queue.get_nowait()
                accumulated.append(item)
        except queue.Empty:
            pass

        for kind, val in accumulated:
            if kind == "print":
                self._handle_print(val)
            elif kind == "bubble_nicky":
                self._show_typing(False)
                self._add_bubble(val, "nicky")
            elif kind == "done":
                self._show_typing(False)
                self._set_input_enabled(True)
                self._update_sidebar()
            elif kind == "wake":
                self._add_bubble("👂 Wake word detected!", "system")
                self._voice_input()
            elif kind == "voice_input":
                self._set_input_enabled(True)
                self._submit(val)
            elif kind == "voice_input_fail":
                self._add_bubble("🎤 Couldn't hear anything. Try again.", "system")
                self._set_input_enabled(True)

        self._root.after(80, self._poll)

    def _handle_print(self, text: str):
        """Convert print() output into Nicky chat bubbles."""
        text = text.strip()
        if not text:
            return
        # Strip ANSI codes if any
        import re
        text = re.sub(r'\x1b\[[0-9;]*m', '', text)
        # Prefix lines that look like Nicky responses
        if text.startswith("[Nicky]") or text.startswith("Nicky:"):
            clean = text.replace("[Nicky] ", "").replace("Nicky: ", "")
            self._add_bubble(clean, "nicky")
        elif text.startswith("[Error]") or text.startswith("[Nicky AI]"):
            self._add_bubble(text, "system")
        elif text.startswith("You:") or text.startswith("[You]"):
            pass  # user bubbles already added via _submit
        else:
            # Generic output → nicky bubble
            self._add_bubble(text, "nicky")

    # ── Reminder checker ──────────────────────────────────────────────────────

    def _schedule_reminders(self):
        self._check_reminders()

    def _check_reminders(self):
        cal = getattr(self._chatbot, "_calendar", None)
        if cal:
            due = cal.get_reminders_due(window_minutes=15)
            for ev in due:
                msg = f"⏰ Reminder: '{ev['title']}' at {ev['time']}"
                self._add_bubble(msg, "system")
                if self._chatbot.voice.voice_enabled:
                    threading.Thread(
                        target=self._chatbot.voice.speak,
                        args=(f"Reminder: {ev['title']} at {ev['time']}",),
                        daemon=True
                    ).start()
                cal.mark_reminded(ev["id"])
        self._reminder_job = self._root.after(60_000, self._check_reminders)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_input_enabled(self, enabled: bool):
        self._input_enabled = enabled
        state = tk.NORMAL if enabled else tk.DISABLED
        self._entry.config(state=state)
        self._send_btn.config(state=state)
        if enabled:
            self._entry.focus_set()

    def _print_welcome(self):
        self._add_bubble("Hey! I'm Nicky. Type a message or click the mic to talk.", "nicky")
        self._add_bubble("Tip: Use the sidebar buttons for quick actions, or type 'help' for all commands.", "system")
        self._update_sidebar()
