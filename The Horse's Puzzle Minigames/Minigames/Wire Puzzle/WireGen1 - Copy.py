#!/usr/bin/env python3
"""40k Control‑Panel Wiring Puzzle — v11 (2025‑07‑22)
====================================================
• Palette now **re‑flows** whenever a cable is removed or returned
  (no empty slots, wrap at 8 per row).
• Drag, double‑click and right‑click behaviour unchanged.
"""

from __future__ import annotations
import itertools as _it, random as _rand
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

# ───────────────────────────── Tk availability ────────────────────────────
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None      # head‑less

# ═══════════════════════════ Globals / config ═════════════════════════════
CABLE_COLOURS = ["Black", "Blue", "White", "Red",
                 "Orange", "Green", "Yellow", "Violet"]
SOCKET_EMPTY_STYLE = "Sock.empty.TFrame"

# ═══════════════════════════ Board definition ═════════════════════════════
BOARD_LAYOUTS = {
    "ring‑8": {
        "symbols":  ["Δ", "Ω", "Σ", "Φ", "Π", "Λ", "Ψ", "Θ"],
        "systems":  ["Shield", "Cog", "Gravitas", "Shield",
                     "Open",   "Gravitas", "Cog", "Open"],
        "edges": (0, 7),
        "diametric": 4,
    },
}

# ═══════════════════════════ Helper predicates ════════════════════════════
_left_of   = lambda a, b: a + 1 == b
_adjacent  = lambda a, b: abs(a - b) == 1
_opposite  = lambda a, b, n, d: abs(a - b) % n == d

# ═══════════════════════════ Rule machinery ═══════════════════════════════
@dataclass(frozen=True)
class Rule:
    text: str
    func: Callable[[Tuple[int, ...]], bool]
    def check(self, w: Tuple[int, ...]) -> bool: return self.func(w)


def _build_rule_templates(board: Dict, ci: Dict[str, int]) -> List[Rule]:
    syms, systems, n        = board["symbols"], board["systems"], len(board["symbols"])
    edges, diam             = board["edges"], board["diametric"]
    pool: List[Rule]        = []

    pool.append(Rule(
        f"Black occupies an edge socket ({syms[edges[0]]} or {syms[edges[1]]}).",
        lambda w, e=edges, c=ci["Black"]: w[c] in e
    ))
    pool.append(Rule(
        "Blue sits immediately left of the Gravitas cable (White or Orange) "
        "and is not on Gravitas.",
        lambda w, s=systems, ci=ci: (
            (_left_of(w[ci["Blue"]], w[ci["White"]])
             or _left_of(w[ci["Blue"]], w[ci["Orange"]]))
            and s[w[ci["Blue"]]] != "Gravitas"
        )
    ))
    pool.append(Rule(
        "White uses the Gravitas socket not taken by Orange and neighbours neither Red nor Orange.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["White"]]] == "Gravitas"
            and s[w[ci["Orange"]]] == "Gravitas"
            and w[ci["White"]] != w[ci["Orange"]]
            and not _adjacent(w[ci["White"]], w[ci["Red"]])
            and not _adjacent(w[ci["White"]], w[ci["Orange"]])
        )
    ))
    pool.append(Rule(
        "Red connects to Shield and never neighbours Orange.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["Red"]]] == "Shield"
            and not _adjacent(w[ci["Red"]], w[ci["Orange"]])
        )
    ))
    pool.append(Rule(
        "Orange connects to Gravitas and never neighbours Red.",
        lambda w, s=systems, ci=ci: (
            s[w[ci["Orange"]]] == "Gravitas"
            and not _adjacent(w[ci["Orange"]], w[ci["Red"]])
        )
    ))
    cog = [i for i, sysn in enumerate(systems) if sysn == "Cog"]
    pool.append(Rule(
        "Green occupies the Cog socket farthest from Black.",
        lambda w, cs=cog, e=edges, ci=ci:
            w[ci["Green"]] == (cs[0] if w[ci["Black"]] == e[1] else cs[1])
    ))
    pool.append(Rule(
        "Yellow sits diametrically opposite Red and is not adjacent to it.",
        lambda w, n=n, d=diam, ci=ci: (
            _opposite(w[ci["Yellow"]], w[ci["Red"]], n, d)
            and not _adjacent(w[ci["Yellow"]], w[ci["Red"]])
        )
    ))
    pool.append(Rule(
        "Violet never neighbours Black.",
        lambda w, ci=ci: not _adjacent(w[ci["Violet"]], w[ci["Black"]])
    ))
    # optional generic pool
    for colour in CABLE_COLOURS:
        for sysn in {s for s in systems if s != "Open"}:
            pool.append(Rule(
                f"{colour} connects to {sysn}.",
                lambda w, col=colour, sn=sysn, ci=ci, s=systems:
                    s[w[ci[col]]] == sn
            ))
    return pool


class _GenErr(RuntimeError): ...


