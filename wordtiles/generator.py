from __future__ import annotations

import random
from dataclasses import dataclass, field

from .board import Board, Pos
from .lexicon import MAX_WORD_LEN, MIN_WORD_LEN
from .rules import GameState
from .vocab import full_lexicon, words_in_band
from .wordlists import blocked

# How often answer words of each length appear: mostly 3-6, nine almost never (as in the game).
LENGTH_WEIGHT = {3: 3.0, 4: 4.0, 5: 3.5, 6: 2.5, 7: 1.0, 8: 0.4, 9: 0.15}


VOWELS = set("AEIOU")

LETTER_FREQ = {
    "E": 12.7, "T": 9.1, "A": 8.2, "O": 7.5, "I": 7.0, "N": 6.7, "S": 6.3, "H": 6.1,
    "R": 6.0, "D": 4.3, "L": 4.0, "C": 2.8, "U": 2.8, "M": 2.4, "W": 2.4, "F": 2.2,
    "G": 2.0, "Y": 2.0, "P": 1.9, "B": 1.5, "V": 1.0, "K": 0.8, "J": 0.15, "X": 0.15,
    "Q": 0.1, "Z": 0.07,
}


@dataclass
class Level:
    seed: int
    t: float
    tiles: dict[Pos, str]
    # Certificate that the board can be cleared: the words, in play order, and the tiles
    # each one uses. It never needs the deck - the deck is help, not part of the guarantee.
    solution: list[tuple[str, list[Pos]]] = field(default_factory=list)
    deck: list[str] = field(default_factory=list)
    # How well the opponent bot plays this level, 0 (weak) .. 1 (strong).
    bot_strength: float = 0.5

    def board(self) -> Board:
        return Board(dict(self.tiles))

    def state(self) -> GameState:
        return GameState(self.board(), list(self.deck))

    def all_letters(self) -> str:
        return "".join(self.tiles.values()) + "".join(self.deck)

    def to_json(self) -> dict:
        return {
            "seed": self.seed,
            "t": round(self.t, 4),
            "tiles": [[x, y, z, ch] for (x, y, z), ch in sorted(self.tiles.items())],
            "deck": "".join(self.deck),
            "bot_strength": self.bot_strength,
            "solution": [{"word": w, "tiles": [list(p) for p in ps]} for w, ps in self.solution],
        }

    @staticmethod
    def from_json(data: dict) -> Level:
        return Level(
            seed=data["seed"],
            t=data["t"],
            tiles={(x, y, z): ch for x, y, z, ch in data["tiles"]},
            solution=[(s["word"], [tuple(p) for p in s["tiles"]]) for s in data["solution"]],
            deck=list(data.get("deck", data.get("stack", ""))),
            bot_strength=data.get("bot_strength", default_bot_strength(data["t"])),
        )


def default_bot_strength(t: float) -> float:
    """The opponent gets better as levels get harder: the main difficulty lever."""
    return round(0.9 * t, 3)


def make_deck(t: float, rng: random.Random) -> list[str]:
    """The face-down deck for a difficulty.

    Easy: eight tiles of the letters English leans on. Hard: three tiles where
    Q/X/Z/J are as likely as E - a draw that rarely rescues you. Always at least
    one vowel: a vowel-less deck (FZHTSDR, on an easy level of relaxed-03) is
    chance, not design, and it can't rescue anyone.
    """
    size = round(8 - 5 * t)
    total = sum(LETTER_FREQ.values())
    letters = list(LETTER_FREQ)
    weights = [(1 - t) * LETTER_FREQ[ch] / total + t / len(letters) for ch in letters]
    deck = rng.choices(letters, weights, k=size)
    if not any(ch in VOWELS for ch in deck):
        vowels = sorted(VOWELS)
        deck[rng.randrange(size)] = rng.choices(vowels, [LETTER_FREQ[v] for v in vowels])[0]
    return deck


