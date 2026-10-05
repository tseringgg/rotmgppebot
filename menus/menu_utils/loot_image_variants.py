"""Single source of truth for the loot image "Show Image" button variants."""

from __future__ import annotations

from typing import NamedTuple

from utils.loot_helpers.shareloot_image import VARIANT_DISPLAY_NAMES, variant_from_flags


class LootImageVariant(NamedTuple):
    label: str
    include_skins: bool
    include_limited: bool

    @property
    def display_name(self) -> str:
        """Human-readable variant name (e.g. "Normal + Skins loot"), used for logging."""
        return VARIANT_DISPLAY_NAMES[variant_from_flags(self.include_skins, self.include_limited)]


NORMAL_ONLY = LootImageVariant("Show Image: Normal Only", include_skins=False, include_limited=False)
NORMAL_LIMITED = LootImageVariant("Show Image: Normal + Limited", include_skins=False, include_limited=True)
NORMAL_SKINS = LootImageVariant("Show Image: Normal + Skins", include_skins=True, include_limited=False)
ALL_LOOT = LootImageVariant("Show Image: All Loot", include_skins=True, include_limited=True)

LOOT_IMAGE_VARIANTS: tuple[LootImageVariant, ...] = (NORMAL_ONLY, NORMAL_LIMITED, NORMAL_SKINS, ALL_LOOT)


__all__ = [
    "ALL_LOOT",
    "LOOT_IMAGE_VARIANTS",
    "LootImageVariant",
    "NORMAL_LIMITED",
    "NORMAL_ONLY",
    "NORMAL_SKINS",
]
