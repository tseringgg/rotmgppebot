"""Reusable button wiring for season loot variant menus."""

from __future__ import annotations

import discord

from menus.menu_utils.base_views import OwnerBoundView
from menus.menu_utils.loot_image_variants import (
    ALL_LOOT,
    NORMAL_LIMITED,
    NORMAL_ONLY,
    NORMAL_SKINS,
    LootImageVariant,
)


class SeasonLootVariantActionsView(OwnerBoundView):
    """Common season loot variant controls shared by user/admin menus."""

    def __init__(self, *, owner_id: int, title: str, timeout: float | None = 600) -> None:
        super().__init__(owner_id=owner_id, timeout=timeout, owner_error="This menu belongs to another user.")
        self._title = title

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title=self._title,
            description="Choose an action.",
            color=discord.Color.gold(),
        )

    async def _close_and_share(
        self,
        interaction: discord.Interaction,
        *,
        include_skins: bool,
        include_limited: bool,
    ) -> None:
        raise NotImplementedError

    async def _list_season_loot(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError

    async def _show_statistics(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError

    async def _show_item_graph(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError

    async def _share_variant(self, interaction: discord.Interaction, variant: LootImageVariant) -> None:
        await self._close_and_share(
            interaction,
            include_skins=variant.include_skins,
            include_limited=variant.include_limited,
        )

    @discord.ui.button(label=NORMAL_ONLY.label, style=discord.ButtonStyle.primary, row=0)
    async def normal_only(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._share_variant(interaction, NORMAL_ONLY)

    @discord.ui.button(label=NORMAL_LIMITED.label, style=discord.ButtonStyle.primary, row=0)
    async def normal_limited(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._share_variant(interaction, NORMAL_LIMITED)

    @discord.ui.button(label=NORMAL_SKINS.label, style=discord.ButtonStyle.primary, row=1)
    async def normal_skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._share_variant(interaction, NORMAL_SKINS)

    @discord.ui.button(label=ALL_LOOT.label, style=discord.ButtonStyle.primary, row=1)
    async def all_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._share_variant(interaction, ALL_LOOT)

    @discord.ui.button(label="List Loot", style=discord.ButtonStyle.primary, row=1)
    async def list_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._list_season_loot(interaction)

    @discord.ui.button(label="Show Statistics", style=discord.ButtonStyle.success, row=2)
    async def show_statistics(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._show_statistics(interaction)

    @discord.ui.button(label="Item Graph", style=discord.ButtonStyle.success, row=2)
    async def item_graph(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._show_item_graph(interaction)
