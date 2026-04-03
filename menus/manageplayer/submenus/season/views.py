"""Season loot views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.manageplayer.common import (
    close_manageplayer_menu,
    send_target_season_loot_markdown_followup,
)
from menus.manageplayer.services import load_target_player_data
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils.season_loot_variants import SeasonLootVariantActionsView
from utils.guild_config import load_guild_config
from utils.player_statistics import build_season_wrapped_embed
from utils.helpers.loot_share_commands import share_season_loot_image


class ManagePlayerSeasonLootView(SeasonLootVariantActionsView):
    """View for admin to view a player's season loot."""

    def __init__(self, *, owner_id: int, target: ManagedPlayerTarget, max_ppes: int):
        super().__init__(owner_id=owner_id, title=f"Show Season Stats - {target.display_name}", timeout=600)
        self.target = target
        self.max_ppes = max_ppes

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

    async def _list_season_loot(self, interaction: discord.Interaction) -> None:
        await close_manageplayer_menu(interaction)
        player_data = await load_target_player_data(interaction, self.target.user_id)
        await send_target_season_loot_markdown_followup(interaction, target=self.target, player_data=player_data)

    async def _show_statistics(self, interaction: discord.Interaction) -> None:
        player_data = await load_target_player_data(interaction, self.target.user_id)
        guild_config = await load_guild_config(interaction)
        embed = build_season_wrapped_embed(
            player_data=player_data,
            display_name=self.target.display_name,
            guild_config=guild_config,
        )
        await close_manageplayer_menu(interaction)
        await interaction.followup.send(embed=embed, ephemeral=False)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
