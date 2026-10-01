"""The rules of a turn-based word-tile duel, as Word Tiles GO's level mode plays.

Two players share one Mahjong-style board; the human always moves first. On a
turn you spell a word of 3-9 letters (the word tray holds nine) from free tiles,
optionally using the open tile of the face-down deck, and score by its length.
When no word can be made you turn the next deck tile face up - only the most
recently opened tile is usable, as in solitaire's waste pile. With no word and
no deck left you pass. The game ends when the board is empty (or both players
pass in a row); the higher score wins.

Observed in the game: shared board, human first, 9-tile tray, length-based
score, no timer, covered letters hidden, a face-down deck where only the top
open tile counts. Assumed (not observed): the points table, that drawing does
not end the turn, that the deck is shared, and that the open tile underneath
becomes usable again once the top one is spent.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from .board import Board, Pos
from .lexicon import MAX_WORD_LEN, Lexicon

POINTS = {3: 3, 4: 5, 5: 8, 6: 12, 7: 17, 8: 23, 9: 30}

# Chooses which of several free tiles carrying the same letter to spend.
TilePicker = Callable[[Board, str, list[Pos]], Pos]


@dataclass
class GameState:
    board: Board
    deck: list[str] = field(default_factory=list)    # face down; the next draw comes first
    waste: list[str] = field(default_factory=list)   # opened deck tiles; only the last is usable
    scores: list[int] = field(default_factory=lambda: [0, 0])
    to_move: int = 0                                 # 0 = the human, who always starts
    passes: int = 0

    def clone(self) -> GameState:
        return GameState(self.board.clone(), list(self.deck), list(self.waste),
                         list(self.scores), self.to_move, self.passes)

    def free_letters(self) -> list[str]:
        return [self.board.tiles[p] for p in self.board.free_tiles()]

    def open_tile(self) -> str | None:
        return self.waste[-1] if self.waste else None

    def options(self, lexicon: Lexicon) -> list[str]:
        extra = [self.waste[-1]] if self.waste else []
        return [w for w in lexicon.spellable_using(self.free_letters(), extra) if len(w) <= MAX_WORD_LEN]

    def draw(self) -> str:
        letter = self.deck.pop(0)
        self.waste.append(letter)
        return letter

    def play(self, word: str, pick: TilePicker) -> list[Pos]:
        """Spends free board tiles first; the open deck tile covers at most one missing letter."""
        free = free_letters(self.board)
        used_open = False
        from_board: list[Pos] = []
        for letter, count in Counter(word).items():
            candidates = list(free.get(letter, []))
            take = min(count, len(candidates))
            for _ in range(take):
                pos = pick(self.board, letter, candidates)
                candidates.remove(pos)
                from_board.append(pos)
            missing = count - take
            if missing:
                if missing == 1 and not used_open and self.open_tile() == letter:
                    used_open = True
                else:
                    raise ValueError(f"{word!r} cannot be spelled from the free tiles and open tile")
        if len(word) > MAX_WORD_LEN:
            raise ValueError(f"{word!r} does not fit the {MAX_WORD_LEN}-tile tray")
        self.board.remove(from_board)
        if used_open:
            self.waste.pop()
        self.scores[self.to_move] += POINTS[len(word)]
        self.passes = 0
        self.to_move ^= 1
        return from_board

    def pass_turn(self) -> None:
        self.passes += 1
        self.to_move ^= 1

    def over(self) -> bool:
        return self.board.is_empty() or self.passes >= 2


def free_letters(board: Board) -> dict[str, list[Pos]]:
    by_letter: dict[str, list[Pos]] = defaultdict(list)
    for pos in board.free_tiles():
        by_letter[board.tiles[pos]].append(pos)
    return by_letter


def random_picker(rng: random.Random) -> TilePicker:
    return lambda _board, _letter, candidates: rng.choice(candidates)


def unblocking_picker(rng: random.Random) -> TilePicker:
    """Spends the tile whose removal frees the most others; ties at random."""
    def pick(board: Board, _letter: str, candidates: list[Pos]) -> Pos:
        return max(candidates, key=lambda p: (tiles_freed_by(board, p), rng.random()))
    return pick


def tiles_freed_by(board: Board, pos: Pos) -> int:
    before = set(board.free_tiles())
    trial = board.clone()
    trial.remove([pos])
    return len(set(trial.free_tiles()) - before)
