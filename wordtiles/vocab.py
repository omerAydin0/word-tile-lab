from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .lexicon import MAX_WORD_LEN, MIN_WORD_LEN, Lexicon

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ENABLE_PATH = DATA_DIR / "enable1.txt"
# Derived from wordfreq (CC BY-SA data): a local cache, never committed.
ZIPF_CACHE = DATA_DIR / ".cache" / "zipf.tsv"


@lru_cache(maxsize=1)
def enable_words() -> tuple[str, ...]:
    words = ENABLE_PATH.read_text(encoding="ascii").split()
    return tuple(w.upper() for w in words if MIN_WORD_LEN <= len(w) <= MAX_WORD_LEN)


@lru_cache(maxsize=1)
def zipf_table() -> dict[str, float]:
    if ZIPF_CACHE.exists():
        table = {}
        for line in ZIPF_CACHE.read_text(encoding="ascii").splitlines():
            word, z = line.split("\t")
            table[word] = float(z)
        return table

    from wordfreq import zipf_frequency

    table = {w: zipf_frequency(w.lower(), "en") for w in enable_words()}
    ZIPF_CACHE.parent.mkdir(parents=True, exist_ok=True)
    ZIPF_CACHE.write_text("".join(f"{w}\t{z}\n" for w, z in table.items()), encoding="ascii")
    return table


def zipf(word: str) -> float:
    return zipf_table().get(word.upper(), 0.0)


@lru_cache(maxsize=1)
def full_lexicon() -> Lexicon:
    """Every ENABLE word: what the game accepts."""
    return Lexicon(enable_words())


@lru_cache(maxsize=256)
def accepted_for(letters: str) -> Lexicon:
    """Accepted words a given level's letters could ever spell (cached per level)."""
    return full_lexicon().restrict(letters)


@lru_cache(maxsize=16)
def known_lexicon(min_zipf: float, max_len: int) -> Lexicon:
    """Words a player of a given vocabulary would think of: common enough and short enough."""
    table = zipf_table()
    return Lexicon(w for w in enable_words() if table[w] >= min_zipf and len(w) <= max_len)


@lru_cache(maxsize=4096)
def words_in_band(lo: float, hi: float, length: int) -> tuple[str, ...]:
    table = zipf_table()
    return tuple(w for w in enable_words() if len(w) == length and lo <= table[w] < hi)
