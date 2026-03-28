"""Season loot views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    ManagedPlayerTarget,
    close_manageplayer_menu,
    load_target_player_data,
    send_target_season_loot_markdown_followup,
)
from menus.menu_utils import OwnerBoundView
from utils.helpers.loot_share_commands import share_season_loot_image


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

    async def _close_and_share(
        self,
        interaction: discord.Interaction,
        *,
        include_skins: bool,
        include_limited: bool,
    ) -> None:
        await close_manageplayer_menu(interaction)
        await share_season_loot_image(
            interaction,
            include_skins=include_skins,
            include_limited=include_limited,
            target_user_id=self.target.user_id,
            target_display_name=self.target.display_name,
            error_ephemeral=False,
        )

    @discord.ui.button(label="Generate Image: Normal Only", style=discord.ButtonStyle.primary, row=0)
    async def normal_only(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=False)

    @discord.ui.button(label="Generate Image: Normal + Limited", style=discord.ButtonStyle.primary, row=0)
    async def normal_limited(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=False, include_limited=True)

    @discord.ui.button(label="Generate Image: Normal + Skins", style=discord.ButtonStyle.primary, row=1)
    async def normal_skins(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=False)

    @discord.ui.button(label="Generate Image: All Loot", style=discord.ButtonStyle.success, row=1)
    async def all_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self._close_and_share(interaction, include_skins=True, include_limited=True)

    @discord.ui.button(label="List Season Loot", style=discord.ButtonStyle.secondary, row=2)
    async def list_season_loot(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
        player_data = await load_target_player_data(interaction, self.target.user_id)
        await send_target_season_loot_markdown_followup(interaction, target=self.target, player_data=player_data)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
