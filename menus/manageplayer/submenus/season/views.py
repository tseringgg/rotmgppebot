"""Season loot views for the /manageplayer admin menu."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.manageplayer.common import (
    close_manageplayer_menu,
    send_target_season_loot_markdown_followup,
)
from menus.manageplayer.services import load_target_player_data
from menus.manageplayer.targets import ManagedPlayerTarget
from menus.menu_utils.season_loot_variants import SeasonLootVariantActionsView
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
        view = ManagePlayerSeasonStatisticsView(
            owner_id=interaction.user.id,
            target=self.target,
            max_ppes=self.max_ppes,
        )
        embed = build_season_wrapped_embed(player_data=player_data, display_name=self.target.display_name)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)


class ManagePlayerSeasonStatisticsView(OwnerBoundView):
    """Spotify Wrapped-style season recap view for /manageplayer target users."""

    def __init__(self, *, owner_id: int, target: ManagedPlayerTarget, max_ppes: int) -> None:
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.target = target
        self.max_ppes = max_ppes

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        view = ManagePlayerSeasonLootView(owner_id=interaction.user.id, target=self.target, max_ppes=self.max_ppes)
        await interaction.response.edit_message(embed=view.current_embed(), view=view)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_manageplayer_menu(interaction)
