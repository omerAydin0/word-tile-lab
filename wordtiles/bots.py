"""Players, and the duel between the human (always first) and the level's opponent bot.

Every policy plays by the same rules and sees only what a player sees: free
tiles and the open deck tile. A bot that reads covered tiles or the face-down
deck measures a game nobody plays.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .generator import Level
from .lexicon import Lexicon
from .rules import POINTS, GameState, TilePicker, random_picker, unblocking_picker
from .vocab import accepted_for, full_lexicon, known_lexicon, zipf_table
from .wordlists import blocked

# A casual player: thinks of words they actually use, usually three to six letters.
CASUAL_MIN_ZIPF = 3.5
CASUAL_MAX_LEN = 6


class Player:
    lexicon: Lexicon

    def vocab_for(self, letters: str) -> Lexicon:
        if self.lexicon is full_lexicon():
            return accepted_for(letters)
        return self.lexicon.restrict(letters)

    def choose_word(self, state: GameState, options: list[str], rng: random.Random) -> str:
        raise NotImplementedError

    def picker(self, rng: random.Random) -> TilePicker:
        raise NotImplementedError


class CasualPlayer(Player):
    """Grabs a word it notices - common words more often, longer ones a little more
    (it knows they score) - and spends tiles without planning ahead."""

    def __init__(self, min_zipf: float = CASUAL_MIN_ZIPF, max_len: int = CASUAL_MAX_LEN):
        self.lexicon = known_lexicon(min_zipf, max_len)
        self._zipf = zipf_table()

    def choose_word(self, state, options, rng):
        weights = [max(self._zipf[w] - 2.0, 0.1) * POINTS[len(w)] ** 0.5 for w in options]
        return rng.choices(options, weights)[0]

    def picker(self, rng):
        return random_picker(rng)


class OpponentBot(Player):
    """The level's opponent. Strength 0..1 widens its vocabulary (rarer and longer words)
    and makes it more likely to take the highest-scoring word it can see."""

    def __init__(self, strength: float):
        self.strength = max(0.0, min(1.0, strength))
        # The bot's words appear on the player's screen too, so blocked words are off its list.
        known = known_lexicon(round(4.8 - 2.2 * self.strength, 2), min(9, 4 + round(5 * self.strength)))
        banned = blocked()
        self.lexicon = Lexicon(w for w in known.words if w not in banned) if banned else known
        self._zipf = zipf_table()

    def choose_word(self, state, options, rng):
        if rng.random() < 0.1 + 0.8 * self.strength:
            best = max(POINTS[len(w)] for w in options)
            options = [w for w in options if POINTS[len(w)] == best]
        weights = [max(self._zipf[w] - 2.0, 0.1) for w in options]
        return rng.choices(options, weights)[0]

    def picker(self, rng):
        return random_picker(rng)


class ExpertPlayer(Player):
    """Knows every accepted word, always takes the highest score, and spends whichever
    duplicate tile opens the board most. Used as a fairness check, not as difficulty."""

    def __init__(self):
        self.lexicon = full_lexicon()

    def choose_word(self, state, options, rng):
        best = max(POINTS[len(w)] for w in options)
        return rng.choice([w for w in options if POINTS[len(w)] == best])

    def picker(self, rng):
        return unblocking_picker(rng)


@dataclass
class Duel:
    scores: tuple[int, int]
    moves: list[tuple[int, str]] = field(default_factory=list)   # (player, word | "draw X" | "pass")
    board_cleared: bool = False
    # The human passed while the board + open tile DID spell an accepted word: a vocabulary wall.
    vocabulary_walls: int = 0
    stuck_letters: str = ""

    @property
    def won(self) -> bool:
        return self.scores[0] > self.scores[1]

    @property
    def tie(self) -> bool:
        return self.scores[0] == self.scores[1]


def play_duel(level: Level, human: Player, opponent: Player, rng: random.Random) -> Duel:
    letters = level.all_letters()
    players = (human, opponent)
    vocabs = (human.vocab_for(letters), opponent.vocab_for(letters))
    pickers = (human.picker(rng), opponent.picker(rng))
    accepted = accepted_for(letters)
    state = level.state()
    duel = Duel(scores=(0, 0))

    while not state.over():
        me = state.to_move
        while True:
            options = state.options(vocabs[me])
            if options:
                word = players[me].choose_word(state, options, rng)
                state.play(word, pickers[me])
                duel.moves.append((me, word))
                break
            if state.deck:
                duel.moves.append((me, f"draw {state.draw()}"))
                continue
            if me == 0:
                if state.options(accepted):
                    duel.vocabulary_walls += 1
                duel.stuck_letters = "".join(sorted(state.free_letters()))
            state.pass_turn()
            duel.moves.append((me, "pass"))
            break

    duel.scores = (state.scores[0], state.scores[1])
    duel.board_cleared = state.board.is_empty()
    return duel
