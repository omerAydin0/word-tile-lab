from __future__ import annotations

from collections.abc import Iterable

import numpy as np

MIN_WORD_LEN = 3
# The word tray holds nine tiles, so nothing longer can be played.
MAX_WORD_LEN = 9
_A = ord("A")


def letter_vector(letters: Iterable[str]) -> np.ndarray:
    vec = np.zeros(26, dtype=np.int16)
    for ch in letters:
        vec[ord(ch) - _A] += 1
    return vec


def letter_mask(letters: Iterable[str]) -> int:
    mask = 0
    for ch in letters:
        mask |= 1 << (ord(ch) - _A)
    return mask


class Lexicon:
    """A word list indexed for "which words can these letters spell".

    That question is asked at every move of every simulated playthrough. Two
    stages answer it: a bitmask of each word's distinct letters discards, in one
    integer operation, every word using a letter that isn't available at all
    (most of them); only the survivors get the exact letter-count comparison.
    `restrict` cuts the list down to words a given level could ever spell.
    """

    def __init__(self, words: Iterable[str], min_len: int = MIN_WORD_LEN):
        cleaned = sorted({
            w.strip().upper() for w in words
            if len(w.strip()) >= min_len and w.strip().isascii() and w.strip().isalpha()
        })
        self._set(cleaned,
                  np.array([letter_vector(w) for w in cleaned], dtype=np.int16)
                  if cleaned else np.zeros((0, 26), dtype=np.int16))

    def _set(self, words: list[str], counts: np.ndarray) -> None:
        self.words = words
        self.counts = counts
        self.masks = np.array([letter_mask(w) for w in words], dtype=np.int64)
        self._index = {w: i for i, w in enumerate(words)}

    def __contains__(self, word: str) -> bool:
        return word.upper() in self._index

    def __len__(self) -> int:
        return len(self.words)

    def _within(self, available: np.ndarray) -> np.ndarray:
        avail_mask = int(np.dot(available > 0, 1 << np.arange(26, dtype=np.int64)))
        cand = np.flatnonzero((self.masks & ~avail_mask) == 0)
        if cand.size:
            cand = cand[np.all(self.counts[cand] <= available, axis=1)]
        return cand

    def spellable(self, letters: Iterable[str]) -> list[str]:
        return [self.words[i] for i in self._within(letter_vector(letters))]

    def spellable_using(self, board_letters: Iterable[str], hand_letters: Iterable[str]) -> list[str]:
        """Words spellable from board + hand that take at least one board tile.

        Board tiles are spent first, so a word takes a board tile exactly when it
        shares a letter with the free tiles - even if the hand alone could spell it.
        """
        board = list(board_letters)
        cand = self._within(letter_vector(board) + letter_vector(hand_letters))
        if cand.size:
            cand = cand[(self.masks[cand] & letter_mask(board)) != 0]
        return [self.words[i] for i in cand]

    def restrict(self, letters: Iterable[str]) -> Lexicon:
        idx = self._within(letter_vector(letters))
        sub = Lexicon.__new__(Lexicon)
        sub._set([self.words[i] for i in idx], self.counts[idx])
        return sub
