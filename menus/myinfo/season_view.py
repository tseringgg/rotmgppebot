"""Season loot actions shown from the /myinfo dashboard."""

from __future__ import annotations

import discord

from menus.menu_utils import OwnerBoundView
from menus.myinfo.common import (
    close_myinfo_menu,
    send_interaction_text,
    send_season_loot_markdown_followup,
)
from utils.helpers.loot_share_commands import share_season_loot_image
from utils.player_records import ensure_player_exists, load_player_records


class SeasonLootVariantView(OwnerBoundView):
    """View for selecting season loot output variants and list actions."""

    def __init__(self, owner_id: int, *, max_ppes: int):
        super().__init__(owner_id=owner_id, timeout=600, owner_error="This menu belongs to another user.")
        self.max_ppes = max_ppes

    def current_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Show Season Loot",
            description="Choose an action.",
            color=discord.Color.gold(),
        )

    async def _share(self, interaction: discord.Interaction, *, include_skins: bool, include_limited: bool) -> None:
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]

        if key not in records or not player_data.is_member:
            await send_interaction_text(interaction, "❌ You're not part of the PPE contest.", ephemeral=True)
            return

        if not player_data.unique_items:
            await send_interaction_text(
                interaction,
                "You haven't collected any season loot yet!\nUse `/addseasonloot` to start tracking your unique items.",
                ephemeral=True,
            )
            return

        await share_season_loot_image(interaction, include_skins=include_skins, include_limited=include_limited)

    async def _close_and_share(
        self,
        interaction: discord.Interaction,
        *,
        include_skins: bool,
        include_limited: bool,
    ) -> None:
        await close_myinfo_menu(interaction)
        await self._share(interaction, include_skins=include_skins, include_limited=include_limited)

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
        await close_myinfo_menu(interaction)
        await send_season_loot_markdown_followup(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)