def _filter(perms: List[Tuple[int, ...]], rule: Rule):
    return [p for p in perms if rule.check(p)]


def _generate_once(board_key: str, *, min_rules: int,
                   rng: _rand.Random, ci, pool):
    board, n = BOARD_LAYOUTS[board_key], 8
    sol = list(range(n)); rng.shuffle(sol); sol_t = tuple(sol)
    compat = [r for r in pool if r.check(sol_t)]
    if len(compat) < min_rules + 1:
        raise _GenErr
    rng.shuffle(compat)
    remaining, chosen = list(_it.permutations(range(n))), []
    while len(remaining) > 1 and compat:
        best = min(compat, key=lambda r: len(_filter(remaining, r)))
        pruned = _filter(remaining, best)
        if len(pruned) == len(remaining):
            compat.remove(best); continue
        chosen.append(best); remaining = pruned; compat.remove(best)
        if len(remaining) == 1 and len(chosen) >= min_rules:
            break
    if len(remaining) != 1:
        raise _GenErr
    if len(chosen) < min_rules + 1:
        chosen.append(compat[0])
    hint = chosen.pop()
    return {"board": board, "solution": remaining[0],
            "rules": chosen, "hint": hint}


def generate_puzzle(seed=None, debug=False, *, board_key="ring‑8",
                    min_rules=5, max_attempts=300):
    rng = _rand.Random(seed)
    ci  = {c: i for i, c in enumerate(CABLE_COLOURS)}
    pool = _build_rule_templates(BOARD_LAYOUTS[board_key], ci)
    for _ in range(max_attempts):
        try:
            return _generate_once(board_key, min_rules=min_rules,
                                  rng=rng, ci=ci, pool=pool)
        except _GenErr:
            continue
    raise RuntimeError("Could not generate a unique puzzle")

# ═══════════════════════════ CLI fallback (unchanged) ════════════════════
def play_cli(puz):
    syms, systems = puz["board"]["symbols"], puz["board"]["systems"]
    rules, sol    = puz["rules"], puz["solution"]
    print("\n« CONTROL PANEL »")
    print("Symbols :", " ".join(syms))
    print("Sockets :", " ".join(str(i+1) for i in range(len(syms))))
    print("Systems :", " ".join(s[:3] for s in systems))
    print("\nRules:"); [print(" •", r.text) for r in rules]
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
            print("✓ Correct!" if tuple(placed[c] for c in CABLE_COLOURS) == sol
                  else "✗ Wrong wiring."); return
        try:
            col, pos = cmd.split(); pos = int(pos)-1
            placed[col.capitalize()] = pos
        except Exception:
            print("Bad input. Try: blue 3 / hint / done")