def layout(t: float, rng: random.Random) -> list[Pos]:
    """Stepped pyramid: each layer inset one column from the one below.

    Big enough even at t=0 for a duel to last several turns each (a 9-tile board
    was over in two words, and its result was a coin toss).
    """
    width = round(5 + 2 * t) + rng.randint(0, 1)
    rows = 3 if t < 0.7 else 4
    layers = 1 if t < 0.15 else (2 if t < 0.75 else 3)

    positions: list[Pos] = []
    for z in range(layers):
        lo, hi = z, width - 1 - z
        if hi - lo < 1:
            break
        for y in range(rows):
            for x in range(lo, hi + 1):
                positions.append((x, y, z))
    return positions


def word_band(t: float) -> tuple[float, float]:
    """Zipf band the intended words are drawn from: very common at t=0, uncommon at t=1."""
    centre = 5.2 - 2.6 * t
    return centre - 0.6, centre + 0.6


def generate(t: float, seed: int, max_restarts: int = 40) -> Level:
    """Builds a level backwards from a guaranteed solution.

    Labels are assigned while an *unlabelled* layout is emptied in a legal
    order: at each step a word is written onto tiles that are free right
    then. Freedom depends only on which cells are occupied, never on letters,
    so replaying those words in the same order is always legal - the board
    is solvable by construction, and the order is kept as its certificate.
    """
    for restart in range(max_restarts):
        rng = random.Random(seed * 7919 + restart)
        level = _try_build(t, seed, rng)
        if level is not None:
            return level
    raise RuntimeError(f"no buildable level for t={t:.2f} seed={seed}")


def _try_build(t: float, seed: int, rng: random.Random) -> Level | None:
    remaining = set(layout(t, rng))
    if len(remaining) < MIN_WORD_LEN:
        return None
    lo, hi = word_band(t)
    banned = blocked()
    tiles: dict[Pos, str] = {}
    solution: list[tuple[str, list[Pos]]] = []

    while remaining:
        shape = Board({p: "?" for p in remaining})
        free = shape.free_tiles()
        step = _choose_step(remaining, free, t, rng)
        if step is None:
            return None
        length, chosen = step

        pool = ([w for w in words_in_band(lo, hi, length) if w not in banned]
                or [w for w in words_in_band(lo - 1.0, hi + 1.0, length) if w not in banned])
        if not pool:
            return None
        word = rng.choice(pool)
        letters = list(word)
        rng.shuffle(letters)
        for pos, ch in zip(chosen, letters):
            tiles[pos] = ch
        solution.append((word, _order_for(word, chosen, tiles)))
        remaining -= set(chosen)

    return Level(seed=seed, t=t, tiles=tiles, solution=solution, deck=make_deck(t, rng),
                 bot_strength=default_bot_strength(t))


def _choose_step(remaining: set[Pos], free: list[Pos], t: float, rng: random.Random):
    """A word length and a set of free tiles that leave the rest still emptiable."""
    left = len(remaining)
    lengths = [n for n in range(MIN_WORD_LEN, min(MAX_WORD_LEN, len(free)) + 1)
               if left - n == 0 or left - n >= MIN_WORD_LEN]
    if not lengths:
        return None
    # Mostly short words; longer ones a little more often as t rises (harder to spot).
    weights = [LENGTH_WEIGHT[n] * (1.0 + t * (n - MIN_WORD_LEN) / 3) for n in lengths]

    for _ in range(30):
        n = rng.choices(lengths, weights)[0]
        chosen = rng.sample(free, n)
        after = remaining - set(chosen)
        if not after or len(Board({p: "?" for p in after}).free_tiles()) >= MIN_WORD_LEN:
            return n, chosen
    return None


def _order_for(word: str, chosen: list[Pos], tiles: dict[Pos, str]) -> list[Pos]:
    """The chosen tiles, re-ordered to spell `word` letter by letter."""
    unused = list(chosen)
    ordered = []
    for ch in word:
        pos = next(p for p in unused if tiles[p] == ch)
        unused.remove(pos)
        ordered.append(pos)
    return ordered


def verify(level: Level) -> bool:
    """Replays the certificate; True only if every word is legal at its turn and the board empties."""
    board = level.board()
    lexicon = full_lexicon()
    for word, positions in level.solution:
        if word not in lexicon or len(set(positions)) != len(positions):
            return False
        if any(p not in board.tiles or not board.is_free(p) for p in positions):
            return False
        if board.letters_at(positions) != word:
            return False
        board.remove(positions)
    return board.is_empty()
