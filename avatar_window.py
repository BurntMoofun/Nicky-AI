"""Nicky AI — floating response window.

Shows Nicky's full replies in a scrollable area with a vibrating logo.
Has a built-in input box — type and press Enter to chat directly.
Open with 'window'; close with 'close window'.
"""
import tkinter as tk
import threading
import math

_BG        = "#0f0f1a"
_GLOW_IDLE = "#1e90ff"
_GLOW_TALK = "#7b2fff"
_CIRCLE_BG = "#0f1e40"
_TEXT_FG   = "#00bfff"
_LABEL_FG  = "#9090b0"
_RESP_FG   = "#d0d0f0"
_INPUT_FG  = "#e0e0ff"
_INPUT_BG  = "#12122a"
_SEP_COLOR = "#1e2040"
_SCROLL_BG = "#0d0d1a"

_WIN_W, _WIN_H = 300, 420
_LOGO_H  = 140
_CX, _CY = 150, 68
_RADIUS  = 46

_ALPHA      = 0.88
_FRAME_MS   = 40
_MAX_SHAKE  = 3
_MS_PER_SYL = 110
_MS_WORD_GAP = 70


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:\"'()-")
    if not word:
        return 1
    vowels = "aeiouy"
    count, prev_was_vowel = 0, False
    for ch in word:
        is_v = ch in vowels
        if is_v and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _build_amplitude_schedule(text: str) -> list:
    if not text:
        return []
    schedule = []
    for word in text.split():
        syls = _count_syllables(word)
        intensity = min(1.0, 0.2 + syls * 0.2)
        n_frames = max(1, round(syls * _MS_PER_SYL / _FRAME_MS))
        for i in range(n_frames):
            progress = i / max(1, n_frames - 1)
            beat = abs(math.sin(math.pi * progress * syls))
            schedule.append(intensity * (0.4 + 0.6 * beat))
        gap_frames = max(1, round(_MS_WORD_GAP / _FRAME_MS))
        schedule.extend([0.05] * gap_frames)
    return schedule


