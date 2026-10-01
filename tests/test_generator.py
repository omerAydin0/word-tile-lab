import random

import pytest

from wordtiles.bots import CasualPlayer, ExpertPlayer, OpponentBot, play_duel
from wordtiles.generator import Level, generate, verify
from wordtiles.lexicon import MAX_WORD_LEN
from wordtiles.wordlists import blocked


@pytest.mark.parametrize("t", [0.0, 0.3, 0.6, 1.0])
def test_every_generated_board_replays_its_own_certificate(t):
    for seed in range(15):
        level = generate(t, seed)
        assert verify(level)
        assert all(len(w) <= MAX_WORD_LEN for w, _ in level.solution)


def test_generation_is_deterministic_per_seed():
    assert generate(0.5, 7).to_json() == generate(0.5, 7).to_json()


def test_tampered_certificate_fails_verification():
    level = generate(0.5, 3)
    word, positions = level.solution[0]
    level.solution[0] = (word, list(reversed(positions)))
    assert word == word[::-1] or not verify(level)


def test_json_round_trip():
    level = generate(0.8, 11)
    assert Level.from_json(level.to_json()).to_json() == level.to_json()


def test_harder_levels_get_a_stronger_bot_and_a_less_helpful_deck():
    easy, hard = generate(0.0, 1), generate(1.0, 1)
    assert len(easy.deck) > len(hard.deck) and easy.bot_strength < hard.bot_strength


def test_the_bot_never_knows_a_blocked_word():
    banned = set(blocked())
    for strength in (0.0, 0.5, 1.0):
        assert not banned & set(OpponentBot(strength).lexicon.words)


@pytest.mark.parametrize("player", [CasualPlayer(), ExpertPlayer()])
def test_a_duel_ends_and_the_human_moves_first(player):
    level = generate(0.4, 2)
    duel = play_duel(level, player, OpponentBot(level.bot_strength), random.Random(0))
    assert duel.moves and duel.moves[0][0] == 0
    assert duel.board_cleared or [m for _, m in duel.moves[-2:]] == ["pass", "pass"]
    assert sum(duel.scores) > 0


def test_render_shows_a_duel_move_by_move_with_the_running_score():
    from wordtiles.render import to_html
    level = generate(0.4, 2)
    duel = play_duel(level, CasualPlayer(), OpponentBot(level.bot_strength), random.Random(0))
    page = to_html(level, "x", True, duel, "Sample duel")
    p, b = duel.scores
    assert "Sample duel" in page and f"{p}&ndash;{b}" in page
    assert page.count('<tr class="') == len(duel.moves)
