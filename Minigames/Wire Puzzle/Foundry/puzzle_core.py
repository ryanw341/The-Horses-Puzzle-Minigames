#!/usr/bin/env python3
"""
40k Control‑Panel Wiring Puzzle — core logic (v13.4-web)
========================================================
Pure-Python core (no Tkinter) suitable for running under Pyodide/PyScript or
importing server-side. Contains:

• Rule/datamodel + fast unique-rule subset solver
• generate_puzzle() → full puzzle dict (including Rule objects)
• get_puzzle()      → JSON-serialisable snapshot for the browser
• check_solution()  → validate a player's guess

Differences vs your original wire_puzzle6.py:
--------------------------------------------
1. All Tkinter GUI code and CLI loop removed.
2. Added JSON-friendly helpers (get_puzzle, serialise_rule_texts).
3. Kept logic 1:1 so behaviour/solutions match desktop version.

You can import this from JS via Pyodide and call get_puzzle()/check_solution().

Usage (Pyodide example):
------------------------
>>> from puzzle_core import get_puzzle, check_solution
>>> puz = get_puzzle(seed=42, min_rules=5)
>>> check_solution(puz, [0,1,2,3,4,5])
False

Author : ChatGPT (OpenAI o3)
Date   : 2025-07-23
"""
from __future__ import annotations

import itertools as _it
import random as _rand
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Set, Tuple, Optional, Any

# ──────────────────────────────── Constants ────────────────────────────────
CABLE_COLOURS: List[str] = ["Black", "Blue", "White", "Red", "Orange", "Green"]

BOARD_LAYOUTS: Dict[str, Dict[str, Any]] = {
    "ring-6": {
        "symbols":   ["Δ", "Ω", "Σ", "Φ", "Ψ", "Θ"],
        "systems":   ["Shield", "Cog", "Gravitas", "Open", "Cog", "Gravitas"],
        "edges":     (0, 5),       # indices counted from 0
        "diametric": 3,            # offset to the opposite socket on ring
    },
}

# ────────────────────────────── Helper predicates ──────────────────────────
_left_of   = lambda a, b: a + 1 == b
_wrap_adj  = lambda a, b, n: abs(a - b) in (1, n - 1)


def _ring_dist(a: int, b: int, n: int) -> int:
    """Shortest distance clockwise/counter-clockwise on a ring of size n."""
    d = abs(a - b)
    return min(d, n - d)

# ───────────────────────────────── Data model ──────────────────────────────
@dataclass(frozen=True)
class Rule:
    text: str
    func: Callable[[Tuple[int, ...]], bool]

    def __call__(self, wiring: Tuple[int, ...]) -> bool:
        return self.func(wiring)


# ───────────────────────────── Rule pool builder ───────────────────────────
def _build_rule_pool(board: Dict[str, Any], ci: Dict[str, int], rng: _rand.Random) -> List[Rule]:
    syms, systems   = board["symbols"], board["systems"]
    edges, diam_off = board["edges"], board["diametric"]
    n               = len(syms)
    P: List[Rule]   = []

    # Always-useful anchor rule (Black on an edge)
    P.append(Rule(
        f"Black occupies an edge socket ({syms[edges[0]]} or {syms[edges[1]]}).",
        lambda w, e=edges, c=ci["Black"]: w[c] in e
    ))

    # Random colours for Shield vs Gravitas constraints (not Black)
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

    # Green farthest Cog from Black (constant rule)
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

# ───────────────────────────── Permutation cache/solver ────────────────────
_PERM_CACHE: Dict[int, List[Tuple[int, ...]]] = {}


def _perms(n: int) -> List[Tuple[int, ...]]:
    if n not in _PERM_CACHE:
        _PERM_CACHE[n] = list(_it.permutations(range(n)))
    return _PERM_CACHE[n]


class _NoPuzzle(RuntimeError):
    pass


def _precompute_rule_sets(rules: Sequence[Rule], perms: Sequence[Tuple[int, ...]]) -> List[Set[int]]:
    return [{i for i, p in enumerate(perms) if r(p)} for r in rules]


def _unique_subset(sol_idx: int, compat: Sequence[int], rule_sets: List[Set[int]], total: int) -> Optional[List[int]]:
    """Greedy smallest-first set cover that isolates the solution uniquely."""
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
                min_rules: int, rng: _rand.Random, total: int) -> Optional[Tuple[List[int], Optional[int]]]:
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
    hint_idx: Optional[int] = rng.choice(extras) if extras else None
    return sorted(visible), hint_idx


# ───────────────────────────── Public puzzle API ───────────────────────────
def generate_puzzle(*, seed: Optional[int] = None, board_key: str = "ring-6",
                     min_rules: int = 5, max_checks: Optional[int] = None) -> Dict[str, Any]:
    """Generate a full puzzle dict containing live Rule objects.

    Returns keys: board, solution (tuple), rules (List[Rule]), hint (Rule|None)
    """
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


def serialise_puzzle(puz: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe copy: Rule objects become their text."""
    return {
        "board": puz["board"],
        "solution": list(puz["solution"]),   # list for JSON
        "rules": [r.text for r in puz["rules"]],
        "hint": (puz["hint"].text if puz["hint"] is not None else None)
    }


def get_puzzle(*, seed: Optional[int] = None, board_key: str = "ring-6",
               min_rules: int = 5, max_checks: Optional[int] = None) -> Dict[str, Any]:
    """Convenience: generate and immediately serialise to JSON-safe dict."""
    return serialise_puzzle(
        generate_puzzle(seed=seed, board_key=board_key, min_rules=min_rules, max_checks=max_checks)
    )


def check_solution(puz_or_serial: Dict[str, Any], guess: Sequence[int]) -> bool:
    """Validate a player's guess.

    Parameters
    ----------
    puz_or_serial : dict
        Either the raw puzzle dict from generate_puzzle() *or* the serialised
        one from get_puzzle(). Needs keys 'solution'.
    guess : Sequence[int]
        A list/tuple of length len(CABLE_COLOURS), index i giving the socket
        index for colour CABLE_COLOURS[i].
    """
    sol = puz_or_serial["solution"]
    # tuple vs list agnostic compare
    return list(sol) == list(guess)


__all__ = [
    "CABLE_COLOURS",
    "BOARD_LAYOUTS",
    "Rule",
    "generate_puzzle",
    "get_puzzle",
    "serialise_puzzle",
    "check_solution",
    "_NoPuzzle",
]

