#!/usr/bin/env python3
"""
40k Control‑Panel Wiring Puzzle — v12.10  (2025‑07‑22)
======================================================
Fast, deterministic generator with **guaranteed unique solutions** and a Tk GUI.

Fixes vs v12.9
──────────────
1. **Unreliable drops solved** – the ghost label was sitting on top of the sockets,
   so `winfo_containing()` was often hitting the ghost itself. Now we hide the
   ghost *before* hit‑testing and also fall back to a manual bounding‑box scan.
2. **Whole socket click/drop area** – both grey frame and coloured pad are valid.
3. **Unplug always returns wire** – occupant & palette stay in sync.
4. **No TclErrors** – palette items never leave their grid; only a ghost moves.
"""
from __future__ import annotations

import argparse
import itertools as _it
import random as _rand
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Set, Tuple

# ────────────────────────────── Tk availability ────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:  # head‑less environment
    tk = None  # type: ignore

# ════════════════════════ Global configuration ════════════════════════════
CABLE_COLOURS: List[str] = [
    "Black", "Blue", "White", "Red", "Orange", "Green", "Yellow", "Violet"
]

SOCKET_EMPTY_STYLE = "Sock.empty.TFrame"

BOARD_LAYOUTS: Dict[str, Dict] = {
    "ring-8": {
        "symbols":  ["Δ", "Ω", "Σ", "Φ", "Π", "Λ", "Ψ", "Θ"],
        "systems":  ["Shield", "Cog", "Gravitas", "Shield",
                       "Open",   "Gravitas", "Cog", "Open"],
        "edges": (0, 7),          # sockets considered "edges"
        "diametric": 4,           # opposite sockets are 4 apart in an 8‑ring
    },
}

# ────────────────────────────── Helper predicates ──────────────────────────
_left_of   = lambda a, b: a + 1 == b
_adjacent  = lambda a, b: abs(a - b) == 1
_wrap_adj  = lambda a, b, n: abs(a - b) in (1, n - 1)
_opposite  = lambda a, b, n, d: abs(a - b) % n == d

# ──────────────────────────────── Rule object ──────────────────────────────
@dataclass(frozen=True)
class Rule:
    text: str
    func: Callable[[Tuple[int, ...]], bool]
    def __call__(self, wiring: Tuple[int, ...]) -> bool:
        return self.func(wiring)

