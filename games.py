import random
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
