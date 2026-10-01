from __future__ import annotations

from dataclasses import dataclass, field

Pos = tuple[int, int, int]  # (x, y, z); z grows upward


@dataclass
class Board:
    """Mahjong-solitaire layout of letter tiles.

    A tile is *visible* when nothing sits directly on top of it, and *free*
    (usable in a word) when it is visible and at least one of its left/right
    neighbours on the same layer is empty. Visible-but-blocked tiles are
    information a real player has; covered tiles are not, and a fair bot
    must not read them.
    """

    tiles: dict[Pos, str] = field(default_factory=dict)

    def is_visible(self, pos: Pos) -> bool:
        x, y, z = pos
        return (x, y, z + 1) not in self.tiles

    def is_free(self, pos: Pos) -> bool:
        if not self.is_visible(pos):
            return False
        x, y, z = pos
        return (x - 1, y, z) not in self.tiles or (x + 1, y, z) not in self.tiles

    def free_tiles(self) -> list[Pos]:
        return [p for p in self.tiles if self.is_free(p)]

    def visible_tiles(self) -> list[Pos]:
        return [p for p in self.tiles if self.is_visible(p)]

    def letters_at(self, positions: list[Pos]) -> str:
        return "".join(self.tiles[p] for p in positions)

    def remove(self, positions: list[Pos]) -> None:
        for p in positions:
            del self.tiles[p]

    def clone(self) -> Board:
        return Board(dict(self.tiles))

    def is_empty(self) -> bool:
        return not self.tiles

    def __len__(self) -> int:
        return len(self.tiles)