# ─────────────────────────────── Rule pool build ───────────────────────────
def _build_rule_pool(board: Dict, ci: Dict[str, int]) -> List[Rule]:
    syms, systems   = board["symbols"], board["systems"]
    edges, diam_off = board["edges"], board["diametric"]
    n               = len(syms)
    P: List[Rule]   = []

    P.append(Rule(
        f"Black occupies an edge socket ({syms[edges[0]]} or {syms[edges[1]]}).",
        lambda w, e=edges, c=ci["Black"]: w[c] in e
    ))
    P.append(Rule(
        "Blue sits immediately left of the Gravitas cable (White or Orange) and is not on a Gravitas socket.",
        lambda w, s=systems, ci=ci: ((
            _left_of(w[ci["Blue"]], w[ci["White"]]) or _left_of(w[ci["Blue"]], w[ci["Orange"]]))
            and s[w[ci["Blue"]]] != "Gravitas")
    ))
    P.append(Rule(
        "Exactly two cables occupy Cog sockets.",
        lambda w, s=systems: sum(1 for p in w if s[p] == "Cog") == 2
    ))
    P.append(Rule(
        "Warm colours (Red, Orange, Yellow) never touch each other (ring adjacency).",
        lambda w, ci=ci, n=n: not any(
            _wrap_adj(w[ci[c1]], w[ci[c2]], n)
            for c1 in ("Red", "Orange", "Yellow")
            for c2 in ("Red", "Orange", "Yellow") if c1 < c2
        )
    ))
    P.append(Rule(
        "The alphabetically first colour sits left of the alphabetically last.",
        lambda w, ci=ci: w[ci[min(ci, key=str)]] < w[ci[max(ci, key=str)]]
    ))
    P.append(Rule(
        "White uses the Gravitas socket not taken by Orange and neighbours neither Red nor Orange.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["White"]]] == "Gravitas" and s[w[ci["Orange"]]] == "Gravitas" and
            w[ci["White"]] != w[ci["Orange"]] and
            not _adjacent(w[ci["White"]], w[ci["Red"]]) and
            not _adjacent(w[ci["White"]], w[ci["Orange"]])
        )
    ))
    P.append(Rule(
        "Red connects to Shield and never neighbours Orange.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["Red"]]] == "Shield" and not _adjacent(w[ci["Red"]], w[ci["Orange"]])
        )
    ))
    P.append(Rule(
        "Orange connects to Gravitas and never neighbours Red.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["Orange"]]] == "Gravitas" and not _adjacent(w[ci["Orange"]], w[ci["Red"]])
        )
    ))
    cog = [i for i, sys in enumerate(systems) if sys == "Cog"]
    P.append(Rule(
        "Green occupies the Cog socket farthest from Black.",
        lambda w, cs=cog, e=edges, ci=ci: w[ci["Green"]] == (cs[0] if w[ci["Black"]] == e[1] else cs[1])
    ))
    P.append(Rule(
        "Yellow sits diametrically opposite Red and is not adjacent to it.",
        lambda w, n=n, d=diam_off, ci=ci: (
            _opposite(w[ci["Yellow"]], w[ci["Red"]], n, d) and not _adjacent(w[ci["Yellow"]], w[ci["Red"]])
        )
    ))
    P.append(Rule(
        "Violet never neighbours Black (ring adjacency).",
        lambda w, n=n, ci=ci: not _wrap_adj(w[ci["Violet"]], w[ci["Black"]], n)
    ))
    P.append(Rule(
        "Exactly three cables are on Open sockets.",
        lambda w, s=systems: sum(1 for p in w if s[p] == "Open") == 3
    ))
    P.append(Rule(
        "Among Blue/Green/Violet, exactly one sits on a Shield socket.",
        lambda w, s=systems, ci=ci: sum(s[w[ci[c]]] == "Shield" for c in ("Blue", "Green", "Violet")) == 1
    ))
    return P

# ───────────────────────── puzzle generator (FAST) ─────────────────────────
class _NoPuzzle(RuntimeError):
    pass

_PERMS_8: List[Tuple[int, ...]] = list(_it.permutations(range(8)))
_NP = len(_PERMS_8)


def _precompute_rule_sets(rules: Sequence[Rule]) -> List[Set[int]]:
    masks: List[Set[int]] = []
    for r in rules:
        ok = {i for i, p in enumerate(_PERMS_8) if r(p)}
        masks.append(ok)
    return masks


def _solve_fast(sol_idx: int, compat_idxs: Sequence[int], rule_sets: List[Set[int]],
                min_rules: int, rng: _rand.Random) -> Tuple[List[int], int] | None:
    remaining = set(range(_NP))
    chosen: List[int] = []
    for idx in sorted(compat_idxs, key=lambda j: len(rule_sets[j])):
        if sol_idx not in rule_sets[idx]:
            continue
        new = remaining & rule_sets[idx]
        if len(new) < len(remaining):
            remaining = new
            chosen.append(idx)
            if len(remaining) == 1 and sol_idx in remaining:
                break
    if len(remaining) != 1 or sol_idx not in remaining:
        return None
    if len(chosen) < min_rules:
        extra = [i for i in compat_idxs if i not in chosen and sol_idx in rule_sets[i]]
        rng.shuffle(extra)
        for idx in extra:
            chosen.append(idx)
            if len(chosen) >= min_rules:
                break
        if len(chosen) < min_rules:
            return None
    hint_idx = rng.choice(chosen)
    chosen.remove(hint_idx)
    return chosen, hint_idx


