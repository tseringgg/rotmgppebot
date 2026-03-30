"""Shared carousel helpers for character-based menu views."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


def select_initial_index(ppes: Sequence, preferred_ppe_id: int | None, fallback_active_ppe: int | None) -> int:
    target_id = preferred_ppe_id if preferred_ppe_id is not None else fallback_active_ppe
    for idx, ppe in enumerate(ppes):
        if int(ppe.id) == int(target_id or -1):
            return idx
    return 0


def cycle_index(index: int, *, total: int, step: int) -> int:
    if total <= 0:
        return 0
    return (index + step) % total


@dataclass(frozen=True)
class CharacterCarouselPolicy:
    """Policy hooks for shared character carousel start/cycle behavior."""

    preferred_ppe_id: int | None
    active_ppe_id: int | None

    def initial_index(self, ppes: Sequence) -> int:
        return select_initial_index(ppes, self.preferred_ppe_id, self.active_ppe_id)

    def next_index(self, index: int, *, total: int, step: int) -> int:
        return cycle_index(index, total=total, step=step)
