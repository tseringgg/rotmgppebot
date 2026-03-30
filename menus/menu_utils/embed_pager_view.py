"""Reusable owner-bound embed pager view."""

from __future__ import annotations

import discord

from menus.menu_utils.base_views import OwnerBoundView
from menus.menu_utils.character_carousel import cycle_index


class OwnerBoundEmbedPagerView(OwnerBoundView):
    """Owner-bound embed pager with shared Prev/Next controls."""

    def __init__(self, *, owner_id: int, embeds: list[discord.Embed], timeout: float | None = 600) -> None:
        super().__init__(owner_id=owner_id, timeout=timeout, owner_error="This menu belongs to another user.")
        self.embeds = embeds
        self.index = 0

        if len(self.embeds) <= 1:
            self.remove_item(self.prev_page)
            self.remove_item(self.next_page)

    def current_embed(self) -> discord.Embed:
        return self.embeds[self.index]

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = cycle_index(self.index, total=len(self.embeds), step=-1)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = cycle_index(self.index, total=len(self.embeds), step=1)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)