def generate_puzzle(*, seed: int | None = None, board_key: str = "ring-8",
                     min_rules: int = 6, max_checks: int | None = None) -> Dict:
    rng  = _rand.Random(seed)
    board = BOARD_LAYOUTS[board_key]
    ci   = {c: i for i, c in enumerate(CABLE_COLOURS)}
    pool = _build_rule_pool(board, ci)
    rule_sets = _precompute_rule_sets(pool)

    perm_indices = list(range(_NP))
    rng.shuffle(perm_indices)

    tries = 0
    for sol_idx in perm_indices:
        if max_checks is not None and tries >= max_checks:
            break
        tries += 1
        compat_idxs = [i for i, m in enumerate(rule_sets) if sol_idx in m]
        solved = _solve_fast(sol_idx, compat_idxs, rule_sets, min_rules, rng)
        if solved is None:
            continue
        chosen_idxs, hint_idx = solved
        return {
            "board": board,
            "solution": _PERMS_8[sol_idx],
            "rules": [pool[i] for i in chosen_idxs],
            "hint": pool[hint_idx],
        }
    raise _NoPuzzle("No wiring obeys enough consistent rules — check rule set")

# ═══════════════════════════ CLI fallback ═════════════════════════════════
def play_cli(puz: Dict) -> None:
    syms, systems = puz["board"]["symbols"], puz["board"]["systems"]
    rules, sol    = puz["rules"], puz["solution"]

    print("« CONTROL PANEL »")
    print("Symbols :", " ".join(syms))
    print("Sockets :", " ".join(str(i + 1) for i in range(len(syms))))
    print("Systems :", " ".join(s[:3] for s in systems))
    print("Rules:")
    for r in rules:
        print(" •", r.text)
    placed = {c: None for c in CABLE_COLOURS}

    while True:
        cmd = input(" > ").strip().lower()
        if cmd in {"quit", "exit"}:
            return
        if cmd == "hint":
            print("Hint →", puz["hint"].text); continue
        if cmd == "done":
            if None in placed.values():
                print("Place all cables first."); continue
            guess = tuple(placed[c] for c in CABLE_COLOURS)
            print("✓ Correct!" if guess == sol else "✗ Wrong wiring."); return
        try:
            col, pos = cmd.split(); col = col.capitalize(); pos = int(pos) - 1
            if col not in CABLE_COLOURS or not 0 <= pos < len(syms):
                raise ValueError
            placed[col] = pos
        except ValueError:
            print("Bad input. Example:  blue 3   | hint | done")

