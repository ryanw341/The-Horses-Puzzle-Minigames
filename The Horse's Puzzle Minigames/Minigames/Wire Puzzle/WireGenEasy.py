#!/usr/bin/env python3
"""
40k Control‑Panel Wiring Puzzle — v13.4  (2025‑07‑23)
=====================================================
Six‑socket test build with **randomised rules** and a strict
**no-duplicate / optional hint** policy:

• Visible rules alone always isolate a single wiring.
• The hint is **never one of the visible rules**. If no extra rule is left,
  there is simply no Hint (button is hidden/disabled).
• Alphabet rule randomly flips (first left OR right of last).
• System/adjacency rules pick random colours, so it's not always White/Orange, etc.
• Tautologies (true for all wirings) and impossibles (true for none) are dropped.
• All GUI fixes retained: ghost-drag, full-socket hit boxes, click to unplug.

Run
~~~
GUI (default):   python wire_puzzle6.py
CLI:             python wire_puzzle6.py --cli
Seeded puzzle:   python wire_puzzle6.py --seed 42
Min rules:       python wire_puzzle6.py --min-rules 5
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
except ImportError:
    tk = None  # type: ignore

# ════════════════════════ Global configuration ════════════════════════════
CABLE_COLOURS: List[str] = ["Black", "Blue", "White", "Red", "Orange", "Green"]
SOCKET_EMPTY_STYLE = "Sock.empty.TFrame"

BOARD_LAYOUTS: Dict[str, Dict] = {
    "ring-6": {
        "symbols":   ["Δ", "Ω", "Σ", "Φ", "Ψ", "Θ"],
        "systems":   ["Shield", "Cog", "Gravitas", "Open", "Cog", "Gravitas"],
        "edges":     (0, 5),
        "diametric": 3,
    },
}

# ────────────────────────────── Helpers ───────────────────────────────────
_left_of   = lambda a, b: a + 1 == b
_adjacent  = lambda a, b: abs(a - b) == 1
_wrap_adj  = lambda a, b, n: abs(a - b) in (1, n - 1)
_opposite  = lambda a, b, n, d: abs(a - b) % n == d

def _ring_dist(a: int, b: int, n: int) -> int:
    d = abs(a - b)
    return min(d, n - d)

@dataclass(frozen=True)
class Rule:
    text: str
    func: Callable[[Tuple[int, ...]], bool]
    def __call__(self, wiring: Tuple[int, ...]) -> bool:
        return self.func(wiring)

# ───────────────────────────── Rule pool (randomised) ─────────────────────
def _build_rule_pool(board: Dict, ci: Dict[str, int], rng: _rand.Random) -> List[Rule]:
    syms, systems   = board["symbols"], board["systems"]
    edges, diam_off = board["edges"], board["diametric"]
    n               = len(syms)
    P: List[Rule]   = []

    # Always-useful anchor rule
    P.append(Rule(
        f"Black occupies an edge socket ({syms[edges[0]]} or {syms[edges[1]]}).",
        lambda w, e=edges, c=ci["Black"]: w[c] in e
    ))

    # Randomly choose two distinct colours (not Black) for Shield vs Gravitas constraints
    non_black = [c for c in CABLE_COLOURS if c != "Black"]
    shield_col, grav_col = rng.sample(non_black, 2)
    P.append(Rule(
        f"{shield_col} connects to Shield and never neighbours {grav_col}.",
        lambda w, s=systems, ci=ci, n=n, A=shield_col, B=grav_col: (
            s[w[ci[A]]] == "Shield" and not _wrap_adj(w[ci[A]], w[ci[B]], n)
        )
    ))
    P.append(Rule(
        f"{grav_col} connects to Gravitas and never neighbours {shield_col}.",
        lambda w, s=systems, ci=ci, n=n, A=grav_col, B=shield_col: (
            s[w[ci[A]]] == "Gravitas" and not _wrap_adj(w[ci[A]], w[ci[B]], n)
        )
    ))

    # Blue left of one of two colours' Gravitas sockets (exclude Blue itself)
    pair_candidates = [c for c in CABLE_COLOURS if c != "Blue"]
    grav_pair = rng.sample(pair_candidates, 2)
    P.append(Rule(
        f"Blue sits immediately left of the Gravitas cable ({grav_pair[0]} or {grav_pair[1]}) and is not on a Gravitas socket.",
        lambda w, s=systems, ci=ci, pair=tuple(grav_pair): (
            (_left_of(w[ci["Blue"]], w[ci[pair[0]]]) or _left_of(w[ci["Blue"]], w[ci[pair[1]]]))
            and s[w[ci["Blue"]]] != "Gravitas"
        )
    ))

    # Green farthest Cog from Black (kept constant)
    cog_positions = [i for i, sys in enumerate(systems) if sys == "Cog"]
    P.append(Rule(
        "Green occupies the Cog socket farthest from Black.",
        lambda w, cs=cog_positions, ci=ci, n=n: (
            w[ci["Green"]] == (cs[0] if _ring_dist(cs[0], w[ci["Black"]], n) > _ring_dist(cs[1], w[ci["Black"]], n) else cs[1])
        )
    ))

    # Two colours share Gravitas, first avoids both second and one random other
    g_pair = rng.sample([c for c in CABLE_COLOURS if c not in ("Black",)], 2)
    extra_avoid = rng.choice([c for c in CABLE_COLOURS if c not in g_pair])
    A, B = g_pair
    P.append(Rule(
        f"{A} uses the Gravitas socket not taken by {B} and neighbours neither {B} nor {extra_avoid}.",
        lambda w, s=systems, ci=ci, n=n, A=A, B=B, X=extra_avoid: (
            s[w[ci[A]]] == "Gravitas" and s[w[ci[B]]] == "Gravitas" and w[ci[A]] != w[ci[B]] and
            not _wrap_adj(w[ci[A]], w[ci[B]], n) and not _wrap_adj(w[ci[A]], w[ci[X]], n)
        )
    ))

    # Exactly-one-on-Gravitas among a random triple
    triple = rng.sample(CABLE_COLOURS, 3)
    P.append(Rule(
        f"Among {triple[0]}/{triple[1]}/{triple[2]}, exactly one is on a Gravitas socket.",
        lambda w, s=systems, ci=ci, T=tuple(triple): sum(s[w[ci[c]]] == "Gravitas" for c in T) == 1
    ))

    # Alphabet rule randomly left or right
    first, last = min(ci, key=str), max(ci, key=str)
    if rng.choice([True, False]):
        P.append(Rule(
            "The alphabetically first colour sits left of the alphabetically last.",
            lambda w, ci=ci, f=first, l=last: w[ci[f]] < w[ci[l]]
        ))
    else:
        P.append(Rule(
            "The alphabetically first colour sits right of the alphabetically last.",
            lambda w, ci=ci, f=first, l=last: w[ci[f]] > w[ci[l]]
        ))

    return P

# ═════════════════════════ Permutation cache & solver ═════════════════════
_PERM_CACHE: Dict[int, List[Tuple[int, ...]]] = {}

def _perms(n: int) -> List[Tuple[int, ...]]:
    if n not in _PERM_CACHE:
        _PERM_CACHE[n] = list(_it.permutations(range(n)))
    return _PERM_CACHE[n]

class _NoPuzzle(RuntimeError):
    pass

def _precompute_rule_sets(rules: Sequence[Rule], perms: Sequence[Tuple[int, ...]]) -> List[Set[int]]:
    return [{i for i, p in enumerate(perms) if r(p)} for r in rules]


def _unique_subset(sol_idx: int, compat: Sequence[int], rule_sets: List[Set[int]], total: int) -> List[int] | None:
    """Smallest-first greedy isolation set."""
    remaining = set(range(total))
    chosen: List[int] = []
    for idx in sorted(compat, key=lambda j: len(rule_sets[j])):
        if sol_idx not in rule_sets[idx]:
            continue
        new = remaining & rule_sets[idx]
        if len(new) < len(remaining):
            remaining = new
            chosen.append(idx)
            if len(remaining) == 1 and sol_idx in remaining:
                return chosen
    return None


def _solve_fast(sol_idx: int, compat: Sequence[int], rule_sets: List[Set[int]],
                min_rules: int, rng: _rand.Random, total: int) -> Tuple[List[int], int | None] | None:
    # Drop tautologies/impossibles
    useful = [i for i in compat if 0 < len(rule_sets[i]) < total]
    base = _unique_subset(sol_idx, useful, rule_sets, total)
    if base is None:
        return None
    visible = set(base)
    # Pad with more useful rules without breaking uniqueness
    for idx in useful:
        if idx in visible:
            continue
        inter = set(range(total))
        for j in visible | {idx}:
            inter &= rule_sets[j]
            if len(inter) == 0:
                break
        if len(inter) == 1 and sol_idx in inter:
            visible.add(idx)
        if len(visible) >= min_rules:
            break
    if len(visible) < min_rules:
        return None
    extras = [i for i in useful if i not in visible]
    hint_idx: int | None = rng.choice(extras) if extras else None
    return sorted(visible), hint_idx


def generate_puzzle(*, seed: int | None = None, board_key: str = "ring-6",
                     min_rules: int = 5, max_checks: int | None = None) -> Dict:
    rng   = _rand.Random(seed)
    board = BOARD_LAYOUTS[board_key]
    n     = len(board["symbols"])
    ci    = {c: i for i, c in enumerate(CABLE_COLOURS)}
    pool  = _build_rule_pool(board, ci, rng)
    perms = _perms(n)
    rule_sets = _precompute_rule_sets(pool, perms)

    indices = list(range(len(perms)))
    rng.shuffle(indices)

    tries = 0
    for sol_idx in indices:
        if max_checks is not None and tries >= max_checks:
            break
        tries += 1
        compat = [i for i, m in enumerate(rule_sets) if sol_idx in m]
        solved = _solve_fast(sol_idx, compat, rule_sets, min_rules, rng, len(perms))
        if solved:
            vis, hint_idx = solved
            return {
                "board": board,
                "solution": perms[sol_idx],
                "rules": [pool[i] for i in vis],
                "hint": (pool[hint_idx] if hint_idx is not None else None),
            }
    raise _NoPuzzle("No wiring obeys enough consistent rules — check rule set")

# ═══════════════════════════ CLI fallback ═════════════════════════════════
def play_cli(puz: Dict) -> None:
    syms, systems = puz["board"]["symbols"], puz["board"]["systems"]
    rules, sol    = puz["rules"], puz["solution"]

    print("\n« CONTROL PANEL »")
    print("Symbols :", " ".join(syms))
    print("Sockets :", " ".join(str(i + 1) for i in range(len(syms))))
    print("Systems :", " ".join(s[:3] for s in systems))
    print("\nRules:")
    for r in rules:
        print(" •", r.text)
    if puz["hint"] is not None:
        print("(Hint available: type 'hint')")
    placed = {c: None for c in CABLE_COLOURS}

    while True:
        cmd = input(" > ").strip().lower()
        if cmd in {"quit", "exit"}:
            return
        if cmd == "hint":
            if puz["hint"] is None:
                print("No hint for this puzzle.")
            else:
                print("Hint →", puz["hint"].text)
            continue
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
        while w is not None and not getattr(w, "is_socket", False):
            w = getattr(w, "master", None)
        if w is None:
            return None
        return getattr(w, "socket_frame", w)

    class Palette(ttk.Frame):
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
            self._ghost.place(x=x, y=y, anchor="nw")

        def _drag(self, ev):
            if not self._ghost:
                return
            root = self.winfo_toplevel()
            self._ghost.place_configure(x=ev.x_root - root.winfo_rootx(),
                                        y=ev.y_root - root.winfo_rooty())

        def _drop(self, ev):
            root = self.winfo_toplevel()
            if self._ghost:
                self._ghost.place_forget()
            x_root, y_root = ev.x_root, ev.y_root
            tgt  = root.winfo_containing(x_root, y_root)
            sock = _socket_from_widget(tgt)
            if sock is None:
                sockets = getattr(root, "_sockets", [])
                for s in sockets:
                    x0, y0 = s.winfo_rootx(), s.winfo_rooty()
                    if x0 <= x_root <= x0 + s.winfo_width() and y0 <= y_root <= y0 + s.winfo_height():
                        sock = s; break
            if sock is not None:
                self._plug(sock)
            else:
                self._return()
            if self._ghost:
                self._ghost.destroy(); self._ghost = None

        def _plug(self, sock: ttk.Frame) -> None:
            if hasattr(sock, "cable_colour"):
                gui = sock.winfo_toplevel(); gui._unwire(sock)  # type: ignore
            sock.configure(style=f"Sock.{self.colour.lower()}.TFrame")
            occ = tk.Label(sock, text=self.colour,
                           bg=self.colour.lower(), fg=_fg_for(self.colour), relief="flat")
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
        def __init__(self, puz: Dict, seed: int | None, min_rules: int):
            super().__init__()
            self.title("40k Control‑Panel Puzzle — 6‑Slot")
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
                mid.is_socket = True; mid.socket_frame = mid
                cell.is_socket = True; cell.socket_frame = mid
                for target in (cell, mid):
                    target.bind("<Button-1>", lambda e, s=mid: self._unwire(s))
                    target.bind("<Button-3>", lambda e, s=mid: self._unwire(s))
                ttk.Label(cell, text=sysn, font=("Consolas", 7)).pack()
                self.sockets.append(mid)

            # expose to draggables
            self._sockets = self.sockets

            self.palette = Palette(panel)
            self.palette.grid(row=1, column=0, columnspan=len(syms), pady=(10, 0))
            for idx, c in enumerate(CABLE_COLOURS):
                self.palette.add(c, idx)

            ttk.Label(rules, text="Magos Edicts", font=("Consolas", 12, "bold")).pack(anchor="w")
            self._rule_container = ttk.Frame(rules); self._rule_container.pack(anchor="w")
            self._render_rules()

            # Hint button only if hint exists
            if self.puz["hint"] is not None:
                self._hint_btn = ttk.Button(rules, text="Hint",
                                            command=lambda: messagebox.showinfo("Hint", self.puz["hint"].text))
                self._hint_btn.pack(pady=(10, 2))
            else:
                self._hint_btn = None
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
            # refresh rules and hint button
            self._render_rules()
            if self._hint_btn is not None:
                self._hint_btn.destroy()
                self._hint_btn = None
            rules_frame = self._rule_container.master  # parent of rule_container
            if self.puz["hint"] is not None:
                self._hint_btn = ttk.Button(rules_frame, text="Hint",
                                            command=lambda: messagebox.showinfo("Hint", self.puz["hint"].text))
                # Insert after rule list: pack before Check button by using before parameter is tricky; just pack now.
                self._hint_btn.pack(pady=(10, 2))

# ═════════════════════════════ Entrypoint ════════════════════════════════
def _main() -> None:
    ap = argparse.ArgumentParser(description="40k Control‑Panel Puzzle — 6‑Slot")
    ap.add_argument("--cli", action="store_true", help="text‑mode even if Tk available")
    ap.add_argument("--seed", type=int, help="PRNG seed for repeatable puzzle")
    ap.add_argument("--min-rules", type=int, default=5, help="minimum number of shown rules (excl. hint)")
    args = ap.parse_args()

    puzzle = generate_puzzle(seed=args.seed, min_rules=args.min_rules)

    if args.cli or tk is None:
        play_cli(puzzle)
    else:
        GUI(puzzle, args.seed, args.min_rules).mainloop()


if __name__ == "__main__":
    _main()
