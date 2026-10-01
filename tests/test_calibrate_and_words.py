import pytest

from wordtiles import wordlists
from wordtiles.calibrate import TARGET_FLOOR, initial_t, target_range


def test_default_curve_and_chapter_drop():
    assert target_range(1) == pytest.approx((0.80, 1.00))
    assert target_range(11) == pytest.approx((0.73, 0.93))      # one chapter later: 0.07 harder
    assert target_range(10)[0] == 0.0                          # 0.06 - 0.10 clamps at zero


def test_late_chapters_never_target_below_the_floor():
    lo, hi = target_range(10 + 10 * 9)
    assert hi == pytest.approx(TARGET_FLOOR + 0.10)


def test_custom_targets_move_the_band_and_the_starting_guess():
    gentle = [0.95, 0.9, 0.85, 0.8, 0.6, 0.85, 0.75, 0.65, 0.5, 0.4]
    assert target_range(10, gentle) == pytest.approx((0.30, 0.50))
    assert initial_t(1, gentle) < initial_t(10, gentle)


@pytest.fixture
def lists(tmp_path, monkeypatch):
    monkeypatch.setattr(wordlists, "BLOCKED_PATH", tmp_path / "blocked.tsv")
    monkeypatch.setattr(wordlists, "APPROVED_PATH", tmp_path / "approved.tsv")


def test_word_decisions_are_recorded_and_a_later_one_wins(lists):
    assert wordlists.status("cat") == "unreviewed"
    wordlists.record(["cat", "dog"], "approve", "fine")
    assert wordlists.status("CAT") == "approved"
    wordlists.record(["dog"], "block", "test")
    assert wordlists.status("dog") == "blocked" and "DOG" not in wordlists.approved()


def test_unknown_decision_is_rejected(lists):
    with pytest.raises(ValueError):
        wordlists.record(["cat"], "maybe", "")
