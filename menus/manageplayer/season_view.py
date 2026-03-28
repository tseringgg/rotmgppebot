"""Season loot views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    ManagedPlayerTarget,
    close_manageplayer_menu,
    load_target_player_data,
    send_followup_text,
    send_target_season_loot_markdown_followup,
)
from menus.menu_utils import OwnerBoundView


class ManagePlayerSeasonLootView(OwnerBoundView):
    """View for admin to view a player's season loot."""

    def __init__(self, *, owner_id: int, target: ManagedPlayerTarget, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title=f"Show Season Loot - {self.target.display_name}",
            description="Choose an action.",
            color=discord.Color.gold(),
        )

    @discord.ui.button(label="List Season Loot", style=discord.ButtonStyle.secondary, row=0)
    async def list_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
        player_data = await load_target_player_data(interaction, self.target.user_id)
        await interaction.response.defer()
        await send_target_season_loot_markdown_followup(interaction, target=self.target, player_data=player_data)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
