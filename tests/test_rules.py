import random

import pytest

from wordtiles.board import Board
from wordtiles.lexicon import Lexicon
from wordtiles.rules import POINTS, GameState, random_picker, unblocking_picker

LEX = Lexicon(["COG", "COT", "DOG", "CAT", "ACT", "TAD", "AT", "CATS", "COAT"])
PICK = random_picker(random.Random(0))


def small_board() -> Board:
    #  z=1:      G
    #  z=0:  C  A  T  D  O
    tiles = {(x, 0, 0): ch for x, ch in enumerate("CATDO")}
    tiles[(1, 0, 1)] = "G"
    return Board(tiles)


def test_free_needs_open_top_and_an_open_side():
    assert set(small_board().free_tiles()) == {(0, 0, 0), (4, 0, 0), (1, 0, 1)}


def test_covered_tile_is_not_visible_but_side_blocked_one_is():
    board = small_board()
    visible = set(board.visible_tiles())
    assert (1, 0, 0) not in visible
    assert (2, 0, 0) in visible and (2, 0, 0) not in board.free_tiles()


def test_short_words_are_not_in_the_lexicon():
    assert "AT" not in LEX and "CAT" in LEX


def test_options_use_only_free_letters_without_an_open_deck_tile():
    assert GameState(small_board()).options(LEX) == ["COG"]


def test_a_word_scores_by_length_and_passes_the_turn():
    state = GameState(small_board())
    state.play("COG", PICK)
    assert state.scores == [POINTS[3], 0] and state.to_move == 1
    assert set(state.board.free_tiles()) == {(1, 0, 0), (3, 0, 0)}


def test_longer_words_always_score_more():
    lengths = sorted(POINTS)
    assert lengths == list(range(3, 10))
    assert all(POINTS[a] < POINTS[b] for a, b in zip(lengths, lengths[1:]))


def test_only_the_last_opened_deck_tile_is_usable():
    state = GameState(small_board(), deck=list("TX"))
    state.draw()
    assert "COT" in state.options(LEX)
    state.draw()                                  # X now covers the T
    assert "COT" not in state.options(LEX)


def test_spending_the_open_tile_uncovers_the_one_below():
    state = GameState(small_board(), deck=list("AT"))
    state.draw(); state.draw()                    # waste: A, then T on top
    state.play("COT", PICK)                       # C, O from the board, T from the deck
    assert state.open_tile() == "A"


def test_drawing_does_not_end_the_turn():
    state = GameState(small_board(), deck=list("Q"))
    state.draw()
    assert state.to_move == 0


def test_the_open_tile_covers_at_most_one_missing_letter():
    board = Board({(0, 0, 0): "C", (5, 0, 0): "Q"})
    state = GameState(board, deck=list("AT"))
    state.draw(); state.draw()
    assert "CAT" not in state.options(LEX)        # needs both A and T from the deck


def test_board_tiles_are_spent_before_the_open_tile():
    state = GameState(Board({(0, 0, 0): "C", (5, 0, 0): "A", (9, 0, 0): "T"}), deck=list("T"))
    state.draw()
    state.play("CAT", PICK)
    assert state.board.is_empty() and state.open_tile() == "T"


def test_words_longer_than_the_tray_are_never_options():
    long_lex = Lexicon(["ABCDEFGHIJ"])
    board = Board({(i * 2, 0, 0): ch for i, ch in enumerate("ABCDEFGHIJ")})
    assert GameState(board).options(long_lex) == []


def test_game_ends_on_empty_board_or_two_passes_in_a_row():
    state = GameState(small_board())
    state.pass_turn()
    assert not state.over()
    state.pass_turn()
    assert state.over()


def test_unspellable_word_is_rejected():
    with pytest.raises(ValueError):
        GameState(small_board()).play("DOG", PICK)


def test_unblocking_picker_spends_the_tile_that_opens_the_board():
    board = Board({(0, 0, 0): "A", (0, 0, 1): "T", (3, 0, 0): "T", (5, 0, 0): "C"})
    picker = unblocking_picker(random.Random(0))
    assert picker(board, "T", [(0, 0, 1), (3, 0, 0)]) == (0, 0, 1)


def test_restrict_keeps_only_words_the_letters_could_spell():
    assert set(LEX.restrict("CATDOG").words) == {"COG", "COT", "DOG", "CAT", "ACT", "TAD", "COAT"}
    assert LEX.restrict("CAT").words == ["ACT", "CAT"]
