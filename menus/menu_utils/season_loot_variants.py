"""Reusable button wiring for season loot variant menus."""

from __future__ import annotations

import discord

from menus.menu_utils.base_views import OwnerBoundView


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

    @discord.ui.button(label="Show Image: Normal Only", style=discord.ButtonStyle.primary, row=0)
    async def normal_only(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=False)

    @discord.ui.button(label="Show Image: Normal + Limited", style=discord.ButtonStyle.primary, row=0)
    async def normal_limited(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=True)

    @discord.ui.button(label="Show Image: Normal + Skins", style=discord.ButtonStyle.primary, row=1)
    async def normal_skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=False)

    @discord.ui.button(label="Show Image: All Loot", style=discord.ButtonStyle.primary, row=1)
    async def all_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=True)

    @discord.ui.button(label="List Loot", style=discord.ButtonStyle.primary, row=1)
    async def list_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._list_season_loot(interaction)

    @discord.ui.button(label="Show Statistics", style=discord.ButtonStyle.success, row=2)
    async def show_statistics(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._show_statistics(interaction)
