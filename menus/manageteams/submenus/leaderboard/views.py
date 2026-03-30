"""Leaderboard preview view for /manageteams admin menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView


class LeaderboardPreviewView(OwnerBoundView):
    """Paginated team leaderboard display."""

    def __init__(self, *, owner_id: int, embeds: list[discord.Embed]) -> None:
        super().__init__(owner_id=owner_id, timeout=180, owner_error="This menu belongs to another user.")
        self.owner_id = owner_id
        self.embeds = embeds
        self.index = 0

        if len(self.embeds) <= 1:
            self.remove_item(self.prev_page)
            self.remove_item(self.next_page)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, row=0)
    async def prev_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index - 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, row=0)
    async def next_page(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        self.index = (self.index + 1) % len(self.embeds)
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)