# ═══════════════════════════ Tk GUI with re‑flow ═════════════════════════
if tk is not None:

    _FG = lambda bg: "black" if bg.lower() in {"white", "yellow"} else "white"

    class PaletteFrame(ttk.Frame):
        """Automatically re‑flows labels whenever one leaves / returns."""
        def __init__(self, master):
            super().__init__(master)
            self.max_cols = 8

        # ---------- layout helpers ----------
        def _refresh(self):
            labels = [l for l in self.winfo_children()
                      if isinstance(l, DraggableLabel) and l.winfo_ismapped()]
            for i, lbl in enumerate(labels):
                lbl.grid_configure(row=i//self.max_cols,
                                   column=i % self.max_cols)

        def hide(self, lbl):
            lbl.grid_remove(); self._refresh()

        def show(self, lbl):
            lbl.grid(); self._refresh()

        def add_cable(self, colour: str):
            lbl = DraggableLabel(self, colour)
            lbl.grid(padx=2, pady=2)
            self._refresh()

        add = add_cable  # alias

    class DraggableLabel(ttk.Label):
        def __init__(self, palette: PaletteFrame, colour: str):
            super().__init__(palette, text=colour,
                             background=colour.lower(), foreground=_FG(colour),
                             width=8, anchor="center", relief="raised")
            self.palette, self.colour, self.socket = palette, colour, None
            self._off = (0, 0)

            # placed by palette.add_cable()

            self.bind("<ButtonPress-1>", self._start_drag)
            self.bind("<B1-Motion>",     self._drag)
            self.bind("<ButtonRelease-1>", self._drop)
            self.bind("<Double-Button-1>",
                      lambda e: self._return_to_palette())

        # ---------- drag handlers ----------
        def _start_drag(self, ev):
            if self.master is self.palette:
                self.palette.hide(self)

            # **Fix:** re-parent first, then plain place()  ───────────
            self.place_forget()
            self.master = self.winfo_toplevel()          # re-parent
            self.place(                                  # no “in_=” arg
                x=ev.x_root - self.master.winfo_rootx(),
                y=ev.y_root - self.master.winfo_rooty())
            # ─────────────────────────────────────────────────────────
            self.lift()
            self._off = (ev.x, ev.y)

        def _drag(self, ev):
            self.place_configure(x=self.winfo_x() - self._off[0] + ev.x,
                                 y=self.winfo_y() - self._off[1] + ev.y)

        def _drop(self, ev):
            tgt = self.winfo_containing(ev.x_root, ev.y_root)
            if getattr(tgt, "is_socket", False):
                self._plug_into(tgt)
            else:
                self._return_to_palette()


        # ---------- helpers ----------
        def _plug_into(self, sock):
            for ch in sock.winfo_children():
                if isinstance(ch, DraggableLabel):
                    ch._return_to_palette()
            if self.socket and self.socket is not sock:
                self._clear(self.socket)
            sock.configure(style=f"Sock.{self.colour.lower()}.TFrame")
            self.place_forget(); self.master = sock
            self.place(relx=0.5, rely=0.5, anchor="center")
            self.socket = sock

        def _return_to_palette(self):
            if self.socket:
                self._clear(self.socket); self.socket = None
            self.place_forget(); self.master = self.palette
            self.palette.show(self)

        @staticmethod
        def _clear(sock): sock.configure(style=SOCKET_EMPTY_STYLE)

    class WiringGUI(tk.Tk):
        def __init__(self, puzzle):
            super().__init__()
            self.title("40k Control‑Panel Puzzle")
            self.resizable(False, True)
            self.puzzle = puzzle
            self._register_styles(); self._build()

        def _register_styles(self):
            st = ttk.Style(self)
            st.configure(SOCKET_EMPTY_STYLE, background="#e0e0e0")
            for c in CABLE_COLOURS:
                st.configure(f"Sock.{c.lower()}.TFrame", background=c.lower())

        def _build(self):
            syms, systems = (self.puzzle["board"]["symbols"],
                             self.puzzle["board"]["systems"])
            main = ttk.Frame(self, padding=10); main.pack()
            panel = ttk.Frame(main); panel.grid(row=0, column=0, padx=(0, 20))
            rules = ttk.Frame(main); rules.grid(row=0, column=1, sticky="n")

            # sockets
            self.sockets=[]
            for i,(sym,sysn) in enumerate(zip(syms,systems)):
                cell=ttk.Frame(panel,width=60,height=90,style=SOCKET_EMPTY_STYLE)
                cell.grid(row=0,column=i,padx=2); cell.grid_propagate(False)
                ttk.Label(cell,text=sym,font=("Consolas",12,"bold")).pack()
                mid=ttk.Frame(cell,width=40,height=25,style=SOCKET_EMPTY_STYLE)
                mid.pack(pady=2); mid.is_socket=True
                mid.bind("<Button-3>",lambda e,s=mid:self._unwire(s))
                ttk.Label(cell,text=sysn,font=("Consolas",7)).pack()
                self.sockets.append(mid)

            # palette
            self.palette=PaletteFrame(panel); self.palette.grid(row=1,column=0,
                columnspan=len(syms),pady=(10,0))
            for c in CABLE_COLOURS: self.palette.add(c)

            # rules
            ttk.Label(rules,text="Magos Edicts",
                      font=("Consolas",12,"bold")).pack(anchor="w")
            for r in self.puzzle["rules"]:
                ttk.Label(rules,text="• "+r.text,wraplength=240,
                          justify="left").pack(anchor="w",pady=1)

            ttk.Button(rules,text="Hint",
                command=lambda: messagebox.showinfo("Hint",
                     self.puzzle["hint"].text)).pack(pady=(10,2))
            ttk.Button(rules,text="Check",command=self._check).pack()

        # -------- helpers --------
        def _unwire(self,s):
            for ch in s.winfo_children():
                if isinstance(ch,DraggableLabel):
                    ch._return_to_palette(); break

        def _current(self)->Tuple[int,...]:
            m=[-1]*len(CABLE_COLOURS)
            for i,s in enumerate(self.sockets):
                for ch in s.winfo_children():
                    if isinstance(ch,DraggableLabel):
                        m[CABLE_COLOURS.index(ch.colour)]=i
            return tuple(m)

        def _check(self):
            g=self._current()
            if -1 in g:
                messagebox.showwarning("Incomplete","Place all cables first!")
                return
            if g==self.puzzle["solution"]:
                messagebox.showinfo("Access Granted","Correct wiring!")
                self.destroy()
            else:
                messagebox.showerror("Access Denied","Incorrect wiring.")

# ═══════════════════════════ Entrypoint ═══════════════════════════════════
def _main():
    import argparse, sys
    ap=argparse.ArgumentParser(description="40k Control‑Panel Wiring Puzzle")
    ap.add_argument("--cli",action="store_true",
                    help="force text mode even if Tk available")
    ap.add_argument("--seed",type=int,help="repeatable PRNG seed")
    args=ap.parse_args()
    puzzle=generate_puzzle(seed=args.seed)
    if args.cli or tk is None:
        play_cli(puzzle)
    else:
        WiringGUI(puzzle).mainloop()

if __name__=="__main__":
    _main()