# ═══════════════════════════ Tk GUI implementation ════════════════════════
if tk is not None:

    def _fg_for(bg: str) -> str:
        return "black" if bg.lower() in {"white", "yellow"} else "white"

    def _socket_from_widget(w):
        """Walk up parents to find a widget flagged as a socket; return canonical frame."""
        while w is not None and not getattr(w, "is_socket", False):
            w = getattr(w, "master", None)
        if w is None:
            return None
        return getattr(w, "socket_frame", w)

    class Palette(ttk.Frame):
        """Fixed grid palette: each colour remembers its column."""
        def __init__(self, master):
            super().__init__(master)
            self.widgets: Dict[str, Draggable] = {}
        def hide(self, d: "Draggable") -> None:
            try: d.grid_remove()
            except tk.TclError: pass
        def show(self, d: "Draggable") -> None:
            d.grid(row=0, column=d._col, padx=2, pady=2)
        def add(self, colour: str, idx: int) -> None:
            d = Draggable(self, colour, idx)
            d.grid(row=0, column=idx, padx=2, pady=2)
            self.widgets[colour] = d

    class Draggable(ttk.Label):
        """Palette item; we drag a ghost label instead of this real widget."""
        def __init__(self, palette: Palette, colour: str, col_index: int):
            super().__init__(palette, text=colour,
                             background=colour.lower(), foreground=_fg_for(colour),
                             width=8, anchor="center", relief="raised")
            self.palette = palette
            self.colour = colour
            self._col = col_index
            self.socket: ttk.Frame | None = None
            self._ghost: tk.Label | None = None
            self.bind("<ButtonPress-1>",  self._start_drag)
            self.bind("<B1-Motion>",      self._drag)
            self.bind("<ButtonRelease-1>", self._drop)

        def _start_drag(self, ev):
            root = self.winfo_toplevel()
            x = ev.x_root - root.winfo_rootx()
            y = ev.y_root - root.winfo_rooty()
            self._ghost = tk.Label(root, text=self.colour,
                                   bg=self.colour.lower(), fg=_fg_for(self.colour),
                                   width=8, relief="raised")
            self._ghost.place(x=x, y=y, anchor="nw")  # top-left at cursor

        def _drag(self, ev):
            if not self._ghost:
                return
            root = self.winfo_toplevel()
            self._ghost.place_configure(x=ev.x_root - root.winfo_rootx(),
                                        y=ev.y_root - root.winfo_rooty())

        def _drop(self, ev):
            root = self.winfo_toplevel()
            # hide ghost BEFORE hit-test so it doesn't block
            if self._ghost:
                self._ghost.place_forget()
            x_root, y_root = ev.x_root, ev.y_root
            tgt = root.winfo_containing(x_root, y_root)
            sock = _socket_from_widget(tgt)
            if sock is None:
                # manual bbox fallback
                gui = root  # Tk
                sockets = getattr(gui, "_sockets", [])
                for s in sockets:
                    x0, y0 = s.winfo_rootx(), s.winfo_rooty()
                    x1, y1 = x0 + s.winfo_width(), y0 + s.winfo_height()
                    if x0 <= x_root <= x1 and y0 <= y_root <= y1:
                        sock = s; break
            if sock is not None:
                self._plug(sock)
            else:
                self._return()
            if self._ghost:
                self._ghost.destroy(); self._ghost = None

        # ── helpers ────────────────────────────────────────────────
        def _plug(self, sock: ttk.Frame) -> None:
            if hasattr(sock, "cable_colour"):
                gui = sock.winfo_toplevel()
                gui._unwire(sock)  # type: ignore
            sock.configure(style=f"Sock.{self.colour.lower()}.TFrame")
            occ = tk.Label(sock, text=self.colour,
                           bg=self.colour.lower(), fg=_fg_for(self.colour),
                           relief="flat")
            occ.place(relx=0, rely=0, relwidth=1, relheight=1)
            gui = sock.winfo_toplevel()
            occ.bind("<Button-1>", lambda e, s=sock: gui._unwire(s))
            occ.bind("<Button-3>", lambda e, s=sock: gui._unwire(s))
            sock.cable_widget = occ  # type: ignore
            sock.cable_colour = self.colour  # type: ignore
            self.socket = sock
            self.palette.hide(self)

        def _return(self) -> None:
            self.socket = None
            self.palette.show(self)

    class GUI(tk.Tk):
        """Main window."""
        def __init__(self, puz: Dict, seed: int | None, min_rules: int):
            super().__init__()
            self.title("40k Control‑Panel Puzzle")
            self.resizable(False, True)
            self.puz = puz
            self.seed = seed
            self.min_rules = min_rules
            self._styles(); self._build()

        def _styles(self) -> None:
            s = ttk.Style(self)
            s.configure(SOCKET_EMPTY_STYLE, background="#d9d9d9")
            for c in CABLE_COLOURS:
                s.configure(f"Sock.{c.lower()}.TFrame", background=c.lower())

        def _build(self) -> None:
            syms, systems = self.puz["board"]["symbols"], self.puz["board"]["systems"]
            main = ttk.Frame(self, padding=10); main.pack()
            panel = ttk.Frame(main); panel.grid(row=0, column=0, padx=(0, 20))
            rules = ttk.Frame(main); rules.grid(row=0, column=1, sticky="n")

            self.sockets: List[ttk.Frame] = []
            for i, (sym, sysn) in enumerate(zip(syms, systems)):
                cell = ttk.Frame(panel, width=60, height=90, style=SOCKET_EMPTY_STYLE)
                cell.grid(row=0, column=i, padx=2)
                cell.grid_propagate(False)
                ttk.Label(cell, text=sym, font=("Consolas", 12, "bold")).pack()
                mid = ttk.Frame(cell, width=50, height=35, style=SOCKET_EMPTY_STYLE)
                mid.pack(pady=2)
                mid.is_socket = True; mid.socket_frame = mid  # canonical
                cell.is_socket = True; cell.socket_frame = mid
                for target in (cell, mid):
                    target.bind("<Button-1>", lambda e, s=mid: self._unwire(s))
                    target.bind("<Button-3>", lambda e, s=mid: self._unwire(s))
                ttk.Label(cell, text=sysn, font=("Consolas", 7)).pack()
                self.sockets.append(mid)

            # expose sockets list for Draggable fallback hit-test
            self._sockets = self.sockets

            self.palette = Palette(panel)
            self.palette.grid(row=1, column=0, columnspan=len(syms), pady=(10, 0))
            for idx, c in enumerate(CABLE_COLOURS):
                self.palette.add(c, idx)

            ttk.Label(rules, text="Magos Edicts", font=("Consolas", 12, "bold")).pack(anchor="w")
            self._rule_container = ttk.Frame(rules); self._rule_container.pack(anchor="w")
            self._render_rules()

            ttk.Button(rules, text="Hint",
                       command=lambda: messagebox.showinfo("Hint", self.puz["hint"].text)).pack(pady=(10, 2))
            ttk.Button(rules, text="Check", command=self._check).pack()
            ttk.Button(rules, text="New Puzzle", command=self._new_puzzle).pack(pady=(12, 0))

        def _render_rules(self) -> None:
            for w in self._rule_container.winfo_children():
                w.destroy()
            for r in self.puz["rules"]:
                ttk.Label(self._rule_container, text="• " + r.text,
                          wraplength=240, justify="left").pack(anchor="w", pady=1)

        def _unwire(self, sock: ttk.Frame) -> None:
            if hasattr(sock, "cable_colour"):
                colour = sock.cable_colour  # type: ignore
                sock.cable_widget.destroy()  # type: ignore
                delattr(sock, "cable_widget")
                delattr(sock, "cable_colour")
                sock.configure(style=SOCKET_EMPTY_STYLE)
                d = self.palette.widgets[colour]
                d.socket = None
                self.palette.show(d)

        def _current(self) -> Tuple[int, ...]:
            mapping = [-1] * len(CABLE_COLOURS)
            for colour, d in self.palette.widgets.items():
                if d.socket is not None:
                    mapping[CABLE_COLOURS.index(colour)] = self.sockets.index(d.socket)
            return tuple(mapping)

        def _check(self) -> None:
            wiring = self._current()
            if -1 in wiring:
                messagebox.showwarning("Incomplete", "Wire all sockets before checking.")
                return
            messagebox.showinfo("Result", "Access granted!" if wiring == self.puz["solution"] else "Incorrect wiring.")

        def _new_puzzle(self) -> None:
            new_seed = _rand.randrange(1 << 30)
            try:
                puz = generate_puzzle(seed=new_seed, min_rules=self.min_rules)
            except _NoPuzzle as e:
                messagebox.showerror("Error", str(e)); return
            self.puz = puz
            for sock in self.sockets:
                if hasattr(sock, "cable_colour"):
                    sock.cable_widget.destroy()  # type: ignore
                    delattr(sock, "cable_widget")
                    delattr(sock, "cable_colour")
                sock.configure(style=SOCKET_EMPTY_STYLE)
            for d in self.palette.widgets.values():
                d.socket = None
                self.palette.show(d)
            self._render_rules()

# ═════════════════════════════ Entrypoint ════════════════════════════════
def _main() -> None:
    ap = argparse.ArgumentParser(description="40k Control‑Panel Puzzle")
    ap.add_argument("--cli", action="store_true", help="text‑mode even if Tk available")
    ap.add_argument("--seed", type=int, help="PRNG seed for repeatable puzzle")
    ap.add_argument("--min-rules", type=int, default=6, help="minimum number of shown rules (excl. hint)")
    args = ap.parse_args()

    puzzle = generate_puzzle(seed=args.seed, min_rules=args.min_rules)

    if args.cli or tk is None:
        play_cli(puzzle)
    else:
        GUI(puzzle, args.seed, args.min_rules).mainloop()


if __name__ == "__main__":
    _main()
