"""Reusable "Show Image" buttons that render a team's combined season loot."""

from __future__ import annotations

import time
from typing import Awaitable, Callable

import discord

from menus.menu_utils.loot_image_variants import LOOT_IMAGE_VARIANTS, LootImageVariant
from utils.bot_cost_tracking import capture_runtime_snapshot, log_cost_event
from utils.loot_helpers.loot_share_commands import (
    send_team_season_loot_markdown_followup,
    share_team_loot_image,
)

BeforeShareHook = Callable[[discord.Interaction], Awaitable[None]]


class TeamLootImageButton(discord.ui.Button):
    """Button that posts the combined loot image of one team for a single variant."""

    def __init__(
        self,
        *,
        team_name: str,
        variant: LootImageVariant,
        command_name: str,
        row: int,
        before_share: BeforeShareHook | None = None,
    ) -> None:
        super().__init__(label=variant.label, style=discord.ButtonStyle.primary, row=row)
        self.team_name = team_name
        self.variant = variant
        self.command_name = command_name
        self.before_share = before_share

    async def _prepare_interaction(self, interaction: discord.Interaction) -> None:
        # Either let the owning menu clean itself up, or just ack so the source message stays as-is.
        if self.before_share is not None:
            await self.before_share(interaction)
        elif not interaction.response.is_done():
            await interaction.response.defer()

    async def callback(self, interaction: discord.Interaction) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()

        await self._prepare_interaction(interaction)
        await share_team_loot_image(
            interaction,
            team_name=self.team_name,
            include_skins=self.variant.include_skins,
            include_limited=self.variant.include_limited,
        )
        await log_cost_event(
            interaction,
            command_name=f"{self.command_name} team loot image ({self.variant.display_name})",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )


class TeamLootListButton(discord.ui.Button):
    """Button that exports the combined season loot of one team as a markdown file."""

    def __init__(
        self,
        *,
        team_name: str,
        command_name: str,
        row: int,
        label: str = "List Loot",
        before_share: BeforeShareHook | None = None,
    ) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary, row=row)
        self.team_name = team_name
        self.command_name = command_name
        self.before_share = before_share

    async def _prepare_interaction(self, interaction: discord.Interaction) -> None:
        if self.before_share is not None:
            await self.before_share(interaction)
        elif not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

    async def callback(self, interaction: discord.Interaction) -> None:
        started_monotonic = time.monotonic()
        snapshot_before = capture_runtime_snapshot()

        await self._prepare_interaction(interaction)
        await send_team_season_loot_markdown_followup(
            interaction,
            team_name=self.team_name,
            ephemeral=True,
        )
        await log_cost_event(
            interaction,
            command_name=f"{self.command_name} list team season loot",
            started_monotonic=started_monotonic,
            snapshot_before=snapshot_before,
            source="menu_action",
        )


def add_team_loot_image_buttons(
    view: discord.ui.View,
    *,
    team_name: str,
    row: int,
    command_name: str,
    before_share: BeforeShareHook | None = None,
    include_list_loot: bool = True,
) -> None:
    """Attach one ``TeamLootImageButton`` per loot image variant and optionally a "List Loot" button to ``view`` on ``row``."""
    for variant in LOOT_IMAGE_VARIANTS:
        view.add_item(
            TeamLootImageButton(
                team_name=team_name,
                variant=variant,
                command_name=command_name,
                row=row,
                before_share=before_share,
            )
        )
    if include_list_loot:
        view.add_item(
            TeamLootListButton(
                team_name=team_name,
                command_name=command_name,
                row=row,
                before_share=before_share,
            )
        )


__all__ = ["TeamLootImageButton", "TeamLootListButton", "add_team_loot_image_buttons"]
