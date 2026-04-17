"""Season loot variant view for /myinfo."""

from __future__ import annotations

import time

import discord

from menus.menu_utils.season_loot_variants import SeasonLootVariantActionsView
from menus.myinfo.common import (
    close_myinfo_menu,
    send_interaction_text,
    send_season_loot_markdown_followup,
)
from utils.guild_config import load_guild_config
from utils.bot_cost_tracking import capture_runtime_snapshot, log_cost_event
from utils.player_statistics import build_season_wrapped_embed
from utils.time_graphs import build_item_graph
from utils.loot_helpers.loot_share_commands import share_season_loot_image
from utils.player_records import ensure_player_exists, load_player_records
from utils.season_loot_history import iter_season_variants


class SeasonLootVariantView(SeasonLootVariantActionsView):
    """View for selecting season loot output variants and list actions."""

    def __init__(self, owner_id: int, *, max_ppes: int):
        super().__init__(owner_id=owner_id, title="Show Season Stats", timeout=600)
        self.max_ppes = max_ppes

    async def _share(self, interaction: discord.Interaction, *, include_skins: bool, include_limited: bool) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]

        if key not in records or not player_data.is_member:
            await send_interaction_text(interaction, "❌ You're not part of the PPE contest.", ephemeral=True)
            return

        if not iter_season_variants(player_data):
            await send_interaction_text(
                interaction,
                "You haven't collected any season loot yet!\nUse `/addseasonloot` to start tracking your unique items.",
                ephemeral=True,
            )
            return

        await share_season_loot_image(interaction, include_skins=include_skins, include_limited=include_limited)
        variant_name = "season loot image"
        if include_skins and include_limited:
            variant_name = "season loot image (all loot)"
        elif include_skins:
            variant_name = "season loot image (normal + skins)"
        elif include_limited:
            variant_name = "season loot image (normal + limited)"
        else:
            variant_name = "season loot image (normal only)"

        await log_cost_event(
            interaction,
            command_name=f"/myinfo show image {variant_name}",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

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
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        await close_myinfo_menu(interaction)
        await send_season_loot_markdown_followup(interaction)
        await log_cost_event(
            interaction,
            command_name="/myinfo list season loot",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    async def _show_statistics(self, interaction: discord.Interaction) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]
        guild_config = await load_guild_config(interaction)
        embed = build_season_wrapped_embed(
            player_data=player_data,
            display_name=interaction.user.display_name,
            guild_config=guild_config,
        )
        await close_myinfo_menu(interaction)
        await interaction.followup.send(embed=embed, ephemeral=False)
        await log_cost_event(
            interaction,
            command_name="/myinfo statistics (season)",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    async def _show_item_graph(self, interaction: discord.Interaction) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()
        records = await load_player_records(interaction)
        key = ensure_player_exists(records, interaction.user.id)
        player_data = records[key]

        # Close the source menu first so long graph renders do not hit Discord's response timeout.
        await close_myinfo_menu(interaction)

        graph_image = build_item_graph(player_data, display_name=interaction.user.display_name)
        if graph_image is None:
            await interaction.followup.send(
                "No season loot timestamps found yet. Add season loot first to generate an item graph.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            file=discord.File(graph_image, filename="season_item_graph.png"),
            ephemeral=False,
        )
        await log_cost_event(
            interaction,
            command_name="/myinfo season item graph",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await close_myinfo_menu(interaction)


__all__ = ["SeasonLootVariantView"]