class AvatarWindow:
    """Floating chat window with vibrating logo.

    CLI / standalone:   av = AvatarWindow(); av.start()
    GUI (existing Tk):  av = AvatarWindow(root=gui_root); av.start()

    Wire up input:      av.set_input_callback(fn)
        fn(text) is called on a background thread with whatever the user typed.
        It should return the response string (or None).
    """

    def __init__(self, root=None):
        self._external_root = root
        self._speaking      = False
        self._running       = False
        self._canvas        = None
        self._resp_text     = None   # tk.Text widget
        self._entry         = None   # tk.Entry widget
        self._win           = None
        self._drag_x        = 0
        self._drag_y        = 0
        self._input_cb      = None   # callback(str) -> str | None

        self._schedule:  list = []
        self._sched_idx  = 0
        self._phase      = 0
        self._offset_x   = 0
        self._offset_y   = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        if self._external_root:
            self._build_window(as_toplevel=True)
        else:
            threading.Thread(target=self._run_standalone, daemon=True).start()

    def set_input_callback(self, fn):
        """Register fn(text: str) -> str | None to handle window input."""
        self._input_cb = fn

    def notify_speaking(self, is_speaking: bool, text: str = ""):
        if is_speaking and text:
            self._schedule  = _build_amplitude_schedule(text)
            self._sched_idx = 0
        self._speaking = is_speaking

    def show_response(self, text: str):
        """Append Nicky's response to the scrollable area. Thread-safe."""
        if self._win and self._resp_text:
            try:
                self._win.after(0, lambda t=text: self._append_text("Nicky", t))
            except Exception:
                pass

    def close(self):
        self._running = False
        try:
            if self._win:
                self._win.destroy()
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_standalone(self):
        root = tk.Tk()
        root.withdraw()
        self._build_window(as_toplevel=False, standalone_root=root)
        root.mainloop()
        self._running = False

    def _build_window(self, as_toplevel: bool, standalone_root=None):
        parent = self._external_root if as_toplevel else standalone_root
        win = tk.Toplevel(parent)
        self._win = win
        win.title("Nicky")
        win.geometry(f"{_WIN_W}x{_WIN_H}+60+60")
        win.resizable(True, True)
        win.minsize(_WIN_W, 300)
        win.attributes("-topmost", True)
        win.attributes("-alpha", _ALPHA)
        win.configure(bg=_BG)
        win.overrideredirect(True)

        # Title bar (drag area + close button)
        title_bar = tk.Frame(win, bg="#0a0a18", height=28)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        tk.Label(title_bar, text="  Nicky AI", fg=_TEXT_FG, bg="#0a0a18",
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, pady=4)
        tk.Button(title_bar, text="✕", fg="#ff5050", bg="#0a0a18",
                  activebackground="#1a0a0a", activeforeground="#ff5050",
                  relief="flat", bd=0, font=("Segoe UI", 9),
                  command=self.close).pack(side=tk.RIGHT, padx=6)
        title_bar.bind("<ButtonPress-1>",  self._on_drag_start)
        title_bar.bind("<B1-Motion>",      self._on_drag_move)

        # Logo canvas (vibrates)
        canvas = tk.Canvas(win, width=_WIN_W, height=_LOGO_H,
                           bg=_BG, highlightthickness=0)
        canvas.pack(fill=tk.X, side=tk.TOP)
        self._canvas = canvas
        self._draw_logo()

        tk.Frame(win, height=1, bg=_SEP_COLOR).pack(fill=tk.X, padx=10, side=tk.TOP)

        # ── Pack footer + input FIRST (side=BOTTOM) so they always get space ──

        # Footer
        tk.Label(win, text="by Moofun", fg="#303055", bg=_BG,
                 font=("Segoe UI", 7)).pack(side=tk.BOTTOM, pady=(0, 4))

        # Input area
        input_outer = tk.Frame(win, bg="#0d0d20")
        input_outer.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Frame(input_outer, height=1, bg=_GLOW_IDLE).pack(fill=tk.X)  # top accent line

        inner = tk.Frame(input_outer, bg="#0d0d20", padx=8, pady=6)
        inner.pack(fill=tk.X)

        tk.Label(inner, text="Ask Nicky:", fg=_TEXT_FG, bg="#0d0d20",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 3))

        input_row = tk.Frame(inner, bg="#0d0d20")
        input_row.pack(fill=tk.X)

        entry_border = tk.Frame(input_row, bg=_GLOW_IDLE, padx=1, pady=1)
        entry_border.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._entry = tk.Entry(entry_border, bg="#0a0a1e", fg=_INPUT_FG,
                               insertbackground=_TEXT_FG,
                               relief="flat", font=("Segoe UI", 10), bd=4)
        self._entry.pack(fill=tk.X, ipady=6)
        self._entry.bind("<Return>", self._on_enter)
        self._entry.bind("<Escape>", lambda e: self._entry.delete(0, tk.END))
        self._entry.bind("<FocusIn>",  lambda e: entry_border.config(bg=_TEXT_FG))
        self._entry.bind("<FocusOut>", lambda e: entry_border.config(bg=_GLOW_IDLE))

        tk.Button(input_row, text="Send", fg="#ffffff", bg="#1040a0",
                  activebackground=_GLOW_IDLE, activeforeground="#ffffff",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10,
                  command=lambda: self._on_enter(None)).pack(side=tk.RIGHT, padx=(6, 0))

        win.after(150, self._entry.focus_set)

        tk.Frame(win, height=1, bg=_SEP_COLOR).pack(side=tk.BOTTOM, fill=tk.X, padx=10)

        # ── Scrollable response area fills whatever is left ────────────────────
        resp_frame = tk.Frame(win, bg=_BG)
        resp_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 2))

        scrollbar = tk.Scrollbar(resp_frame, bg=_SCROLL_BG,
                                 troughcolor=_BG, bd=0, width=8)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        resp = tk.Text(resp_frame, wrap=tk.WORD,
                       bg=_BG, fg=_RESP_FG,
                       font=("Segoe UI", 10),
                       relief="flat", bd=0, padx=6,
                       yscrollcommand=scrollbar.set,
                       state=tk.DISABLED, cursor="arrow")
        resp.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=resp.yview)
        self._resp_text = resp

        resp.tag_config("nicky_name", foreground=_TEXT_FG,   font=("Segoe UI", 9, "bold"))
        resp.tag_config("nicky_msg",  foreground=_RESP_FG,   font=("Segoe UI", 10))
        resp.tag_config("user_name",  foreground="#a8d8ff",  font=("Segoe UI", 9, "bold"))
        resp.tag_config("user_msg",   foreground="#c0d8f0",  font=("Segoe UI", 10))

        self._running = True
        self._animate()

    def _append_text(self, sender: str, message: str):
        """Insert a chat bubble. Must run on Tk thread."""
        if not self._resp_text:
            return
        t = self._resp_text
        t.config(state=tk.NORMAL)
        if t.get("1.0", tk.END).strip():
            t.insert(tk.END, "\n")
        if sender == "Nicky":
            t.insert(tk.END, "Nicky  ", "nicky_name")
            t.insert(tk.END, message + "\n", "nicky_msg")
        else:
            t.insert(tk.END, "You  ", "user_name")
            t.insert(tk.END, message + "\n", "user_msg")
        t.config(state=tk.DISABLED)
        t.see(tk.END)

    def _on_enter(self, event):
        if not self._entry:
            return
        text = self._entry.get().strip()
        if not text:
            return
        self._entry.delete(0, tk.END)
        self._win.after(0, lambda: self._append_text("You", text))

        if self._input_cb:
            def _run():
                try:
                    response = self._input_cb(text)
                    if response:
                        clean = response.replace("[Nicky] ", "").strip()
                        if self._win:
                            self._win.after(0, lambda r=clean: self._append_text("Nicky", r))
                except Exception:
                    pass
            threading.Thread(target=_run, daemon=True).start()

    # ── Logo drawing + animation ───────────────────────────────────────────────

    def _draw_logo(self):
        c, r = self._canvas, _RADIUS
        c.create_oval(_CX-r-8, _CY-r-8, _CX+r+8, _CY+r+8,
                      fill="#0a1530", outline=_GLOW_IDLE, width=2, tags="glow")
        c.create_oval(_CX-r, _CY-r, _CX+r, _CY+r,
                      fill=_CIRCLE_BG, outline=_TEXT_FG, width=3, tags="circle")
        c.create_text(_CX, _CY, text="N", fill=_TEXT_FG,
                      font=("Segoe UI", 32, "bold"), tags="letter")
        c.create_text(_CX, _CY + r + 14, text="Nicky AI", fill=_LABEL_FG,
                      font=("Segoe UI", 8), tags="sublabel")

    def _animate(self):
        if not self._running:
            return

        if self._speaking:
            if self._schedule and self._sched_idx < len(self._schedule):
                amp = self._schedule[self._sched_idx]
                self._sched_idx += 1
            else:
                amp = 0.15

            self._phase += 1
            t = self._phase * 0.45
            raw_x = amp * math.sin(t * 2.3) + amp * 0.4 * math.sin(t * 5.1)
            raw_y = amp * math.cos(t * 3.1) + amp * 0.4 * math.cos(t * 4.7)
            target_x = int(raw_x * _MAX_SHAKE)
            target_y = int(raw_y * _MAX_SHAKE)

            dx = target_x - self._offset_x
            dy = target_y - self._offset_y
            if dx or dy:
                for tag in ("glow", "circle", "letter"):
                    self._canvas.move(tag, dx, dy)
                self._offset_x = target_x
                self._offset_y = target_y

            glow_color = _GLOW_TALK if amp > 0.6 else _GLOW_IDLE
            self._canvas.itemconfig("glow",   outline=glow_color)
            self._canvas.itemconfig("circle", outline=glow_color if amp > 0.7 else _TEXT_FG)

            self._win.after(_FRAME_MS, self._animate)
        else:
            if self._offset_x != 0 or self._offset_y != 0:
                for tag in ("glow", "circle", "letter"):
                    self._canvas.move(tag, -self._offset_x, -self._offset_y)
                self._offset_x = 0
                self._offset_y = 0
                self._canvas.itemconfig("glow",   outline=_GLOW_IDLE)
                self._canvas.itemconfig("circle", outline=_TEXT_FG)
                self._phase = 0
                self._schedule = []
            self._win.after(80, self._animate)

    def _on_drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_move(self, event):
        x = self._win.winfo_x() + (event.x - self._drag_x)
        y = self._win.winfo_y() + (event.y - self._drag_y)
        self._win.geometry(f"+{x}+{y}")

