"""Season loot variant view for /myinfo."""

from __future__ import annotations

import discord

from menus.menu_utils.season_loot_variants import SeasonLootVariantActionsView
from menus.myinfo.common import (
    close_myinfo_menu,
    send_interaction_text,
    send_season_loot_markdown_followup,
)
from utils.helpers.loot_share_commands import share_season_loot_image
from utils.player_records import ensure_player_exists, load_player_records


class SeasonLootVariantView(SeasonLootVariantActionsView):
    """View for selecting season loot output variants and list actions."""

    def __init__(self, owner_id: int, *, max_ppes: int):
        super().__init__(owner_id=owner_id, title="Show Season Loot", timeout=600)
        self.max_ppes = max_ppes

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

    async def _list_season_loot(self, interaction: discord.Interaction) -> None:
        await close_myinfo_menu(interaction)
        await send_season_loot_markdown_followup(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)


__all__ = ["SeasonLootVariantView"]
